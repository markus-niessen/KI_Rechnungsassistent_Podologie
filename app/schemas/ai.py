from pydantic import BaseModel, ConfigDict, field_validator


class AIExtractRequest(BaseModel):
    text: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value
