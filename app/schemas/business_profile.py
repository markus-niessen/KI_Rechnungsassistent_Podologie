from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class BusinessProfileCreate(BaseModel):
    business_name: str
    location_name: str
    location_code: str | None = None
    street: str
    postal_code: str
    city: str
    phone: str | None = None
    email: str | None = None
    tax_number: str | None = None
    vat_id: str | None = None
    ik_number: str | None = None
    iban: str
    bic: str | None = None
    bank_name: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("business_name", "location_name", "iban")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field must not be empty.")
        return value

    @field_validator("location_code", mode="before")
    @classmethod
    def normalize_location_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BusinessProfileUpdate(BaseModel):
    business_name: str | None = None
    location_name: str | None = None
    location_code: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    tax_number: str | None = None
    vat_id: str | None = None
    ik_number: str | None = None
    iban: str | None = None
    bic: str | None = None
    bank_name: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("business_name", "location_name", "iban")
    @classmethod
    def validate_required_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Field must not be empty.")
        value = value.strip()
        if not value:
            raise ValueError("Field must not be empty.")
        return value

    @field_validator("location_code", mode="before")
    @classmethod
    def normalize_location_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BusinessProfileRead(BaseModel):
    id: int
    business_name: str
    location_name: str
    location_code: str | None
    invoice_prefix: str
    street: str
    postal_code: str
    city: str
    phone: str | None
    email: str | None
    tax_number: str | None
    vat_id: str | None
    ik_number: str | None
    iban: str
    bic: str | None
    bank_name: str | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
