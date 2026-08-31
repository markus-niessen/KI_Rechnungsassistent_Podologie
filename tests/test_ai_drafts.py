from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Invoice, Patient
from app.db.session import get_db
from app.main import app
from app.schemas.ai import AIReviewResult, AIValidatedExtractionResponse


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


def _business_profile(client: TestClient) -> dict[str, object]:
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


def _patient(client: TestClient, first_name: str = "Peter", last_name: str = "Wagner") -> dict[str, object]:
    response = client.post(
        "/patients",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "street": "Musterweg 1",
            "zip": "50667",
            "city": "Köln",
        },
    )
    assert response.status_code == 201
    return response.json()


def _service(client: TestClient, name: str = "Fußpflege groß", price: str = "58.00") -> dict[str, object]:
    response = client.post(
        "/services",
        json={"name": name, "net_price": price, "vat_rate": "19.00"},
    )
    assert response.status_code == 201
    return response.json()


def _ai_result(text: str, structured_data: dict[str, object]) -> AIValidatedExtractionResponse:
    return AIValidatedExtractionResponse(
        source_text=text,
        data={"original_text": text, "strukturierte_daten": structured_data},
        validation=AIReviewResult(status="ok", issues=[], summary=None),
        correction_attempted=False,
        manual_review_required=False,
        ai_review_comment=None,
    )


def _draft_request(company_id: int, text: str) -> dict[str, object]:
    return {
        "text": text,
        "company_id": company_id,
        "invoice_date": "2026-08-19",
        "due_date": "2026-09-02",
    }


def test_ai_matching_creates_editable_draft_with_existing_patient_and_service(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    patient = _patient(client)
    service = _service(client)
    text = "Peter Wagner, Fußpflege groß zweimal durchgeführt."
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {"vorname": "Peter", "nachname": "Wagner"},
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 2}],
            },
        ),
    )

    response = client.post("/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), text))
    payload = response.json()
    invoice = payload["invoice"]

    assert response.status_code == 201
    assert payload["matching"]["patient"]["status"] == "matched"
    assert invoice["status"] == "DRAFT"
    assert invoice["invoice_number"] is None
    assert invoice["patient_id"] == patient["id"]
    assert invoice["source_text"] == text
    assert invoice["ready_for_finalization"] is True
    assert invoice["unresolved_items"] == []
    assert len(invoice["items"]) == 1
    assert invoice["items"][0]["patient_id"] == patient["id"]
    assert invoice["items"][0]["service_id"] == service["id"]
    assert Decimal(str(invoice["items"][0]["quantity"])) == Decimal("2")
    assert Decimal(str(invoice["items"][0]["unit_price"])) == Decimal("58.00")
    assert Decimal(str(invoice["items"][0]["vat_rate"])) == Decimal("19.00")

    update_response = client.patch(
        f"/invoices/{invoice['id']}/items/{invoice['items'][0]['id']}", json={"quantity": "1.00"}
    )
    assert update_response.status_code == 200
    assert Decimal(str(update_response.json()["items"][0]["quantity"])) == Decimal("1.00")

    finalization = client.post(f"/invoices/{invoice['id']}/finalize")
    assert finalization.status_code == 200
    assert finalization.json()["status"] == "FINAL"
    assert finalization.json()["patient_id"] == patient["id"]
    assert finalization.json()["items"][0]["patient_id"] == patient["id"]


def test_ai_draft_keeps_new_patient_data_without_creating_a_patient(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    _service(client)
    text = "Anna Müller, Fußpflege groß durchgeführt."
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {"vorname": "Anna", "nachname": "Müller"},
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
            },
        ),
    )

    response = client.post("/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), text))
    invoice = response.json()["invoice"]

    assert response.status_code == 201
    assert response.json()["matching"]["patient"]["status"] == "new_patient"
    assert invoice["patient_id"] is None
    assert invoice["new_patient_data"] == {
        "first_name": "Anna",
        "last_name": "Müller",
        "birth_date": None,
        "street": None,
        "zip": None,
        "city": None,
    }
    assert invoice["ready_for_finalization"] is False
    assert invoice["items"][0]["patient_id"] is None
    with Session(app.state.test_engine) as session:
        assert session.scalar(select(func.count(Patient.id))) == 0


def test_ai_draft_creates_new_patient_only_when_finalized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    _service(client)
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {
                    "vorname": "Anna",
                    "nachname": "Müller",
                    "street": "Beispielweg 2",
                    "plz": "50667",
                    "ort": "Köln",
                },
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
            },
        ),
    )

    created = client.post(
        "/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), "Anna Müller")
    ).json()["invoice"]
    with Session(app.state.test_engine) as session:
        assert session.scalar(select(func.count(Patient.id))) == 0

    finalized_response = client.post(f"/invoices/{created['id']}/finalize")
    finalized = finalized_response.json()

    assert finalized_response.status_code == 200
    assert finalized["status"] == "FINAL"
    assert finalized["invoice_number"] == "TEST-RE-2026-000001"
    assert finalized["new_patient_data"] is None
    assert finalized["patient_id"] == finalized["items"][0]["patient_id"]
    with Session(app.state.test_engine) as session:
        patient = session.get(Patient, finalized["patient_id"])
        assert patient is not None
        assert patient.patient_nr == "P-000001"
        assert patient.first_name == "Anna"
        assert patient.last_name == "Müller"
        assert patient.street == "Beispielweg 2"
        assert patient.zip == "50667"
        assert patient.city == "Köln"

    assert client.post(f"/invoices/{created['id']}/finalize").status_code == 409
    with Session(app.state.test_engine) as session:
        assert session.scalar(select(func.count(Patient.id))) == 1


def test_ai_draft_keeps_ambiguous_patient_unresolved_without_assignment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    _patient(client)
    _patient(client)
    _service(client)
    text = "Peter Wagner, Fußpflege groß durchgeführt."
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {"vorname": "Peter", "nachname": "Wagner"},
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
            },
        ),
    )

    response = client.post("/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), text))
    payload = response.json()

    assert response.status_code == 201
    assert payload["matching"]["patient"]["status"] == "ambiguous"
    assert payload["matching"]["patient"]["patient_id"] is None
    assert len(payload["matching"]["patient"]["candidates"]) == 2
    assert payload["invoice"]["patient_id"] is None
    assert payload["invoice"]["patient_resolution_required"] is True
    assert payload["invoice"]["ready_for_finalization"] is False
    assert payload["invoice"]["items"][0]["patient_id"] is None
    finalization = client.post(f"/invoices/{payload['invoice']['id']}/finalize")
    assert finalization.status_code == 422
    assert finalization.json()["detail"] == "Invoice requires an unambiguous patient selection"


@pytest.mark.parametrize("ambiguous", [False, True])
def test_ai_draft_keeps_unresolved_services_without_creating_invoice_items(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, ambiguous: bool
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    _patient(client)
    if ambiguous:
        _service(client, "Mehrarbeit", "5.00")
        _service(client, "Mehrarbeit", "6.00")
        service_name = "Mehrarbeit"
        expected_status = "ambiguous"
    else:
        service_name = "Unbekannte Leistung"
        expected_status = "not_found"
    text = "Peter Wagner, Leistung durchgeführt."
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {"vorname": "Peter", "nachname": "Wagner"},
                "positionen": [{"bezeichnung": service_name, "menge": 1}],
            },
        ),
    )

    response = client.post("/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), text))
    invoice = response.json()["invoice"]

    assert response.status_code == 201
    assert invoice["items"] == []
    assert invoice["unresolved_items"][0]["status"] == expected_status
    assert invoice["ready_for_finalization"] is False
    finalization = client.post(f"/invoices/{invoice['id']}/finalize")
    assert finalization.status_code == 422
    assert finalization.json()["detail"] == "Invoice contains unresolved service items"


def test_new_patient_ai_draft_with_missing_address_cannot_be_finalized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes

    business_profile = _business_profile(client)
    _service(client)
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {"vorname": "Anna", "nachname": "Müller"},
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
            },
        ),
    )

    created = client.post(
        "/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), "Anna Müller")
    ).json()
    finalization = client.post(f"/invoices/{created['invoice']['id']}/finalize")

    assert finalization.status_code == 422
    assert finalization.json()["detail"] == "New patient requires a complete invoice address"
    with Session(app.state.test_engine) as session:
        assert session.scalar(select(func.count(Patient.id))) == 0
        assert session.get(Invoice, created["invoice"]["id"]).invoice_number is None


def test_new_patient_creation_rolls_back_when_finalization_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import ai as ai_routes
    from app.routes import invoices as invoice_routes

    business_profile = _business_profile(client)
    _service(client)
    monkeypatch.setattr(
        ai_routes,
        "extract_and_validate",
        lambda source: _ai_result(
            source,
            {
                "patient": {
                    "vorname": "Anna",
                    "nachname": "Müller",
                    "street": "Beispielweg 2",
                    "plz": "50667",
                    "ort": "Köln",
                },
                "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
            },
        ),
    )
    created = client.post(
        "/ai/extract-and-create-draft", json=_draft_request(int(business_profile["id"]), "Anna Müller")
    ).json()["invoice"]

    def fail_finalization(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated finalization failure")

    monkeypatch.setattr(invoice_routes, "finalize_invoice", fail_finalization)
    with pytest.raises(RuntimeError, match="simulated finalization failure"):
        client.post(f"/invoices/{created['id']}/finalize")

    with Session(app.state.test_engine) as session:
        assert session.scalar(select(func.count(Patient.id))) == 0
        invoice = session.get(Invoice, created["id"])
        assert invoice is not None
        assert invoice.status == "DRAFT"
        assert invoice.invoice_number is None
        assert invoice.patient_id is None
