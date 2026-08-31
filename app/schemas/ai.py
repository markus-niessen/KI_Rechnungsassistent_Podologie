from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIExtractRequest(BaseModel):
    text: str
    invoice_id: int | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value


class AIValidateRequest(BaseModel):
    text: str
    data: dict[str, Any]

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value


class AIDraftCreateRequest(BaseModel):
    text: str
    company_id: int
    invoice_date: date
    due_date: date
    document_type: Literal["INVOICE", "COLLECTIVE_INVOICE", "RECEIPT"] = "INVOICE"

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value


AIReviewStatus = Literal["ok", "correction_required", "manual_review_required"]
AIReviewIssueType = Literal["omission", "invention", "contradiction", "incorrect_value", "ambiguity"]


class AIReviewIssue(BaseModel):
    field: str
    type: AIReviewIssueType
    message: str

    model_config = ConfigDict(extra="forbid")


class AIReviewResult(BaseModel):
    status: AIReviewStatus
    issues: list[AIReviewIssue] = Field(default_factory=list)
    summary: str | None = None

    model_config = ConfigDict(extra="forbid")


class AIValidatedExtractionResponse(BaseModel):
    source_text: str
    data: dict[str, Any]
    validation: AIReviewResult
    correction_attempted: bool
    manual_review_required: bool
    ai_review_comment: str | None

    model_config = ConfigDict(extra="forbid")


MatchStatus = Literal["matched", "not_found", "ambiguous"]
PatientMatchStatus = Literal["matched", "not_found", "ambiguous", "new_patient"]


class PatientMatchCandidate(BaseModel):
    patient_id: int
    patient_nr: str
    first_name: str
    last_name: str
    birth_date: date | None
    city: str | None
    home_name: str | None
    room: str | None


class NewPatientData(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None

    model_config = ConfigDict(extra="forbid")


class PatientCandidateResolution(BaseModel):
    status: PatientMatchStatus
    patient_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    candidates: list[PatientMatchCandidate] = Field(default_factory=list)
    source: Literal["ai_extraction"] | None = None
    data: NewPatientData | None = None
    missing_fields: list[str] = Field(default_factory=list)
    warning: str | None = None


class ServiceMatchCandidate(BaseModel):
    service_id: int
    name: str
    net_price: Decimal
    vat_rate: Decimal


class ServiceCandidateResolution(BaseModel):
    input_name: str
    status: MatchStatus
    service_id: int | None = None
    name: str | None = None
    quantity: Decimal | None = None
    net_price: Decimal | None = None
    vat_rate: Decimal | None = None
    candidates: list[ServiceMatchCandidate] = Field(default_factory=list)


class ValidatedCaseResolution(BaseModel):
    patient: PatientCandidateResolution
    items: list[ServiceCandidateResolution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    all_resolved: bool
