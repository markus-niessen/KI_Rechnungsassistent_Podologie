from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ServiceType = Literal["SERVICE", "ADDITIONAL_SERVICE", "PRODUCT"]


class ServiceCreate(BaseModel):
    name: str
    service_type: ServiceType = "SERVICE"
    description: str | None = None
    net_price: Decimal = Field(ge=Decimal("0"))
    vat_rate: Decimal = Field(ge=Decimal("0"))

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty.")
        return value


class ServiceUpdate(BaseModel):
    name: str | None = None
    service_type: ServiceType | None = None
    description: str | None = None
    net_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    vat_rate: Decimal | None = Field(default=None, ge=Decimal("0"))

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty.")
        return value


class ServiceRead(BaseModel):
    id: int
    name: str
    service_type: ServiceType
    description: str | None
    net_price: Decimal
    vat_rate: Decimal
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
