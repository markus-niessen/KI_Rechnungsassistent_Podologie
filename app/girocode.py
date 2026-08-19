from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from app.db.models import BusinessProfile, Invoice


_IBAN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{13,32}$")
_BIC_PATTERN = re.compile(r"^[A-Z0-9]{8}(?:[A-Z0-9]{3})?$")
_MONEY_QUANTUM = Decimal("0.01")


def _single_line(value: str, field_name: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} is required for GiroCode generation.")
    if "\n" in value or "\r" in value or len(value) > max_length:
        raise ValueError(f"{field_name} is invalid for GiroCode generation.")
    return value


def build_epc_girocode_payload(invoice: Invoice, business_profile: BusinessProfile) -> str:
    if invoice.status != "FINAL" or invoice.invoice_number is None:
        raise ValueError("A FINAL invoice with an invoice number is required for GiroCode generation.")

    payee_name = _single_line(business_profile.business_name, "Business name", 70)
    iban = business_profile.iban.replace(" ", "").upper()
    if not _IBAN_PATTERN.fullmatch(iban):
        raise ValueError("A valid IBAN is required for GiroCode generation.")

    bic = (business_profile.bic or "").replace(" ", "").upper()
    if bic and not _BIC_PATTERN.fullmatch(bic):
        raise ValueError("BIC is invalid for GiroCode generation.")

    amount = Decimal(invoice.total_gross).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValueError("A positive total amount is required for GiroCode generation.")

    remittance_information = _single_line(f"Rechnung {invoice.invoice_number}", "Remittance information", 140)
    return "\n".join(
        [
            "BCD",
            "002",
            "1",
            "SCT",
            bic,
            payee_name,
            iban,
            f"EUR{amount:.2f}",
            "",
            "",
            remittance_information,
            "",
        ]
    )


def create_girocode_qr_image(payload: str):
    qr_code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=5, border=4)
    qr_code.add_data(payload)
    qr_code.make(fit=True)
    return qr_code.make_image(fill_color="black", back_color="white").get_image()
