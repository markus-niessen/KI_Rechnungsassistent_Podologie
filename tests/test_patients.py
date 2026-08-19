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


def create_patient(client: TestClient, first_name: str, last_name: str) -> dict[str, object]:
    response = client.post("/patients", json={"first_name": first_name, "last_name": last_name})
    assert response.status_code == 201
    return response.json()


def test_patient_can_be_created_with_automatic_number(client: TestClient) -> None:
    patient = create_patient(client, "Anna", "Meyer")

    assert patient["patient_number"] == "P-000001"
    assert patient["active"] is True
    assert patient["first_name"] == "Anna"


def test_patients_receive_different_sequential_numbers(client: TestClient) -> None:
    first_patient = create_patient(client, "Anna", "Meyer")
    second_patient = create_patient(client, "Bernd", "Klein")

    assert first_patient["patient_number"] == "P-000001"
    assert second_patient["patient_number"] == "P-000002"


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
    assert response.json()["patient_number"] == "P-000001"
    assert missing_response.status_code == 404


def test_patient_can_be_updated_without_changing_patient_number(client: TestClient) -> None:
    patient = create_patient(client, "David", "Koch")

    response = client.patch(
        f"/patients/{patient['id']}",
        json={"first_name": "Daniel", "city": "Köln"},
    )
    invalid_response = client.patch(
        f"/patients/{patient['id']}",
        json={"patient_number": "P-999999"},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Daniel"
    assert response.json()["city"] == "Köln"
    assert response.json()["patient_number"] == "P-000001"
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
