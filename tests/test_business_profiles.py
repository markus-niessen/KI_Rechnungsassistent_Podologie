from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import BusinessProfile, Invoice, InvoicePrefixReservation, Patient
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


def profile_payload(location_code: str | None) -> dict[str, str | None]:
    return {
        "business_name": "Podologie Beispiel",
        "location_name": f"Standort {location_code}",
        "location_code": location_code,
        "street": "Musterstraße 1",
        "postal_code": "50667",
        "city": "Köln",
        "iban": "DE89370400440532013000",
    }


def create_profile(client: TestClient, location_code: str | None) -> dict[str, object]:
    response = client.post("/business-profiles", json=profile_payload(location_code))
    assert response.status_code == 201
    return response.json()


def test_business_profile_can_be_created(client: TestClient) -> None:
    profile = create_profile(client, "NORD")

    assert profile["business_name"] == "Podologie Beispiel"
    assert profile["location_code"] == "NORD"
    assert profile["invoice_prefix"] == "NORD"
    assert profile["active"] is True


@pytest.mark.parametrize("field", ["business_name", "location_name", "iban"])
def test_required_business_profile_fields_are_validated(client: TestClient, field: str) -> None:
    payload = profile_payload("NORD")
    payload[field] = "   "

    response = client.post("/business-profiles", json=payload)

    assert response.status_code == 422


def test_missing_required_business_profile_field_is_rejected(client: TestClient) -> None:
    payload = profile_payload("NORD")
    del payload["iban"]

    response = client.post("/business-profiles", json=payload)

    assert response.status_code == 422


def test_additional_create_field_is_rejected(client: TestClient) -> None:
    payload = profile_payload("NORD")
    payload["invoice_prefix"] = "client-defined"

    response = client.post("/business-profiles", json=payload)

    assert response.status_code == 422


def test_active_business_profiles_can_be_listed_and_searched(client: TestClient) -> None:
    matching_profile = create_profile(client, "NORD")
    second_profile = create_profile(client, "SUED")

    response = client.get("/business-profiles", params={"search": "NORD"})

    assert response.status_code == 200
    assert [profile["id"] for profile in response.json()] == [matching_profile["id"]]
    assert second_profile["location_code"] == "SUED"


def test_business_profile_can_be_retrieved_and_unknown_id_returns_404(client: TestClient) -> None:
    profile = create_profile(client, "NORD")

    response = client.get(f"/business-profiles/{profile['id']}")
    missing_response = client.get("/business-profiles/999")

    assert response.status_code == 200
    assert response.json()["location_code"] == "NORD"
    assert missing_response.status_code == 404


def test_business_profile_can_be_updated_and_protected_fields_are_rejected(client: TestClient) -> None:
    profile = create_profile(client, "NORD")

    response = client.patch(
        f"/business-profiles/{profile['id']}",
        json={"phone": "0221 123456", "bank_name": "Beispielbank"},
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "0221 123456"
    assert response.json()["bank_name"] == "Beispielbank"

    for payload in (
        {"id": 999},
        {"active": False},
        {"created_at": "2026-08-19T00:00:00Z"},
        {"unexpected": "value"},
    ):
        invalid_response = client.patch(f"/business-profiles/{profile['id']}", json=payload)
        assert invalid_response.status_code == 422


def test_business_profile_logo_path_and_updated_at(client: TestClient) -> None:
    payload = profile_payload("NORD")
    payload["logo_path"] = "logos/podologie.png"

    create_response = client.post("/business-profiles", json=payload)
    profile = create_response.json()
    update_response = client.patch(
        f"/business-profiles/{profile['id']}",
        json={"logo_path": "logos/podologie-neu.png"},
    )

    assert create_response.status_code == 201
    assert profile["logo_path"] == "logos/podologie.png"
    assert update_response.status_code == 200
    assert update_response.json()["logo_path"] == "logos/podologie-neu.png"
    assert update_response.json()["updated_at"] != profile["updated_at"]


def test_deactivated_business_profile_is_hidden_unless_requested(client: TestClient) -> None:
    active_profile = create_profile(client, "NORD")
    inactive_profile = create_profile(client, "SUED")

    response = client.post(f"/business-profiles/{inactive_profile['id']}/deactivate")
    default_list = client.get("/business-profiles")
    complete_list = client.get("/business-profiles", params={"include_inactive": "true"})

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert [profile["id"] for profile in default_list.json()] == [active_profile["id"]]
    assert [profile["id"] for profile in complete_list.json()] == [
        active_profile["id"],
        inactive_profile["id"],
    ]


def test_shared_location_codes_receive_stable_non_reused_invoice_prefixes(client: TestClient) -> None:
    first_profile = create_profile(client, "EU")
    second_profile = create_profile(client, "EU")
    third_profile = create_profile(client, "EU")

    assert first_profile["invoice_prefix"] == "EU"
    assert second_profile["invoice_prefix"] == "EU-2"
    assert third_profile["invoice_prefix"] == "EU-3"

    deactivate_response = client.post(f"/business-profiles/{second_profile['id']}/deactivate")
    fourth_profile = create_profile(client, "EU")
    update_response = client.patch(
        f"/business-profiles/{first_profile['id']}",
        json={
            "business_name": "Umbenannte Podologie",
            "street": "Andere Straße 5",
            "location_code": "FR",
        },
    )

    assert deactivate_response.json()["invoice_prefix"] == "EU-2"
    assert fourth_profile["invoice_prefix"] == "EU-4"
    assert update_response.json()["invoice_prefix"] == "EU"
    assert update_response.json()["location_code"] == "FR"


def test_profile_without_location_code_uses_its_id_as_invoice_prefix(client: TestClient) -> None:
    payload = profile_payload(None)
    del payload["location_code"]

    response = client.post("/business-profiles", json=payload)

    assert response.status_code == 201
    profile = response.json()
    assert profile["location_code"] is None
    assert profile["invoice_prefix"] == str(profile["id"])
    with Session(app.state.test_engine) as session:
        assert session.scalar(
            select(InvoicePrefixReservation.invoice_prefix).where(
                InvoicePrefixReservation.invoice_prefix == profile["invoice_prefix"]
            )
        ) == profile["invoice_prefix"]


def test_invoice_prefix_cannot_be_changed_via_patch(client: TestClient) -> None:
    profile = create_profile(client, "EU")

    response = client.patch(f"/business-profiles/{profile['id']}", json={"invoice_prefix": "other"})

    assert response.status_code == 422


def test_business_profile_can_be_reactivated(client: TestClient) -> None:
    profile = create_profile(client, "EU")

    client.post(f"/business-profiles/{profile['id']}/deactivate")
    response = client.post(f"/business-profiles/{profile['id']}/activate")

    assert response.status_code == 200
    assert response.json()["active"] is True
    assert response.json()["invoice_prefix"] == "EU"


def test_deleted_business_profile_keeps_its_invoice_prefix_reservation(client: TestClient) -> None:
    first_profile = create_profile(client, "EU")
    second_profile = create_profile(client, "EU")
    third_profile = create_profile(client, "EU")

    unconfirmed_response = client.delete(f"/business-profiles/{second_profile['id']}")
    confirmed_response = client.delete(
        f"/business-profiles/{second_profile['id']}", params={"confirm": "true"}
    )
    new_profile = create_profile(client, "EU")
    get_response = client.get(f"/business-profiles/{second_profile['id']}")

    assert first_profile["invoice_prefix"] == "EU"
    assert second_profile["invoice_prefix"] == "EU-2"
    assert third_profile["invoice_prefix"] == "EU-3"
    assert unconfirmed_response.status_code == 400
    assert confirmed_response.status_code == 204
    assert get_response.status_code == 404
    assert new_profile["invoice_prefix"] == "EU-4"
    with Session(app.state.test_engine) as session:
        assert session.scalar(
            select(InvoicePrefixReservation.invoice_prefix).where(
                InvoicePrefixReservation.invoice_prefix == "EU-2"
            )
        ) == "EU-2"


def test_invoice_prefix_reservation_is_unique(client: TestClient) -> None:
    profile = create_profile(client, "EU")

    with Session(app.state.test_engine) as session:
        session.add(InvoicePrefixReservation(invoice_prefix=profile["invoice_prefix"]))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_business_profile_with_invoice_cannot_be_hard_deleted(client: TestClient) -> None:
    profile_data = create_profile(client, "EU")
    with Session(app.state.test_engine) as session:
        profile = session.get(BusinessProfile, profile_data["id"])
        patient = Patient(patient_nr="P-000001", first_name="Lena", last_name="Muster")
        session.add(
            Invoice(
                patient=patient,
                business_profile=profile,
                invoice_date=date(2026, 8, 19),
                due_date=date(2026, 8, 26),
                status="DRAFT",
                total_net=Decimal("0.00"),
                total_vat=Decimal("0.00"),
                total_gross=Decimal("0.00"),
            )
        )
        session.commit()

    response = client.delete(f"/business-profiles/{profile_data['id']}", params={"confirm": "true"})

    assert response.status_code == 409
