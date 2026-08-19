from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Invoice
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


def create_business_profile(client: TestClient) -> dict[str, object]:
    response = client.post(
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
    assert response.status_code == 201
    return response.json()


def create_service(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/services",
        json={"name": "Podologische Behandlung", "net_price": "38.00", "vat_rate": "19.00"},
    )
    assert response.status_code == 201
    return response.json()


def create_patient(client: TestClient) -> dict[str, object]:
    response = client.post("/patients", json={"first_name": "Anna", "last_name": "Beispiel"})
    assert response.status_code == 201
    return response.json()


def create_billable_patient(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/patients",
        json={
            "first_name": "Anna",
            "last_name": "Beispiel",
            "street": "Musterweg 5",
            "zip": "50667",
            "city": "Köln",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_invoice(client: TestClient, company_id: int) -> dict[str, object]:
    response = client.post(
        "/invoices",
        json={
            "company_id": company_id,
            "document_type": "INVOICE",
            "invoice_date": "2026-08-19",
            "due_date": "2026-09-02",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_invoice_draft_crud_list_and_company_validation(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    invoice = create_invoice(client, business_profile["id"])

    list_response = client.get("/invoices")
    get_response = client.get(f"/invoices/{invoice['id']}")
    update_response = client.patch(f"/invoices/{invoice['id']}", json={"due_date": "2026-09-10"})
    missing_company_response = client.post(
        "/invoices",
        json={"company_id": 999, "invoice_date": "2026-08-19", "due_date": "2026-09-02"},
    )
    unknown_field_response = client.post(
        "/invoices",
        json={
            "company_id": business_profile["id"],
            "invoice_date": "2026-08-19",
            "due_date": "2026-09-02",
            "status": "FINAL",
        },
    )

    assert invoice["status"] == "DRAFT"
    assert invoice["invoice_number"] is None
    assert invoice["company_id"] == business_profile["id"]
    assert invoice["items"] == []
    assert [entry["id"] for entry in list_response.json()] == [invoice["id"]]
    assert get_response.json()["id"] == invoice["id"]
    assert update_response.json()["due_date"] == "2026-09-10"
    assert missing_company_response.status_code == 404
    assert unknown_field_response.status_code == 422
    assert client.get("/invoices/999").status_code == 404


def test_invoice_items_snapshot_and_recalculate_totals(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    patient = create_patient(client)
    invoice = create_invoice(client, business_profile["id"])

    add_response = client.post(
        f"/invoices/{invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"], "quantity": "2.00"},
    )
    added_invoice = add_response.json()
    item = added_invoice["items"][0]
    update_response = client.patch(
        f"/invoices/{invoice['id']}/items/{item['id']}", json={"quantity": "1.00"}
    )
    delete_response = client.delete(f"/invoices/{invoice['id']}/items/{item['id']}")
    item_list_response = client.get(f"/invoices/{invoice['id']}/items")

    assert add_response.status_code == 201
    assert item["service_name_snapshot"] == "Podologische Behandlung"
    assert item["patient_name_snapshot"] == "Anna Beispiel"
    assert Decimal(str(item["unit_price"])) == Decimal("38.00")
    assert Decimal(str(item["vat_rate"])) == Decimal("19.00")
    assert Decimal(str(item["line_total"])) == Decimal("90.44")
    assert Decimal(str(added_invoice["subtotal"])) == Decimal("76.00")
    assert Decimal(str(added_invoice["tax_total"])) == Decimal("14.44")
    assert Decimal(str(added_invoice["total"])) == Decimal("90.44")
    assert Decimal(str(update_response.json()["total"])) == Decimal("45.22")
    assert delete_response.status_code == 204
    assert item_list_response.json() == []
    assert Decimal(str(client.get(f"/invoices/{invoice['id']}").json()["total"])) == Decimal("0.00")


def test_invoice_draft_preview_contains_company_items_and_totals(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    patient = create_patient(client)
    invoice = create_invoice(client, business_profile["id"])

    client.post(
        f"/invoices/{invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"], "quantity": "2.00"},
    )
    preview_response = client.get(f"/invoices/{invoice['id']}")

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["company"] == {
        "id": business_profile["id"],
        "business_name": "Podologie Testpraxis",
        "location_name": "Köln",
        "location_code": "TEST",
        "invoice_prefix": "TEST",
    }
    assert preview["item_count"] == 1
    assert preview["items"][0]["patient_name_snapshot"] == "Anna Beispiel"
    assert preview["items"][0]["service_name_snapshot"] == "Podologische Behandlung"
    assert Decimal(str(preview["subtotal"])) == Decimal("76.00")
    assert Decimal(str(preview["tax_total"])) == Decimal("14.44")
    assert Decimal(str(preview["total"])) == Decimal("90.44")


def test_invoice_worklist_filters_drafts_and_keeps_drafts_independent(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    first_draft = create_invoice(client, business_profile["id"])
    second_draft = create_invoice(client, business_profile["id"])

    first_item_response = client.post(
        f"/invoices/{first_draft['id']}/items",
        json={"service_id": service["id"], "quantity": "2.00"},
    )
    first_item_id = first_item_response.json()["items"][0]["id"]
    client.patch(
        f"/invoices/{first_draft['id']}/items/{first_item_id}",
        json={"quantity": "3.00"},
    )
    client.patch(f"/invoices/{first_draft['id']}", json={"due_date": "2026-09-10"})

    worklist_response = client.get("/invoices?status=DRAFT")

    assert worklist_response.status_code == 200
    worklist = worklist_response.json()
    assert [entry["id"] for entry in worklist] == [first_draft["id"], second_draft["id"]]
    assert worklist[0]["item_count"] == 1
    assert Decimal(str(worklist[0]["total"])) == Decimal("135.66")
    assert worklist[0]["due_date"] == "2026-09-10"
    assert worklist[1]["item_count"] == 0
    assert Decimal(str(worklist[1]["total"])) == Decimal("0.00")
    assert worklist[1]["due_date"] == "2026-09-02"


def test_finalize_invoice_assigns_number_snapshots_and_keeps_other_drafts_editable(
    client: TestClient,
) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    patient = create_billable_patient(client)
    first_invoice = create_invoice(client, business_profile["id"])
    second_invoice = create_invoice(client, business_profile["id"])
    first_item_response = client.post(
        f"/invoices/{first_invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"], "quantity": "2.00"},
    )
    first_item = first_item_response.json()["items"][0]
    client.post(
        f"/invoices/{second_invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"]},
    )

    finalized_response = client.post(f"/invoices/{first_invoice['id']}/finalize")
    second_draft_update = client.patch(
        f"/invoices/{second_invoice['id']}", json={"due_date": "2026-09-10"}
    )
    second_finalized_response = client.post(f"/invoices/{second_invoice['id']}/finalize")

    assert first_invoice["invoice_number"] is None
    assert finalized_response.status_code == 200
    finalized = finalized_response.json()
    assert finalized["status"] == "FINAL"
    assert finalized["invoice_number"] == "TEST-RE-2026-000001"
    assert Decimal(str(finalized["subtotal"])) == Decimal("76.00")
    assert Decimal(str(finalized["tax_total"])) == Decimal("14.44")
    assert Decimal(str(finalized["total"])) == Decimal("90.44")
    assert finalized["items"][0]["patient_name_snapshot"] == "Anna Beispiel"
    assert finalized["items"][0]["service_name_snapshot"] == "Podologische Behandlung"
    assert Decimal(str(finalized["items"][0]["unit_price"])) == Decimal("38.00")
    assert Decimal(str(finalized["items"][0]["vat_rate"])) == Decimal("19.00")
    assert second_draft_update.status_code == 200
    assert second_draft_update.json()["status"] == "DRAFT"
    assert second_finalized_response.json()["invoice_number"] == "TEST-RE-2026-000002"

    client.patch(f"/services/{service['id']}", json={"name": "Geänderte Leistung"})
    client.patch(f"/patients/{patient['id']}", json={"first_name": "Geändert"})
    stored_final = client.get(f"/invoices/{first_invoice['id']}").json()
    assert stored_final["items"][0]["patient_name_snapshot"] == "Anna Beispiel"
    assert stored_final["items"][0]["service_name_snapshot"] == "Podologische Behandlung"

    assert client.patch(f"/invoices/{first_invoice['id']}", json={"due_date": "2026-09-11"}).status_code == 409
    assert client.post(
        f"/invoices/{first_invoice['id']}/items", json={"service_id": service["id"]}
    ).status_code == 409
    assert client.patch(
        f"/invoices/{first_invoice['id']}/items/{first_item['id']}", json={"quantity": "1.00"}
    ).status_code == 409
    assert client.delete(f"/invoices/{first_invoice['id']}/items/{first_item['id']}").status_code == 409


def test_finalize_invoice_validates_draft_requirements(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    empty_invoice = create_invoice(client, business_profile["id"])
    unaddressed_invoice = create_invoice(client, business_profile["id"])
    item_response = client.post(
        f"/invoices/{unaddressed_invoice['id']}/items", json={"service_id": service["id"]}
    )

    empty_response = client.post(f"/invoices/{empty_invoice['id']}/finalize")
    unaddressed_response = client.post(f"/invoices/{unaddressed_invoice['id']}/finalize")

    assert empty_response.status_code == 422
    assert unaddressed_response.status_code == 422
    assert client.post("/invoices/999/finalize").status_code == 404

    patient = create_billable_patient(client)
    item_id = item_response.json()["items"][0]["id"]
    patient_update = client.patch(
        f"/invoices/{unaddressed_invoice['id']}/items/{item_id}",
        json={"patient_id": patient["id"]},
    )
    successful_response = client.post(f"/invoices/{unaddressed_invoice['id']}/finalize")

    assert patient_update.status_code == 200
    assert successful_response.status_code == 200
    assert successful_response.json()["status"] == "FINAL"
    assert client.post(f"/invoices/{unaddressed_invoice['id']}/finalize").status_code == 409


def test_invoice_item_validation_and_non_draft_protection(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    invoice = create_invoice(client, business_profile["id"])

    invalid_service_response = client.post(
        f"/invoices/{invoice['id']}/items", json={"service_id": 999}
    )
    invalid_patient_response = client.post(
        f"/invoices/{invoice['id']}/items", json={"service_id": service["id"], "patient_id": 999}
    )
    unknown_field_response = client.post(
        f"/invoices/{invoice['id']}/items", json={"service_id": service["id"], "unit_price": "1.00"}
    )
    item_response = client.post(f"/invoices/{invoice['id']}/items", json={"service_id": service["id"]})
    item_id = item_response.json()["items"][0]["id"]

    with Session(app.state.test_engine) as session:
        stored_invoice = session.get(Invoice, invoice["id"])
        stored_invoice.status = "FINAL"
        session.commit()

    update_invoice_response = client.patch(f"/invoices/{invoice['id']}", json={"due_date": "2026-09-10"})
    update_item_response = client.patch(
        f"/invoices/{invoice['id']}/items/{item_id}", json={"quantity": "2.00"}
    )
    delete_item_response = client.delete(f"/invoices/{invoice['id']}/items/{item_id}")

    assert invalid_service_response.status_code == 404
    assert invalid_patient_response.status_code == 404
    assert unknown_field_response.status_code == 422
    assert update_invoice_response.status_code == 409
    assert update_item_response.status_code == 409
    assert delete_item_response.status_code == 409
