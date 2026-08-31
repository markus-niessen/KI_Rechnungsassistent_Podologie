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
