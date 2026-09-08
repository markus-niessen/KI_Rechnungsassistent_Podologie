from collections.abc import Generator
from datetime import date, timedelta
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

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)


def create_final_invoice(client: TestClient) -> dict[str, object]:
    business_profile = client.post(
        "/business-profiles",
        json={
            "business_name": "Podologie Beispielpraxis",
            "location_name": "Köln",
            "location_code": "TEST",
            "street": "Musterstraße 1",
            "postal_code": "50667",
            "city": "Köln",
            "iban": "DE89370400440532013000",
        },
    ).json()
    service = client.post(
        "/services", json={"name": "Behandlung", "net_price": "48.74", "vat_rate": "19.00"}
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
        json={
            "company_id": business_profile["id"],
            "invoice_date": str(date.today() - timedelta(days=30)),
            "due_date": str(date.today() - timedelta(days=10)),
        },
    ).json()
    assert client.post(
        f"/invoices/{invoice['id']}/items", json={"service_id": service["id"], "patient_id": patient["id"]}
    ).status_code == 201
    finalized = client.post(f"/invoices/{invoice['id']}/finalize")
    assert finalized.status_code == 200
    return finalized.json()


def create_setting(client: TestClient, sequence: int, *, auto: bool = False, deadline_days: int = 0) -> dict[str, object]:
    return client.post(
        "/reminder-settings",
        json={
            "sequence": sequence,
            "type": "PAYMENT_REMINDER" if sequence == 0 else "REMINDER",
            "deadline_days": deadline_days,
            "reminder_fee": "2.50",
            "postage_fee": "0.95",
            "auto_create_draft": auto,
        },
    ).json()


def test_reminder_setting_crud_and_sequence_validation(client: TestClient) -> None:
    invalid = client.post(
        "/reminder-settings", json={"sequence": 0, "type": "REMINDER", "deadline_days": 1}
    )
    setting = create_setting(client, 0)
    duplicate = client.post(
        "/reminder-settings",
        json={"sequence": 0, "type": "PAYMENT_REMINDER", "deadline_days": 1},
    )
    updated = client.patch(f"/reminder-settings/{setting['id']}", json={"reminder_fee": "4.00"})
    stage_one = create_setting(client, 1)
    partial_update = client.patch(f"/reminder-settings/{stage_one['id']}", json={"deadline_days": 7})

    assert invalid.status_code == 422
    assert duplicate.status_code == 409
    assert client.get("/reminder-settings").status_code == 200
    assert updated.status_code == 200
    assert updated.json()["reminder_fee"] == "4.00"
    assert partial_update.status_code == 200
    assert partial_update.json()["type"] == "REMINDER"
    assert partial_update.json()["deadline_days"] == 7
    assert client.patch(f"/reminder-settings/{setting['id']}", json={"unknown": True}).status_code == 422


def test_due_stage_zero_auto_creates_exactly_one_draft_with_partial_payment_snapshot(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    create_setting(client, 0, auto=True)
    payment = client.post(
        "/payments",
        json={
            "invoice_id": invoice["id"],
            "amount": "20.00",
            "payment_date": str(date.today()),
            "payment_method": "CASH",
        },
    )
    first_due = client.get("/reminders/due")
    second_due = client.get("/reminders/due")
    reminders = client.get(f"/reminders?invoice_id={invoice['id']}").json()

    assert payment.status_code == 201
    assert first_due.status_code == 200
    assert first_due.json()[0]["sequence"] == 0
    assert first_due.json()[0]["auto_created"] is True
    assert first_due.json()[0]["reminder"]["status"] == "DRAFT"
    assert Decimal(first_due.json()[0]["reminder"]["open_amount"]) == Decimal("38.00")
    assert second_due.status_code == 200
    assert len(second_due.json()) == 1
    assert second_due.json()[0]["reminder"]["id"] == first_due.json()[0]["reminder"]["id"]
    assert second_due.json()[0]["auto_created"] is False
    assert len(reminders) == 1
    assert reminders[0]["status"] == "DRAFT"


def test_snoozed_draft_is_hidden_from_due_list_until_its_snooze_expires(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    create_setting(client, 0, auto=True)
    due = client.get("/reminders/due").json()
    reminder_id = due[0]["reminder"]["id"]

    assert client.post(
        f"/reminders/{reminder_id}/snooze", json={"snoozed_until": str(date.today() + timedelta(days=1))}
    ).status_code == 200
    assert client.get("/reminders/due").json() == []


def test_reminder_issue_enables_next_stage_only_after_issued_stage_deadline(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    create_setting(client, 0, auto=False)
    create_setting(client, 1, auto=True)

    first_due = client.get("/reminders/due").json()
    draft = client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 0})
    blocked_next = client.get("/reminders/due").json()
    issued = client.post(f"/reminders/{draft.json()['id']}/issue")
    next_due = client.get("/reminders/due").json()

    assert first_due[0]["sequence"] == 0
    assert draft.status_code == 201
    assert len(blocked_next) == 1
    assert blocked_next[0]["sequence"] == 0
    assert blocked_next[0]["reminder"]["id"] == draft.json()["id"]
    assert issued.status_code == 200
    assert issued.json()["status"] == "ISSUED"
    assert issued.json()["issued_at"] is not None
    assert next_due[0]["sequence"] == 1
    assert next_due[0]["reminder"]["status"] == "DRAFT"
    assert client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 1}).status_code == 409


def test_reminder_lifecycle_actions_and_paid_status(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    create_setting(client, 0)
    reminder = client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 0}).json()

    snoozed = client.post(
        f"/reminders/{reminder['id']}/snooze", json={"snoozed_until": str(date.today() + timedelta(days=5))}
    )
    waived_fee = client.post(f"/reminders/{reminder['id']}/waive-fee")
    waived_postage = client.post(f"/reminders/{reminder['id']}/waive-postage")
    issued = client.post(f"/reminders/{reminder['id']}/issue")
    payment = client.post(
        "/payments",
        json={
            "invoice_id": invoice["id"],
            "amount": "58.00",
            "payment_date": str(date.today()),
            "payment_method": "BANK_TRANSFER",
        },
    )
    stored = client.get(f"/reminders/{reminder['id']}")

    assert snoozed.status_code == 200
    assert waived_fee.json()["reminder_fee_waived"] is True
    assert waived_postage.json()["postage_fee_waived"] is True
    assert waived_postage.json()["total_due"] == "58.00"
    assert issued.status_code == 200
    assert payment.status_code == 201
    assert stored.json()["status"] == "PAID"
    assert client.post(f"/reminders/{reminder['id']}/cancel").status_code == 409
    waive_after_paid = client.post(f"/reminders/{reminder['id']}/waive-fee")
    assert waive_after_paid.status_code == 409
    assert waive_after_paid.json()["detail"] == "Only active reminders can be changed"


def test_cancelled_stage_can_be_recreated_but_paid_invoice_cannot(client: TestClient) -> None:
    invoice = create_final_invoice(client)
    create_setting(client, 0)
    first = client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 0}).json()
    assert client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 0}).status_code == 409
    assert client.post(f"/reminders/{first['id']}/cancel").status_code == 200
    second = client.post("/reminders", json={"invoice_id": invoice["id"], "sequence": 0})
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]

    assert client.post(
        "/payments",
        json={
            "invoice_id": invoice["id"],
            "amount": "58.00",
            "payment_date": str(date.today()),
            "payment_method": "CASH",
        },
    ).status_code == 201
    assert client.get("/reminders/due").json() == []
