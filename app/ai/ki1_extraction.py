import json
import logging
import re
from typing import Any

from openai import OpenAI, OpenAIError

from app.ai.prompts import SYSTEM_PROMPT
from app.core.config import get_settings


DEFAULT_KI1_MODEL = "gpt-4.1-mini"
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


def _ki1_model() -> str:
    return getattr(get_settings(), "openai_ki1_model", DEFAULT_KI1_MODEL) or DEFAULT_KI1_MODEL


def _log_usage(response: Any, *, stage: str, model: str) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    logger.info(
        "AI extraction stage completed",
        extra={
            "stage": stage,
            "model": model,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        },
    )


def _run_ki1(input_text: str, *, stage: str, client: OpenAI | None = None) -> dict[str, Any]:
    model = _ki1_model()
    if not input_text.strip():
        raise ValueError("Treatment text must not be empty")
    try:
        response = (client or _get_openai_client()).responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=input_text,
            temperature=0,
        )
    except OpenAIError as error:
        raise AIExtractionError("KI 1 request failed") from error
    _log_usage(response, stage=stage, model=model)
    return _parse_json_output(response.output_text)


def _service_context_input(service_names: list[str] | None) -> str:
    if not service_names:
        return ""
    names = "\n".join(f"- {name}" for name in service_names)
    return (
        "\n\nAktive Leistungen/Produkte aus der Datenbank (nur Bezeichnungen):\n"
        f"{names}\n\n"
        "Prüfe für jede im Originaltext genannte Leistung oder jedes Produkt, ob genau "
        "eine dieser aktiven Bezeichnungen plausibel entspricht. Bei genau einer "
        "plausiblen Zuordnung MUSST du exakt diese Datenbank-Bezeichnung ausgeben. Das "
        "gilt auch für fehlende oder zusätzliche einzelne Wörter, leichte "
        "Schreibvarianten, typische Abkürzungen, kleine Tippfehler und ausgelassene "
        "Produktzusätze. Gibt es mehrere plausible Treffer oder keinen eindeutigen "
        "Treffer, behalte die Originalbezeichnung unverändert bei. Verwende niemals "
        "eine Bezeichnung außerhalb dieser Liste und erfinde keine Leistungen."
    )


_SELF_CORRECTION_PATTERN = re.compile(
    r"(?P<before>[^.!?]+?)\s*(?:,|–|-|\.)\s*"
    r"(?P<marker>ich\s+meine|korrektur\s*:)\s*"
    r"(?:,|–|-)?\s*(?P<after>[^.!?]+)",
    re.IGNORECASE,
)


def _self_correction_input(source_text: str) -> str:
    corrections = list(_SELF_CORRECTION_PATTERN.finditer(source_text))
    if not corrections:
        return ""

    excerpts = "\n".join(
        f'- „{match.group("before").strip()}, {match.group("marker").strip()} '
        f'{match.group("after").strip()}“'
        for match in corrections
    )
    return (
        "\n\nUNMITTELBARE SELBSTKORREKTUREN HABEN VORRANG VOR DEM ERHALT ALTER DATEN. "
        "In den folgenden Originaltextstellen ist die unmittelbar vorhergehende "
        "widersprochene Angabe widerrufen und die Angabe nach dem Marker gültig. "
        "Entferne die widerrufene Angabe aus allen betroffenen Feldern und Positionen; "
        "sie darf weder erhalten noch erneut ergänzt werden. Andere unabhängige "
        "Angaben bleiben erhalten:\n"
        f"{excerpts}"
    )


def extract_treatment_text(
    text: str, client: OpenAI | None = None, service_names: list[str] | None = None
) -> dict[str, Any]:
    """Return KI 1's structured JSON without applying it to application data."""
    return _run_ki1(
        "Strukturiere ausschließlich den folgenden Behandlungs-Text nach den Regeln."
        f"{_service_context_input(service_names)}"
        f"{_self_correction_input(text)}\n\n{text}",
        stage="KI_1",
        client=client,
    )


def correct_treatment_text(
    source_text: str,
    previous_result: dict[str, Any],
    issues: list[dict[str, Any]],
    client: OpenAI | None = None,
    service_names: list[str] | None = None,
) -> dict[str, Any]:
    """Run exactly one KI 1 correction using KI 2's concrete review issues."""
    correction_input = (
        "Prüfe ausschließlich die konkret beanstandeten Stellen erneut. Gib ausschließlich "
        "ein vollständiges, gültiges JSON im bisherigen KI-1-Schema zurück. Verwende nur "
        "Informationen aus dem unveränderten Originaltext und erfinde nichts.\n\n"
        "WICHTIG: Behalte alle bereits korrekten und durch den Originaltext belegten "
        "Informationen unverändert bei. Entferne oder verändere insbesondere keine "
        "Positionen, Mengen oder anderen Felder, sofern sie nicht konkret beanstandet "
        "wurden. Ergänze bei einer beanstandeten Auslassung nur die fehlende Information; "
        "gib danach weiterhin das vollständige Ergebnis aus. Davon ausgenommen sind "
        "unmittelbare Selbstkorrekturen im Originaltext: Die widerrufene Angabe muss "
        "entfernt und darf nicht als geschützte Position erhalten werden.\n\n"
        f"{_self_correction_input(source_text)}\n\n"
        f"Originaltext:\n{source_text}\n\n"
        f"Bisheriges KI-1-Ergebnis:\n{json.dumps(previous_result, ensure_ascii=False)}\n\n"
        f"Konkrete Prüfhinweise von KI-2:\n{json.dumps(issues, ensure_ascii=False)}"
        f"{_service_context_input(service_names)}"
    )
    return _run_ki1(correction_input, stage="KI_1_CORRECTION", client=client)
