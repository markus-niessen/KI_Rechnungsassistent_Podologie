from decimal import Decimal

from app.db.models import Invoice


def calculate_invoice_totals(invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be changed.")

    invoice.total_net = sum((item.line_net for item in invoice.invoice_items), Decimal("0.00"))
    invoice.total_vat = sum((item.line_vat for item in invoice.invoice_items), Decimal("0.00"))
    invoice.total_gross = sum((item.line_gross for item in invoice.invoice_items), Decimal("0.00"))


def confirm_invoice(invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise ValueError("Only DRAFT invoices can be confirmed.")
    if invoice.id is None:
        raise ValueError("Invoice must be saved before confirmation.")

    calculate_invoice_totals(invoice)
    invoice.invoice_number = f"INV-{invoice.id:06d}"
    invoice.status = "CONFIRMED"
