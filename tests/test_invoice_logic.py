from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import BusinessProfile, Invoice, InvoiceItem, Patient
from app.invoice_logic import calculate_invoice_totals, confirm_invoice


def test_calculate_invoice_totals_from_multiple_items() -> None:
    invoice = Invoice(
        patient=Patient(patient_nr="P-0003", first_name="Lena", last_name="Fischer"),
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


def create_business_profile(location_code: str, invoice_prefix: str | None = None) -> BusinessProfile:
    return BusinessProfile(
        business_name="Podologie Beispiel",
        location_name=f"Standort {location_code}",
        location_code=location_code,
        invoice_prefix=invoice_prefix or location_code,
        street="Musterstraße 1",
        postal_code="50667",
        city="Köln",
        iban="DE89370400440532013000",
    )


def create_draft_invoice(
    patient_nr: str,
    invoice_date: date,
    business_profile: BusinessProfile | None = None,
) -> Invoice:
    return Invoice(
        patient=Patient(patient_nr=patient_nr, first_name="Jan", last_name="Becker"),
        business_profile=business_profile,
        invoice_date=invoice_date,
        due_date=invoice_date,
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


def test_draft_invoice_without_business_profile_cannot_be_confirmed() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        invoice = create_draft_invoice("P-0004", date.today())
        session.add(invoice)
        session.commit()

        assert invoice.invoice_number is None

        with pytest.raises(ValueError):
            confirm_invoice(session, invoice)


def test_confirm_invoices_with_location_and_year_sequences() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        invoice_date = date.today()
        eu_profile = create_business_profile("EU")
        fr_profile = create_business_profile("FR")
        eu_first_invoice = create_draft_invoice("P-0005", invoice_date, eu_profile)
        eu_second_invoice = create_draft_invoice("P-0006", invoice_date, eu_profile)
        fr_first_invoice = create_draft_invoice("P-0007", invoice_date, fr_profile)
        session.add_all([eu_profile, fr_profile, eu_first_invoice, eu_second_invoice, fr_first_invoice])
        session.commit()

        assert eu_first_invoice.business_profile_id == eu_profile.id
        assert eu_first_invoice.invoice_number is None

        confirm_invoice(session, eu_first_invoice)
        session.commit()
        confirm_invoice(session, eu_second_invoice)
        session.commit()
        confirm_invoice(session, fr_first_invoice)
        session.commit()

        year = invoice_date.year
        assert eu_first_invoice.invoice_number == f"EU-RE-{year}-000001"
        assert eu_second_invoice.invoice_number == f"EU-RE-{year}-000002"
        assert fr_first_invoice.invoice_number == f"FR-RE-{year}-000001"
        assert len(
            {
                eu_first_invoice.invoice_number,
                eu_second_invoice.invoice_number,
                fr_first_invoice.invoice_number,
            }
        ) == 3
        assert eu_first_invoice.status == "CONFIRMED"
        assert eu_first_invoice.total_net == Decimal("38.00")
        assert eu_first_invoice.total_vat == Decimal("7.22")
        assert eu_first_invoice.total_gross == Decimal("45.22")

        with pytest.raises(ValueError):
            confirm_invoice(session, eu_first_invoice)
        with pytest.raises(ValueError):
            calculate_invoice_totals(eu_first_invoice)


def test_same_location_code_profiles_have_separate_invoice_number_prefixes() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        invoice_date = date.today()
        eu_profile = create_business_profile("EU", "EU")
        eu_second_profile = create_business_profile("EU", "EU-2")
        eu_invoice = create_draft_invoice("P-0008", invoice_date, eu_profile)
        eu_second_invoice = create_draft_invoice("P-0009", invoice_date, eu_second_profile)
        session.add_all([eu_profile, eu_second_profile, eu_invoice, eu_second_invoice])
        session.commit()

        confirm_invoice(session, eu_invoice)
        session.commit()
        confirm_invoice(session, eu_second_invoice)
        session.commit()

        year = invoice_date.year
        assert eu_invoice.invoice_number == f"EU-RE-{year}-000001"
        assert eu_second_invoice.invoice_number == f"EU-2-RE-{year}-000001"
        assert eu_invoice.invoice_number != eu_second_invoice.invoice_number
