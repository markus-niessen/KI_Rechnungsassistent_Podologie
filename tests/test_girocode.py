from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest

from app.db.models import BusinessProfile, Invoice
from app.girocode import build_epc_girocode_payload, create_girocode_qr_image


def create_final_invoice() -> tuple[Invoice, BusinessProfile]:
    business_profile = BusinessProfile(
        business_name="Podologie Beispiel",
        location_name="Köln",
        location_code="EU",
        invoice_prefix="EU",
        street="Musterstraße 1",
        postal_code="50667",
        city="Köln",
        iban="DE89370400440532013000",
        bic="COBADEFFXXX",
    )
    invoice = Invoice(
        invoice_number="EU-RE-2026-000001",
        invoice_date=date(2026, 8, 20),
        due_date=date(2026, 9, 5),
        status="FINAL",
        total_net=Decimal("38.00"),
        total_vat=Decimal("7.22"),
        total_gross=Decimal("45.22"),
    )
    return invoice, business_profile


def test_epc_girocode_payload_and_qr_image() -> None:
    invoice, business_profile = create_final_invoice()

    payload = build_epc_girocode_payload(invoice, business_profile)
    image_buffer = BytesIO()
    create_girocode_qr_image(payload).save(image_buffer, format="PNG")

    assert payload.splitlines()[:4] == ["BCD", "002", "1", "SCT"]
    assert "DE89370400440532013000" in payload
    assert "EUR45.22" in payload
    assert "Rechnung EU-RE-2026-000001" in payload
    assert "Podologie Beispiel" in payload
    assert image_buffer.getvalue().startswith(b"\x89PNG")
    assert len(image_buffer.getvalue()) > 100


def test_epc_girocode_requires_valid_iban() -> None:
    invoice, business_profile = create_final_invoice()
    business_profile.iban = ""

    with pytest.raises(ValueError, match="IBAN"):
        build_epc_girocode_payload(invoice, business_profile)
