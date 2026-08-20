from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import BusinessProfile, Invoice
from app.db.session import get_db
from app import invoice_pdf
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


def create_collective_invoice(client: TestClient, company_id: int) -> dict[str, object]:
    response = client.post(
        "/invoices",
        json={
            "company_id": company_id,
            "document_type": "COLLECTIVE_INVOICE",
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


def test_final_invoice_pdf_is_created_without_changing_invoices(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(invoice_pdf, "INVOICE_PDF_DIRECTORY", tmp_path)
    business_profile = create_business_profile(client)
    service = create_service(client)
    patient = create_billable_patient(client)
    final_invoice = create_invoice(client, business_profile["id"])
    other_draft = create_invoice(client, business_profile["id"])
    client.post(
        f"/invoices/{final_invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"]},
    )
    finalized = client.post(f"/invoices/{final_invoice['id']}/finalize").json()

    pdf_response = client.get(f"/invoices/{final_invoice['id']}/pdf")
    stored_final = client.get(f"/invoices/{final_invoice['id']}").json()
    stored_draft = client.get(f"/invoices/{other_draft['id']}").json()

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF")
    assert len(pdf_response.content) > 500
    assert (tmp_path / "TEST-RE-2026-000001.pdf").read_bytes() == pdf_response.content
    pdf_text = PdfReader(tmp_path / "TEST-RE-2026-000001.pdf").pages[0].extract_text()
    assert "Rechnung" in pdf_text
    assert "Pos." in pdf_text
    assert "Leistung / Produkt" in pdf_text
    assert "Zahlungsinformationen" in pdf_text
    assert "GiroCode" in pdf_text
    assert "Patient" not in pdf_text
    assert stored_final["status"] == "FINAL"
    assert stored_final["invoice_number"] == finalized["invoice_number"]
    assert stored_draft["status"] == "DRAFT"
    assert stored_draft["invoice_number"] is None


def test_invoice_pdf_rejects_drafts_missing_invoices_and_incomplete_final_invoices(
    client: TestClient,
) -> None:
    business_profile = create_business_profile(client)
    draft = create_invoice(client, business_profile["id"])

    assert client.get(f"/invoices/{draft['id']}/pdf").status_code == 409
    assert client.get("/invoices/999/pdf").status_code == 404

    with Session(app.state.test_engine) as session:
        incomplete_final = session.get(Invoice, draft["id"])
        incomplete_final.status = "FINAL"
        session.commit()

    assert client.get(f"/invoices/{draft['id']}/pdf").status_code == 422


def test_invoice_pdf_rejects_missing_iban_without_changing_final_invoice(client: TestClient) -> None:
    business_profile = create_business_profile(client)
    service = create_service(client)
    patient = create_billable_patient(client)
    invoice = create_invoice(client, business_profile["id"])
    client.post(
        f"/invoices/{invoice['id']}/items",
        json={"service_id": service["id"], "patient_id": patient["id"]},
    )
    finalized = client.post(f"/invoices/{invoice['id']}/finalize").json()

    with Session(app.state.test_engine) as session:
        stored_profile = session.get(BusinessProfile, business_profile["id"])
        stored_profile.iban = ""
        session.commit()

    pdf_response = client.get(f"/invoices/{invoice['id']}/pdf")
    stored_invoice = client.get(f"/invoices/{invoice['id']}").json()

    assert pdf_response.status_code == 422
    assert stored_invoice["invoice_number"] == finalized["invoice_number"]
    assert stored_invoice["total"] == finalized["total"]


def test_collective_invoice_finalization_pdf_and_write_protection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(invoice_pdf, "INVOICE_PDF_DIRECTORY", tmp_path)
    business_profile = create_business_profile(client)
    first_service = create_service(client)
    second_service_response = client.post(
        "/services",
        json={"name": "Podologische Zusatzleistung", "net_price": "10.00", "vat_rate": "7.00"},
    )
    common_recipient = {
        "invoice_name": "Pflegeheim Muster",
        "invoice_street": "Rechnungsweg 1",
        "invoice_zip": "50667",
        "invoice_city": "Köln",
    }
    first_patient_response = client.post(
        "/patients", json={"first_name": "Anna", "last_name": "Beispiel", **common_recipient}
    )
    second_patient_response = client.post(
        "/patients", json={"first_name": "Bernd", "last_name": "Beispiel", **common_recipient}
    )
    collective_invoice = create_collective_invoice(client, business_profile["id"])
    draft_pdf_response = client.get(f"/invoices/{collective_invoice['id']}/pdf")
    first_item_response = client.post(
        f"/invoices/{collective_invoice['id']}/items",
        json={"service_id": first_service["id"], "patient_id": first_patient_response.json()["id"], "quantity": "2.00"},
    )
    second_item_response = client.post(
        f"/invoices/{collective_invoice['id']}/items",
        json={"service_id": second_service_response.json()["id"], "patient_id": second_patient_response.json()["id"]},
    )
    draft = client.get(f"/invoices/{collective_invoice['id']}").json()
    finalized_response = client.post(f"/invoices/{collective_invoice['id']}/finalize")
    pdf_response = client.get(f"/invoices/{collective_invoice['id']}/pdf")

    assert draft_pdf_response.status_code == 409
    assert first_item_response.status_code == 201
    assert second_item_response.status_code == 201
    assert draft["status"] == "DRAFT"
    assert [item["patient_name_snapshot"] for item in draft["items"]] == ["Anna Beispiel", "Bernd Beispiel"]
    assert Decimal(str(draft["subtotal"])) == Decimal("86.00")
    assert Decimal(str(draft["tax_total"])) == Decimal("15.14")
    assert Decimal(str(draft["total"])) == Decimal("101.14")
    assert finalized_response.status_code == 200
    finalized = finalized_response.json()
    assert finalized["status"] == "FINAL"
    assert finalized["invoice_number"] == "TEST-RE-2026-000001"
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF")
    assert len(pdf_response.content) > 500
    assert (tmp_path / "TEST-RE-2026-000001.pdf").is_file()
    pdf_text = PdfReader(tmp_path / "TEST-RE-2026-000001.pdf").pages[0].extract_text()
    assert "Sammelrechnung" in pdf_text
    assert "Patient" in pdf_text
    assert "Anna Beispiel" in pdf_text
    assert "Bernd Beispiel" in pdf_text
    assert "GiroCode" in pdf_text
    assert client.patch(
        f"/invoices/{collective_invoice['id']}", json={"due_date": "2026-09-10"}
    ).status_code == 409
    assert client.post(
        f"/invoices/{collective_invoice['id']}/items",
        json={"service_id": first_service["id"], "patient_id": first_patient_response.json()["id"]},
    ).status_code == 409
    assert client.patch(
        f"/invoices/{collective_invoice['id']}/items/{first_item_response.json()['items'][0]['id']}",
        json={"quantity": "1.00"},
    ).status_code == 409
    assert client.delete(
        f"/invoices/{collective_invoice['id']}/items/{second_item_response.json()['items'][1]['id']}"
    ).status_code == 409


def test_large_collective_invoice_pdf_spans_pages_with_repeated_table_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(invoice_pdf, "INVOICE_PDF_DIRECTORY", tmp_path)
    business_profile = create_business_profile(client)
    service = create_service(client)
    common_recipient = {
        "invoice_name": "Pflegeheim Muster",
        "invoice_street": "Rechnungsweg 1",
        "invoice_zip": "50667",
        "invoice_city": "Köln",
    }
    first_patient = client.post(
        "/patients",
        json={
            "first_name": "Alexandra-Maria",
            "last_name": "Beispielname mit längerem Zusatz",
            **common_recipient,
        },
    ).json()
    second_patient = client.post(
        "/patients",
        json={
            "first_name": "Bernhard-Theodor",
            "last_name": "Weiterer Beispielname mit längerem Zusatz",
            **common_recipient,
        },
    ).json()
    invoice = create_collective_invoice(client, business_profile["id"])

    for index in range(30):
        response = client.post(
            f"/invoices/{invoice['id']}/items",
            json={
                "service_id": service["id"],
                "patient_id": (first_patient if index % 2 == 0 else second_patient)["id"],
                "quantity": "1.00",
            },
        )
        assert response.status_code == 201

    finalized = client.post(f"/invoices/{invoice['id']}/finalize").json()
    pdf_response = client.get(f"/invoices/{invoice['id']}/pdf")
    stored = client.get(f"/invoices/{invoice['id']}").json()
    reader = PdfReader(tmp_path / "TEST-RE-2026-000001.pdf")
    page_texts = [page.extract_text() or "" for page in reader.pages]

    assert finalized["status"] == "FINAL"
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")
    assert len(reader.pages) > 1
    assert "Patient" in page_texts[1]
    assert "Leistung" in page_texts[1]
    assert "Sammelrechnung TEST-RE-2026-000001" in page_texts[1]
    assert "Seite 2" in page_texts[1]
    assert Decimal(str(stored["subtotal"])) == Decimal("1140.00")
    assert Decimal(str(stored["tax_total"])) == Decimal("216.60")
    assert Decimal(str(stored["total"])) == Decimal("1356.60")
    assert stored["invoice_number"] == finalized["invoice_number"]


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
