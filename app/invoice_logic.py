from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invoice


def calculate_invoice_totals(invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be changed.")

    invoice.total_net = sum((item.line_net for item in invoice.invoice_items), Decimal("0.00"))
    invoice.total_vat = sum((item.line_vat for item in invoice.invoice_items), Decimal("0.00"))
    invoice.total_gross = sum((item.line_gross for item in invoice.invoice_items), Decimal("0.00"))


def _next_invoice_number(db: Session, invoice: Invoice) -> str:
    business_profile = invoice.business_profile
    if business_profile is None or business_profile.id is None:
        raise ValueError("Invoice must have a saved business profile.")

    year = invoice.invoice_date.year
    year_start = date(year, 1, 1)
    next_year_start = date(year + 1, 1, 1)
    prefix = f"{business_profile.invoice_prefix}-RE-{year}-"
    existing_numbers = db.scalars(
        select(Invoice.invoice_number).where(
            Invoice.business_profile_id == business_profile.id,
            Invoice.status == "CONFIRMED",
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


def confirm_invoice(db: Session, invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be confirmed.")
    if invoice.id is None:
        raise ValueError("Invoice must be saved before confirmation.")

    calculate_invoice_totals(invoice)
    invoice.invoice_number = _next_invoice_number(db, invoice)
    invoice.status = "CONFIRMED"
