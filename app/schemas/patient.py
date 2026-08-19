from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None

    model_config = ConfigDict(extra="forbid")


class PatientRead(BaseModel):
    id: int
    patient_number: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    street: str | None
    postal_code: str | None
    city: str | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
