from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invoice


MONEY_QUANTUM = Decimal("0.01")
DOCUMENT_NUMBER_CODES = {
    "INVOICE": "RE",
    "COLLECTIVE_INVOICE": "SR",
    "RECEIPT": "QT",
}


def money(value: Decimal | int) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_invoice_totals(invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be changed.")

    invoice.total_net = money(sum((item.line_net for item in invoice.invoice_items), Decimal("0.00")))
    invoice.total_vat = money(sum((item.line_vat for item in invoice.invoice_items), Decimal("0.00")))
    invoice.total_gross = money(sum((item.line_gross for item in invoice.invoice_items), Decimal("0.00")))


def _next_invoice_number(db: Session, invoice: Invoice) -> str:
    business_profile = invoice.business_profile
    if business_profile is None or business_profile.id is None:
        raise ValueError("Invoice must have a saved business profile.")

    year = invoice.invoice_date.year
    year_start = date(year, 1, 1)
    next_year_start = date(year + 1, 1, 1)
    document_code = DOCUMENT_NUMBER_CODES.get(invoice.document_type)
    if document_code is None:
        raise ValueError("Invoice has an unsupported document type.")
    prefix = f"{business_profile.invoice_prefix}-{document_code}-{year}-"
    existing_numbers = db.scalars(
        select(Invoice.invoice_number).where(
            Invoice.business_profile_id == business_profile.id,
            Invoice.invoice_date >= year_start,
            Invoice.invoice_date < next_year_start,
            Invoice.invoice_number.is_not(None),
        )
    )
    sequence = max(
        (
            int(number.removeprefix(prefix))
            for number in existing_numbers
            if number is not None and number.startswith(prefix) and number.removeprefix(prefix).isdigit()
        ),
        default=0,
    ) + 1
    return f"{prefix}{sequence:06d}"


def finalize_invoice(db: Session, invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be finalized.")
    if invoice.id is None:
        raise ValueError("Invoice must be saved before confirmation.")

    calculate_invoice_totals(invoice)
    invoice.invoice_number = _next_invoice_number(db, invoice)
    invoice.status = "FINAL"


def confirm_invoice(db: Session, invoice: Invoice) -> None:
    """Backward-compatible internal alias for the finalization operation."""
    finalize_invoice(db, invoice)
