from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
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


def create_final_invoice(client: TestClient) -> dict[str, object]:
    business_profile = client.post(
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
    ).json()
    service = client.post(
        "/services",
        json={"name": "Behandlung", "net_price": "48.74", "vat_rate": "19.00"},
    ).json()
    patient = client.post(
        "/patients",
        json={
            "first_name": "Alex",
            "last_name": "Beispiel",
            "street": "Musterweg 1",
            "zip": "50667",
            "city": "Köln",
        },
    ).json()
    invoice = client.post(
        "/invoices",
        json={"company_id": business_profile["id"], "invoice_date": "2026-08-20", "due_date": "2026-09-03"},
    ).json()
    item_response = client.post(
        f"/invoices/{invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"]},
    )
    assert item_response.status_code == 201
    final_response = client.post(f"/invoices/{invoice['id']}/finalize")
    assert final_response.status_code == 200
    return final_response.json()


def test_payment_partial_payment_and_paid_status(client: TestClient) -> None:
    invoice = create_final_invoice(client)

    assert client.get(f"/invoices/{invoice['id']}").json()["payment_status"] == "OPEN"
    first_payment_response = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "20.00", "payment_date": "2026-08-20", "payment_method": "CASH"},
    )
    first_payment = first_payment_response.json()
    invoice_after_cash = client.get(f"/invoices/{invoice['id']}").json()
    payment_list = client.get(f"/invoices/{invoice['id']}/payments").json()
    second_payment_response = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "38.00", "payment_date": "2026-08-21", "payment_method": "BANK_TRANSFER", "note": "Restbetrag"},
    )
    invoice_after_transfer = client.get(f"/invoices/{invoice['id']}").json()
    all_payments = client.get(f"/invoices/{invoice['id']}/payments").json()

    assert first_payment_response.status_code == 201
    assert client.get(f"/payments/{first_payment['id']}").json()["payment_method"] == "CASH"
    assert [payment["amount"] for payment in payment_list] == ["20.00"]
    assert Decimal(str(invoice_after_cash["paid_amount"])) == Decimal("20.00")
    assert Decimal(str(invoice_after_cash["remaining_amount"])) == Decimal("38.00")
    assert invoice_after_cash["payment_status"] == "PARTIALLY_PAID"
    assert second_payment_response.status_code == 201
    assert [payment["amount"] for payment in all_payments] == ["20.00", "38.00"]
    assert Decimal(str(invoice_after_transfer["paid_amount"])) == Decimal("58.00")
    assert Decimal(str(invoice_after_transfer["remaining_amount"])) == Decimal("0.00")
    assert invoice_after_transfer["payment_status"] == "PAID"


def test_payment_validation_update_and_delete(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    missing_invoice = client.post(
        "/payments",
        json={"invoice_id": 999, "amount": "1.00", "payment_date": "2026-08-20", "payment_method": "CASH"},
    )
    zero_amount = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "0.00", "payment_date": "2026-08-20", "payment_method": "CASH"},
    )
    negative_amount = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "-1.00", "payment_date": "2026-08-20", "payment_method": "CASH"},
    )
    overpayment = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "58.01", "payment_date": "2026-08-20", "payment_method": "CASH"},
    )
    payment = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "amount": "20.00", "payment_date": "2026-08-20", "payment_method": "CASH"},
    ).json()
    unknown_field = client.patch(f"/payments/{payment['id']}", json={"unexpected": "value"})
    update_response = client.patch(
        f"/payments/{payment['id']}",
        json={"amount": "30.00", "payment_date": "2026-08-22", "payment_method": "BANK_TRANSFER", "note": "korrigiert"},
    )
    update_overpayment = client.patch(f"/payments/{payment['id']}", json={"amount": "58.01"})
    invoice_after_update = client.get(f"/invoices/{invoice['id']}").json()
    delete_response = client.delete(f"/payments/{payment['id']}")
    invoice_after_delete = client.get(f"/invoices/{invoice['id']}").json()

    assert missing_invoice.status_code == 404
    assert zero_amount.status_code == 422
    assert negative_amount.status_code == 422
    assert overpayment.status_code == 422
    assert unknown_field.status_code == 422
    assert update_response.status_code == 200
    assert update_overpayment.status_code == 422
    assert update_response.json()["payment_method"] == "BANK_TRANSFER"
    assert Decimal(str(invoice_after_update["paid_amount"])) == Decimal("30.00")
    assert Decimal(str(invoice_after_update["remaining_amount"])) == Decimal("28.00")
    assert invoice_after_update["payment_status"] == "PARTIALLY_PAID"
    assert delete_response.status_code == 204
    assert client.get(f"/payments/{payment['id']}").status_code == 404
    assert invoice_after_delete["payment_status"] == "OPEN"
    assert client.get("/invoices/999/payments").status_code == 404
