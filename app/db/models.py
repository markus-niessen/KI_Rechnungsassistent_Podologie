from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (Index("idx_patients_name", "last_name", "first_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_nr: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deceased: Mapped[bool] = mapped_column(default=False, nullable=False)
    death_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    invoice_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    home_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    invoices: Mapped[list[Invoice]] = relationship(back_populates="patient")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    net_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_prefix: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ik_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    invoices: Mapped[list[Invoice]] = relationship(back_populates="business_profile")


class InvoicePrefixReservation(Base):
    __tablename__ = "invoice_prefix_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_prefix: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    business_profile_id: Mapped[int | None] = mapped_column(ForeignKey("business_profiles.id"), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    total_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="invoices")
    business_profile: Mapped[BusinessProfile | None] = relationship(back_populates="invoices")
    payments: Mapped[list[Payment]] = relationship(back_populates="invoice")
    invoice_items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_net_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    line_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="invoice_items")
    service: Mapped[Service | None] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")
