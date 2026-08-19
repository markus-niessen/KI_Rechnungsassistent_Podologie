from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    birth_date: date | None = None
    deceased: bool = False
    death_date: date | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    invoice_name: str | None = None
    invoice_street: str | None = None
    invoice_zip: str | None = None
    invoice_city: str | None = None
    home_name: str | None = None
    room: str | None = None

    model_config = ConfigDict(extra="forbid")


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    deceased: bool | None = None
    death_date: date | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    invoice_name: str | None = None
    invoice_street: str | None = None
    invoice_zip: str | None = None
    invoice_city: str | None = None
    home_name: str | None = None
    room: str | None = None

    model_config = ConfigDict(extra="forbid")


class PatientRead(BaseModel):
    id: int
    patient_nr: str
    first_name: str
    last_name: str
    birth_date: date | None
    deceased: bool
    death_date: date | None
    street: str | None
    zip: str | None
    city: str | None
    invoice_name: str | None
    invoice_street: str | None
    invoice_zip: str | None
    invoice_city: str | None
    home_name: str | None
    room: str | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
