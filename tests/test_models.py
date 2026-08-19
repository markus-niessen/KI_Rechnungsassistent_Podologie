from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Invoice, Patient, Payment


def test_core_tables_can_be_created_in_sqlite_memory_db() -> None:
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {"patients", "services", "invoices", "payments"}


def test_patient_invoice_payment_relationship() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        patient = Patient(
            patient_number="P-0001",
            first_name="Erika",
            last_name="Müller",
            date_of_birth=date(1940, 5, 12),
            active=True,
        )
        invoice = Invoice(
            invoice_number="RE-2026-0001",
            patient=patient,
            invoice_date=date(2026, 8, 19),
            due_date=date(2026, 8, 26),
            status="DRAFT",
            total_net=Decimal("58.00"),
            total_vat=Decimal("11.02"),
            total_gross=Decimal("69.02"),
        )
        payment = Payment(
            invoice=invoice,
            amount=Decimal("69.02"),
            payment_date=date(2026, 8, 19),
            payment_method="CASH",
            note="Barzahlung",
        )

        session.add_all([patient, invoice, payment])
        session.commit()
        session.refresh(invoice)

        stored_invoice = session.get(Invoice, invoice.id)
        assert stored_invoice is not None
        assert stored_invoice.patient.patient_number == "P-0001"
        assert len(stored_invoice.payments) == 1
        assert stored_invoice.payments[0].amount == Decimal("69.02")
