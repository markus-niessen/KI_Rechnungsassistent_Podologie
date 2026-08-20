from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PaymentMethod = Literal["CASH", "BANK_TRANSFER"]


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: Decimal = Field(gt=Decimal("0"))
    payment_date: date
    payment_method: PaymentMethod
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class PaymentUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    payment_date: date | None = None
    payment_method: PaymentMethod | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_non_null_updates(self) -> "PaymentUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one payment field is required")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None and field_name != "note":
                raise ValueError(f"{field_name} must not be null")
        return self


class PaymentRead(BaseModel):
    id: int
    invoice_id: int
    amount: Decimal
    payment_date: date
    payment_method: PaymentMethod
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
