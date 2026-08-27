import json
import logging
from typing import Any

from openai import OpenAI, OpenAIError

from app.ai.prompts import SYSTEM_PROMPT
from app.core.config import get_settings


MODEL = "gpt-4.1-mini"
logger = logging.getLogger(__name__)


class AIConfigurationError(Exception):
    """Raised when the OpenAI integration cannot be configured."""


class AIExtractionError(Exception):
    """Raised when KI 1 cannot return a usable extraction."""


def _get_openai_client() -> OpenAI:
    api_key = get_settings().openai_api_key
    if not api_key:
        raise AIConfigurationError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key)


def _parse_json_output(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        result = json.loads(cleaned.strip())
    except json.JSONDecodeError as error:
        raise AIExtractionError("KI 1 returned invalid JSON") from error
    if not isinstance(result, dict):
        raise AIExtractionError("KI 1 returned a JSON value other than an object")
    return result


def _log_usage(response: Any) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    logger.info(
        "KI 1 extraction completed",
        extra={
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        },
    )


def extract_treatment_text(text: str, client: OpenAI | None = None) -> dict[str, Any]:
    """Return KI 1's structured JSON without applying it to application data."""
    if not text.strip():
        raise ValueError("Treatment text must not be empty")
    try:
        response = (client or _get_openai_client()).responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=(
                "Strukturiere ausschließlich den folgenden "
                "Behandlungs-Text nach den Regeln.\n\n"
                f"{text}"
            ),
            temperature=0,
        )
    except OpenAIError as error:
        raise AIExtractionError("KI 1 request failed") from error
    _log_usage(response)
    return _parse_json_output(response.output_text)
