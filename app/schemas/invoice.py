from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DocumentType = Literal["INVOICE", "COLLECTIVE_INVOICE", "RECEIPT"]


class InvoiceCreate(BaseModel):
    company_id: int
    document_type: DocumentType = "INVOICE"
    invoice_date: date
    due_date: date

    model_config = ConfigDict(extra="forbid")


class InvoiceUpdate(BaseModel):
    company_id: int | None = None
    document_type: DocumentType | None = None
    invoice_date: date | None = None
    due_date: date | None = None

    model_config = ConfigDict(extra="forbid")


class InvoiceItemCreate(BaseModel):
    service_id: int
    patient_id: int | None = None
    quantity: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0"))

    model_config = ConfigDict(extra="forbid")


class InvoiceItemUpdate(BaseModel):
    service_id: int | None = None
    patient_id: int | None = None
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))

    model_config = ConfigDict(extra="forbid")


class InvoiceItemRead(BaseModel):
    id: int
    invoice_id: int
    patient_id: int | None
    patient_name_snapshot: str | None
    service_id: int | None
    service_name_snapshot: str | None
    quantity: Decimal
    unit_price: Decimal = Field(validation_alias="unit_net_price")
    vat_rate: Decimal
    line_net: Decimal
    line_vat: Decimal
    line_total: Decimal = Field(validation_alias="line_gross")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvoiceRead(BaseModel):
    id: int
    company_id: int = Field(validation_alias="business_profile_id")
    document_type: str
    status: str
    invoice_number: str | None
    invoice_date: date
    due_date: date
    subtotal: Decimal = Field(validation_alias="total_net")
    tax_total: Decimal = Field(validation_alias="total_vat")
    total: Decimal = Field(validation_alias="total_gross")
    created_at: datetime
    items: list[InvoiceItemRead] = Field(validation_alias="invoice_items")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
