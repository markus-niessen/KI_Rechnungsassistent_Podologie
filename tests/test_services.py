from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Invoice, InvoiceItem, Patient, Service
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


def test_service_can_be_reactivated(client: TestClient) -> None:
    service = create_service(client, "Nagelkorrektur")

    client.post(f"/services/{service['id']}/deactivate")
    response = client.post(f"/services/{service['id']}/activate")

    assert response.status_code == 200
    assert response.json()["active"] is True


def test_unused_service_requires_confirmation_before_hard_delete(client: TestClient) -> None:
    service = create_service(client, "Unbenutzte Leistung")

    unconfirmed_response = client.delete(f"/services/{service['id']}")
    confirmed_response = client.delete(f"/services/{service['id']}", params={"confirm": "true"})
    get_response = client.get(f"/services/{service['id']}")

    assert unconfirmed_response.status_code == 400
    assert confirmed_response.status_code == 204
    assert get_response.status_code == 404


def test_service_used_in_invoice_item_cannot_be_hard_deleted(client: TestClient) -> None:
    service_data = create_service(client, "Historische Leistung")
    with Session(app.state.test_engine) as session:
        service = session.get(Service, service_data["id"])
        patient = Patient(patient_nr="P-000001", first_name="Lena", last_name="Muster")
        invoice = Invoice(
            patient=patient,
            invoice_date=date(2026, 8, 19),
            due_date=date(2026, 8, 26),
            status="DRAFT",
            total_net=Decimal("38.00"),
            total_vat=Decimal("7.22"),
            total_gross=Decimal("45.22"),
        )
        session.add(
            InvoiceItem(
                invoice=invoice,
                service=service,
                description="Historische Leistung",
                quantity=Decimal("1.00"),
                unit_net_price=Decimal("38.00"),
                vat_rate=Decimal("19.00"),
                line_net=Decimal("38.00"),
                line_vat=Decimal("7.22"),
                line_gross=Decimal("45.22"),
            )
        )
        session.commit()

    response = client.delete(f"/services/{service_data['id']}", params={"confirm": "true"})

    assert response.status_code == 409
