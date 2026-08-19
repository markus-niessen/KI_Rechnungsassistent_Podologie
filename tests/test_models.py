from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Invoice, InvoiceItem, Patient, Payment, Service


def test_core_tables_can_be_created_in_sqlite_memory_db() -> None:
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
            "business_profiles",
            "invoice_prefix_reservations",
            "patients",
        "services",
        "invoices",
        "invoice_items",
        "payments",
    }


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
            invoice_number=None,
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
        assert stored_invoice in stored_invoice.patient.invoices
        assert len(stored_invoice.payments) == 1
        assert stored_invoice.payments[0].amount == Decimal("69.02")


def test_invoice_items_keep_service_snapshot_values() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        patient = Patient(patient_number="P-0002", first_name="Uwe", last_name="Schmidt")
        service = Service(
            name="Fußpflege klein",
            description="Kleine Fußpflege",
            net_price=Decimal("38.00"),
            vat_rate=Decimal("19.00"),
        )
        invoice = Invoice(
            patient=patient,
            invoice_date=date(2026, 8, 19),
            due_date=date(2026, 8, 26),
            status="DRAFT",
            total_net=Decimal("76.00"),
            total_vat=Decimal("14.44"),
            total_gross=Decimal("90.44"),
        )
        first_item = InvoiceItem(
            invoice=invoice,
            service=service,
            description="Fußpflege klein",
            quantity=Decimal("1.00"),
            unit_net_price=Decimal("38.00"),
            vat_rate=Decimal("19.00"),
            line_net=Decimal("38.00"),
            line_vat=Decimal("7.22"),
            line_gross=Decimal("45.22"),
        )
        second_item = InvoiceItem(
            invoice=invoice,
            description="Zusatzleistung",
            quantity=Decimal("1.50"),
            unit_net_price=Decimal("25.33"),
            vat_rate=Decimal("19.00"),
            line_net=Decimal("38.00"),
            line_vat=Decimal("7.22"),
            line_gross=Decimal("45.22"),
        )

        session.add_all([patient, service, invoice, first_item, second_item])
        session.commit()

        service.name = "Fußpflege angepasst"
        service.description = "Angepasste Fußpflege"
        service.net_price = Decimal("42.00")
        service.vat_rate = Decimal("7.00")
        session.commit()
        session.expire_all()

        stored_invoice = session.get(Invoice, invoice.id)
        assert stored_invoice is not None
        assert len(stored_invoice.invoice_items) == 2
        stored_first_item = next(item for item in stored_invoice.invoice_items if item.id == first_item.id)
        assert stored_first_item.service is not None
        assert stored_first_item.service.name == "Fußpflege angepasst"
        assert stored_first_item.service.description == "Angepasste Fußpflege"
        assert stored_first_item.service.net_price == Decimal("42.00")
        assert stored_first_item.service.vat_rate == Decimal("7.00")
        assert stored_first_item.description == "Fußpflege klein"
        assert stored_first_item.unit_net_price == Decimal("38.00")
        assert stored_first_item.vat_rate == Decimal("19.00")
