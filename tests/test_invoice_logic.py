from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Invoice, InvoiceItem, Patient
from app.invoice_logic import calculate_invoice_totals, confirm_invoice


def test_calculate_invoice_totals_from_multiple_items() -> None:
    invoice = Invoice(
        patient=Patient(patient_number="P-0003", first_name="Lena", last_name="Fischer"),
        invoice_date=date(2026, 8, 19),
        due_date=date(2026, 8, 26),
        status="DRAFT",
        total_net=Decimal("0.00"),
        total_vat=Decimal("0.00"),
        total_gross=Decimal("0.00"),
        invoice_items=[
            InvoiceItem(
                description="Leistung eins",
                quantity=Decimal("1.00"),
                unit_net_price=Decimal("38.00"),
                vat_rate=Decimal("19.00"),
                line_net=Decimal("38.00"),
                line_vat=Decimal("7.22"),
                line_gross=Decimal("45.22"),
            ),
            InvoiceItem(
                description="Leistung zwei",
                quantity=Decimal("1.50"),
                unit_net_price=Decimal("25.33"),
                vat_rate=Decimal("19.00"),
                line_net=Decimal("38.00"),
                line_vat=Decimal("7.22"),
                line_gross=Decimal("45.22"),
            ),
        ],
    )

    calculate_invoice_totals(invoice)

    assert invoice.total_net == Decimal("76.00")
    assert invoice.total_vat == Decimal("14.44")
    assert invoice.total_gross == Decimal("90.44")


def test_confirm_draft_invoice_once_and_protect_totals() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        invoice = Invoice(
            patient=Patient(patient_number="P-0004", first_name="Jan", last_name="Becker"),
            invoice_date=date(2026, 8, 19),
            due_date=date(2026, 8, 26),
            status="DRAFT",
            total_net=Decimal("0.00"),
            total_vat=Decimal("0.00"),
            total_gross=Decimal("0.00"),
            invoice_items=[
                InvoiceItem(
                    description="Leistung",
                    quantity=Decimal("1.00"),
                    unit_net_price=Decimal("38.00"),
                    vat_rate=Decimal("19.00"),
                    line_net=Decimal("38.00"),
                    line_vat=Decimal("7.22"),
                    line_gross=Decimal("45.22"),
                )
            ],
        )
        session.add(invoice)
        session.commit()

        assert invoice.invoice_number is None

        confirm_invoice(invoice)

        assert invoice.invoice_number == f"INV-{invoice.id:06d}"
        assert invoice.status == "CONFIRMED"
        assert invoice.total_net == Decimal("38.00")
        assert invoice.total_vat == Decimal("7.22")
        assert invoice.total_gross == Decimal("45.22")

        with pytest.raises(ValueError):
            confirm_invoice(invoice)
        with pytest.raises(ValueError):
            calculate_invoice_totals(invoice)
