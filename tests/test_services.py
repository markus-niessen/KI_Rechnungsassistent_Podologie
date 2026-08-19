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
from app.schemas.service import ServiceCreate


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


def create_service(client: TestClient, name: str, description: str | None = None) -> dict[str, object]:
    response = client.post(
        "/services",
        json={
            "name": name,
            "description": description,
            "net_price": "38.00",
            "vat_rate": "19.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_service_can_be_created_with_decimal_prices(client: TestClient) -> None:
    service = create_service(client, "Fußpflege klein", "Grundbehandlung")
    schema = ServiceCreate(name="Fußpflege klein", net_price="38.00", vat_rate="19.00")

    assert service["name"] == "Fußpflege klein"
    assert service["net_price"] == "38.00"
    assert service["vat_rate"] == "19.00"
    assert schema.net_price == Decimal("38.00")
    assert schema.vat_rate == Decimal("19.00")


def test_list_shows_active_services_and_searches_case_insensitively(client: TestClient) -> None:
    matching_service = create_service(client, "Fußpflege klein")
    create_service(client, "Mehrarbeit")

    response = client.get("/services", params={"search": "FUßPFLEGE"})

    assert response.status_code == 200
    assert [service["id"] for service in response.json()] == [matching_service["id"]]


def test_service_can_be_retrieved_and_unknown_service_returns_404(client: TestClient) -> None:
    service = create_service(client, "Fußpflege groß")

    response = client.get(f"/services/{service['id']}")
    missing_response = client.get("/services/999")

    assert response.status_code == 200
    assert response.json()["name"] == "Fußpflege groß"
    assert missing_response.status_code == 404


def test_service_can_be_updated_and_rejects_protected_or_extra_fields(client: TestClient) -> None:
    service = create_service(client, "Mehrarbeit")

    response = client.patch(
        f"/services/{service['id']}",
        json={"name": "Mehrarbeit verlängert", "net_price": "5.00", "vat_rate": "7.00"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Mehrarbeit verlängert"
    assert response.json()["net_price"] == "5.00"
    assert response.json()["vat_rate"] == "7.00"

    for payload in (
        {"id": 999},
        {"active": False},
        {"created_at": "2026-08-19T00:00:00Z"},
        {"unexpected": "value"},
    ):
        invalid_response = client.patch(f"/services/{service['id']}", json=payload)
        assert invalid_response.status_code == 422


@pytest.mark.parametrize("field", ["net_price", "vat_rate"])
def test_negative_prices_are_rejected(client: TestClient, field: str) -> None:
    payload = {
        "name": "Ungültige Leistung",
        "net_price": "38.00",
        "vat_rate": "19.00",
    }
    payload[field] = "-1.00"

    response = client.post("/services", json=payload)

    assert response.status_code == 422


def test_deactivated_service_is_hidden_unless_requested(client: TestClient) -> None:
    active_service = create_service(client, "Fußpflege klein")
    inactive_service = create_service(client, "Fußpflege groß")

    response = client.post(f"/services/{inactive_service['id']}/deactivate")
    default_list = client.get("/services")
    complete_list = client.get("/services", params={"include_inactive": "true"})

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert [service["id"] for service in default_list.json()] == [active_service["id"]]
    assert [service["id"] for service in complete_list.json()] == [
        active_service["id"],
        inactive_service["id"],
    ]
