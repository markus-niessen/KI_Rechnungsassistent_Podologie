from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Invoice, Patient
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app.state.test_engine = engine

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    del app.state.test_engine
    Base.metadata.drop_all(engine)


def create_patient(client: TestClient, first_name: str, last_name: str, **extra: object) -> dict[str, object]:
    response = client.post("/patients", json={"first_name": first_name, "last_name": last_name, **extra})
    assert response.status_code == 201
    return response.json()


def test_patient_can_be_created_with_automatic_number(client: TestClient) -> None:
    patient = create_patient(client, "Anna", "Meyer")

    assert patient["patient_nr"] == "P-000001"
    assert patient["active"] is True
    assert patient["first_name"] == "Anna"


def test_patients_receive_different_sequential_numbers(client: TestClient) -> None:
    first_patient = create_patient(client, "Anna", "Meyer")
    second_patient = create_patient(client, "Bernd", "Klein")

    assert first_patient["patient_nr"] == "P-000001"
    assert second_patient["patient_nr"] == "P-000002"


def test_list_shows_active_patients_and_searches_case_insensitively(client: TestClient) -> None:
    matching_patient = create_patient(client, "Anna", "Meyer")
    create_patient(client, "Bernd", "Klein")

    response = client.get("/patients", params={"search": "ANNA"})

    assert response.status_code == 200
    assert [patient["id"] for patient in response.json()] == [matching_patient["id"]]


def test_patient_can_be_retrieved_and_unknown_patient_returns_404(client: TestClient) -> None:
    patient = create_patient(client, "Clara", "Wolf")

    response = client.get(f"/patients/{patient['id']}")
    missing_response = client.get("/patients/999")

    assert response.status_code == 200
    assert response.json()["patient_nr"] == "P-000001"
    assert missing_response.status_code == 404


def test_patient_can_be_updated_without_changing_patient_nr(client: TestClient) -> None:
    patient = create_patient(client, "David", "Koch")

    response = client.patch(
        f"/patients/{patient['id']}",
        json={"first_name": "Daniel", "city": "Köln"},
    )
    invalid_response = client.patch(
        f"/patients/{patient['id']}",
        json={"patient_nr": "P-999999"},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Daniel"
    assert response.json()["city"] == "Köln"
    assert response.json()["patient_nr"] == "P-000001"
    assert invalid_response.status_code == 422


def test_deactivated_patient_is_hidden_unless_requested(client: TestClient) -> None:
    active_patient = create_patient(client, "Eva", "Bauer")
    inactive_patient = create_patient(client, "Frank", "Sommer")

    response = client.post(f"/patients/{inactive_patient['id']}/deactivate")
    default_list = client.get("/patients")
    complete_list = client.get("/patients", params={"include_inactive": "true"})

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert [patient["id"] for patient in default_list.json()] == [active_patient["id"]]
    assert [patient["id"] for patient in complete_list.json()] == [
        active_patient["id"],
        inactive_patient["id"],
    ]


def test_patient_can_be_reactivated(client: TestClient) -> None:
    patient = create_patient(client, "Gabi", "Lenz")

    client.post(f"/patients/{patient['id']}/deactivate")
    response = client.post(f"/patients/{patient['id']}/activate")

    assert response.status_code == 200
    assert response.json()["active"] is True


def test_unused_patient_requires_confirmation_before_hard_delete(client: TestClient) -> None:
    patient = create_patient(client, "Hugo", "Maas")

    unconfirmed_response = client.delete(f"/patients/{patient['id']}")
    confirmed_response = client.delete(f"/patients/{patient['id']}", params={"confirm": "true"})
    get_response = client.get(f"/patients/{patient['id']}")

    assert unconfirmed_response.status_code == 400
    assert confirmed_response.status_code == 204
    assert get_response.status_code == 404


def test_patient_with_invoice_cannot_be_hard_deleted(client: TestClient) -> None:
    patient_data = create_patient(client, "Ines", "Roth")
    with Session(app.state.test_engine) as session:
        patient = session.get(Patient, patient_data["id"])
        session.add(
            Invoice(
                patient=patient,
                invoice_date=date(2026, 8, 19),
                due_date=date(2026, 8, 26),
                status="DRAFT",
                total_net=Decimal("0.00"),
                total_vat=Decimal("0.00"),
                total_gross=Decimal("0.00"),
            )
        )
        session.commit()

    response = client.delete(f"/patients/{patient_data['id']}", params={"confirm": "true"})

    assert response.status_code == 409


def test_patient_supports_invoice_address_and_home_fields(client: TestClient) -> None:
    patient = create_patient(
        client,
        "Maria",
        "Beispiel",
        invoice_name="Pflegeheim Muster",
        invoice_street="Rechnungsweg 1",
        invoice_zip="50667",
        invoice_city="Köln",
        home_name="Seniorenhaus Beispiel",
        room="2.14",
    )

    assert patient["invoice_name"] == "Pflegeheim Muster"
    assert patient["invoice_street"] == "Rechnungsweg 1"
    assert patient["invoice_zip"] == "50667"
    assert patient["invoice_city"] == "Köln"
    assert patient["home_name"] == "Seniorenhaus Beispiel"
    assert patient["room"] == "2.14"


def test_patient_deceased_states_and_updated_at(client: TestClient) -> None:
    living_patient = create_patient(client, "Nina", "Berg")
    deceased_patient = create_patient(
        client,
        "Otto",
        "Tal",
        deceased=True,
        death_date="2026-08-01",
    )
    unknown_death_date_patient = create_patient(client, "Paul", "See", deceased=True)
    inactive_patient = create_patient(client, "Rita", "Wald")

    initial_updated_at = living_patient["updated_at"]
    update_response = client.patch(
        f"/patients/{living_patient['id']}",
        json={"city": "Köln", "deceased": True},
    )
    client.post(f"/patients/{inactive_patient['id']}/deactivate")

    assert living_patient["deceased"] is False
    assert living_patient["death_date"] is None
    assert deceased_patient["deceased"] is True
    assert deceased_patient["death_date"] == "2026-08-01"
    assert deceased_patient["active"] is False
    assert unknown_death_date_patient["deceased"] is True
    assert unknown_death_date_patient["death_date"] is None
    assert unknown_death_date_patient["active"] is False
    assert update_response.json()["active"] is False
    assert update_response.json()["updated_at"] != initial_updated_at
    assert client.post(f"/patients/{deceased_patient['id']}/activate").status_code == 409
    assert client.get(f"/patients/{inactive_patient['id']}").json()["deceased"] is False


def test_deceased_status_can_be_corrected_before_reactivation(client: TestClient) -> None:
    patient = create_patient(
        client,
        "Sven",
        "Klar",
        deceased=True,
        death_date="2026-08-10",
    )

    correction_response = client.patch(
        f"/patients/{patient['id']}",
        json={"deceased": False},
    )
    activate_response = client.post(f"/patients/{patient['id']}/activate")

    assert correction_response.status_code == 200
    assert correction_response.json()["deceased"] is False
    assert correction_response.json()["death_date"] is None
    assert correction_response.json()["active"] is False
    assert activate_response.status_code == 200
    assert activate_response.json()["active"] is True


def test_patient_invoices_include_drafts_finals_and_no_duplicates(client: TestClient) -> None:
    business_profile_response = client.post(
        "/business-profiles",
        json={
            "business_name": "Podologie Testpraxis",
            "location_name": "Köln",
            "location_code": "TEST",
            "street": "Teststraße 1",
            "postal_code": "50667",
            "city": "Köln",
            "iban": "DE89370400440532013000",
        },
    )
    service_response = client.post(
        "/services",
        json={"name": "Podologische Behandlung", "net_price": "38.00", "vat_rate": "19.00"},
    )
    patient = create_patient(
        client,
        "Anna",
        "Beispiel",
        street="Musterweg 5",
        zip="50667",
        city="Köln",
    )
    other_patient = create_patient(client, "Bernd", "Anders")
    patient_without_invoices = create_patient(client, "Clara", "Leer")
    company_id = business_profile_response.json()["id"]
    service_id = service_response.json()["id"]

    def create_invoice_for(patient_id: int) -> dict[str, object]:
        invoice_response = client.post(
            "/invoices",
            json={
                "company_id": company_id,
                "invoice_date": "2026-08-19",
                "due_date": "2026-09-02",
            },
        )
        assert invoice_response.status_code == 201
        invoice = invoice_response.json()
        add_item_response = client.post(
            f"/invoices/{invoice['id']}/items",
            json={"service_id": service_id, "patient_id": patient_id},
        )
        assert add_item_response.status_code == 201
        return invoice

    draft_invoice = create_invoice_for(patient["id"])
    second_item_response = client.post(
        f"/invoices/{draft_invoice['id']}/items",
        json={"service_id": service_id, "patient_id": patient["id"]},
    )
    final_invoice = create_invoice_for(patient["id"])
    other_invoice = create_invoice_for(other_patient["id"])
    final_response = client.post(f"/invoices/{final_invoice['id']}/finalize")

    response = client.get(f"/patients/{patient['id']}/invoices")
    empty_response = client.get(f"/patients/{patient_without_invoices['id']}/invoices")
    missing_response = client.get("/patients/999/invoices")

    assert second_item_response.status_code == 201
    assert final_response.status_code == 200
    assert response.status_code == 200
    invoices = response.json()
    assert [invoice["id"] for invoice in invoices] == [draft_invoice["id"], final_invoice["id"]]
    assert invoices[0]["status"] == "DRAFT"
    assert invoices[0]["invoice_number"] is None
    assert invoices[0]["item_count"] == 2
    assert invoices[0]["pdf_available"] is False
    assert invoices[1]["status"] == "FINAL"
    assert invoices[1]["invoice_number"] == "TEST-RE-2026-000001"
    assert invoices[1]["item_count"] == 1
    assert invoices[1]["pdf_available"] is True
    assert invoices[1]["subtotal"] == "38.00"
    assert invoices[1]["tax_total"] == "7.22"
    assert invoices[1]["total"] == "45.22"
    assert other_invoice["id"] not in [invoice["id"] for invoice in invoices]
    assert empty_response.status_code == 200
    assert empty_response.json() == []
    assert missing_response.status_code == 404
