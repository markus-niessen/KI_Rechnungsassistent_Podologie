from collections.abc import Generator

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


def test_invoice_prefix_cannot_be_changed_via_patch(client: TestClient) -> None:
    profile = create_profile(client, "EU")

    response = client.patch(f"/business-profiles/{profile['id']}", json={"invoice_prefix": "other"})

    assert response.status_code == 422
