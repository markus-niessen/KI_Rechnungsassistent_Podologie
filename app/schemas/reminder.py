from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


ReminderType = Literal["PAYMENT_REMINDER", "REMINDER"]
ReminderStatus = Literal["DRAFT", "ISSUED", "PAID", "CANCELLED"]


def _validate_sequence_type(sequence: int, reminder_type: ReminderType) -> None:
    if sequence == 0 and reminder_type != "PAYMENT_REMINDER":
        raise ValueError("Sequence 0 must use PAYMENT_REMINDER")
    if sequence > 0 and reminder_type != "REMINDER":
        raise ValueError("Sequences 1 through 10 must use REMINDER")


class ReminderSettingCreate(BaseModel):
    sequence: int = Field(ge=0, le=10)
    type: ReminderType
    deadline_days: int = Field(ge=0)
    reminder_fee: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    postage_fee: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    active: bool = True
    auto_create_draft: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_sequence_type(self) -> "ReminderSettingCreate":
        _validate_sequence_type(self.sequence, self.type)
        return self


class ReminderSettingUpdate(BaseModel):
    sequence: int | None = Field(default=None, ge=0, le=10)
    type: ReminderType | None = None
    deadline_days: int | None = Field(default=None, ge=0)
    reminder_fee: Decimal | None = Field(default=None, ge=Decimal("0"))
    postage_fee: Decimal | None = Field(default=None, ge=Decimal("0"))
    active: bool | None = None
    auto_create_draft: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_update(self) -> "ReminderSettingUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one reminder setting field is required")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class ReminderSettingRead(BaseModel):
    id: int
    sequence: int
    type: ReminderType
    deadline_days: int
    reminder_fee: Decimal
    postage_fee: Decimal
    active: bool
    auto_create_draft: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderCreate(BaseModel):
    invoice_id: int
    sequence: int = Field(ge=0, le=10)

    model_config = ConfigDict(extra="forbid")


class ReminderUpdate(BaseModel):
    snoozed_until: date | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_update(self) -> "ReminderUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one reminder field is required")
        return self


class ReminderSnoozeRequest(BaseModel):
    snoozed_until: date

    model_config = ConfigDict(extra="forbid")


class ReminderRead(BaseModel):
    id: int
    invoice_id: int
    sequence: int
    type: ReminderType
    open_amount: Decimal
    reminder_fee: Decimal
    postage_fee: Decimal
    status: ReminderStatus
    issued_at: datetime | None
    snoozed_until: date | None
    reminder_fee_waived: bool
    postage_fee_waived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=Decimal)
    @property
    def total_due(self) -> Decimal:
        reminder_fee = Decimal("0.00") if self.reminder_fee_waived else self.reminder_fee
        postage_fee = Decimal("0.00") if self.postage_fee_waived else self.postage_fee
        return self.open_amount + reminder_fee + postage_fee


class ReminderDueRead(BaseModel):
    invoice_id: int
    invoice_number: str | None
    sequence: int
    type: ReminderType
    due_date: date
    remaining_amount: Decimal
    reminder: ReminderRead | None = None
    auto_created: bool
