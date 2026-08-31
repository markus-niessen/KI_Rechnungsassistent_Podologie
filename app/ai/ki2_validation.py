import json
import logging
from typing import Any

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.ai.ki1_extraction import AIConfigurationError, _get_openai_client
from app.ai.prompts import KI2_SYSTEM_PROMPT
from app.core.config import get_settings
from app.schemas.ai import AIReviewResult


DEFAULT_KI2_MODEL = "gpt-4o-mini"
logger = logging.getLogger(__name__)


class AIValidationError(Exception):
    """Raised when KI 2 cannot return a usable validation."""


def _ki2_model() -> str:
    return getattr(get_settings(), "openai_ki2_model", DEFAULT_KI2_MODEL) or DEFAULT_KI2_MODEL


def _parse_review_output(text: str) -> AIReviewResult:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        result = json.loads(cleaned.strip())
        if isinstance(result, dict) and isinstance(result.get("summary"), str):
            if result["summary"].strip().lower() == "null":
                result["summary"] = None
        return AIReviewResult.model_validate(result)
    except (json.JSONDecodeError, ValidationError) as error:
        raise AIValidationError("KI 2 returned invalid structured validation") from error


def _log_usage(response: Any, *, stage: str, model: str) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    logger.info(
        "AI validation stage completed",
        extra={
            "stage": stage,
            "model": model,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        },
    )


def validate_ki1_result(
    source_text: str,
    extracted_data: dict[str, Any],
    *,
    stage: str = "KI_2",
    client: OpenAI | None = None,
) -> AIReviewResult:
    """Validate KI 1 output against the source text without changing application data."""
    if not source_text.strip():
        raise ValueError("Treatment text must not be empty")
    model = _ki2_model()
    validation_input = (
        "Originaltext (unverändert):\n"
        f"{source_text}\n\n"
        "Strukturierte Ausgabe von KI_1:\n"
        f"{json.dumps(extracted_data, ensure_ascii=False)}"
    )
    try:
        response = (client or _get_openai_client()).responses.create(
            model=model,
            instructions=KI2_SYSTEM_PROMPT,
            input=validation_input,
            temperature=0,
        )
    except OpenAIError as error:
        raise AIValidationError("KI 2 request failed") from error
    _log_usage(response, stage=stage, model=model)
    return _parse_review_output(response.output_text)
