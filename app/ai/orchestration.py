from copy import deepcopy
import re
from typing import Any

from openai import OpenAI

from app.ai.ki1_extraction import correct_treatment_text, extract_treatment_text
from app.ai.ki2_validation import validate_ki1_result
from app.schemas.ai import AIReviewResult, AIValidatedExtractionResponse


def _manual_review_comment(review: AIReviewResult) -> str:
    detail = review.summary or (review.issues[0].message if review.issues else "Die Extraktion blieb uneindeutig.")
    return (
        "KI-Prüfung erforderlich: "
        f"{detail} Bitte Originaleingabe und extrahierte Daten vor Erstellung der Rechnung prüfen."
    )


def _manual_response(
    source_text: str, data: dict[str, Any], review: AIReviewResult, correction_attempted: bool
) -> AIValidatedExtractionResponse:
    validation = review.model_copy(update={"status": "manual_review_required"})
    return AIValidatedExtractionResponse(
        source_text=source_text,
        data=data,
        validation=validation,
        correction_attempted=correction_attempted,
        manual_review_required=True,
        ai_review_comment=_manual_review_comment(validation),
    )


_SELF_CORRECTION_PATTERN = re.compile(
    r"(?P<before>[^.!?]+?)\s*(?:,|–|-|\.)\s*"
    r"(?:ich\s+meine|korrektur\s*:)\s*(?:,|–|-)?\s*(?P<after>[^.!?]+)",
    re.IGNORECASE,
)


def _revoked_position_names(source_text: str, positions: list[Any]) -> set[str]:
    revoked: set[str] = set()
    for correction in _SELF_CORRECTION_PATTERN.finditer(source_text):
        preceding_text = correction.group("before").casefold()
        for position in positions:
            if not isinstance(position, dict):
                continue
            name = position.get("bezeichnung")
            if isinstance(name, str) and name.casefold() in preceding_text:
                revoked.add(name.casefold())
    return revoked


def _structured_service_names(result: dict[str, Any]) -> set[str]:
    structured_data = result.get("strukturierte_daten")
    if not isinstance(structured_data, dict):
        return set()

    names: set[str] = set()
    treatment = structured_data.get("behandlung")
    if isinstance(treatment, dict) and isinstance(treatment.get("art"), str):
        names.add(treatment["art"].casefold())
    positions = structured_data.get("positionen")
    if isinstance(positions, list):
        for position in positions:
            if isinstance(position, dict) and isinstance(position.get("bezeichnung"), str):
                names.add(position["bezeichnung"].casefold())
    return names


def _self_correction_name_sets(
    source_text: str, previous_result: dict[str, Any], corrected_result: dict[str, Any]
) -> tuple[set[str], set[str]]:
    names = _structured_service_names(previous_result) | _structured_service_names(corrected_result)
    revoked_names: set[str] = set()
    valid_names: set[str] = set()
    for correction in _SELF_CORRECTION_PATTERN.finditer(source_text):
        before = correction.group("before").casefold()
        after = correction.group("after").casefold()
        revoked_names.update(name for name in names if name in before)
        valid_names.update(name for name in names if name in after)
    return revoked_names, valid_names


def _preserve_self_correction_result(
    source_text: str, previous_result: dict[str, Any], corrected_result: dict[str, Any]
) -> dict[str, Any]:
    """Keep a resolved correction from regressing to its withdrawn original value."""
    revoked_names, valid_names = _self_correction_name_sets(source_text, previous_result, corrected_result)
    if not revoked_names or not valid_names:
        return corrected_result

    previous_data = previous_result.get("strukturierte_daten")
    corrected_data = corrected_result.get("strukturierte_daten")
    if not isinstance(previous_data, dict) or not isinstance(corrected_data, dict):
        return corrected_result

    result = deepcopy(corrected_result)
    result_data = result["strukturierte_daten"]
    previous_treatment = previous_data.get("behandlung")
    corrected_treatment = result_data.get("behandlung")
    if (
        isinstance(previous_treatment, dict)
        and isinstance(previous_treatment.get("art"), str)
        and previous_treatment["art"].casefold() in valid_names
        and isinstance(corrected_treatment, dict)
        and isinstance(corrected_treatment.get("art"), str)
        and corrected_treatment["art"].casefold() in revoked_names
    ):
        result_data["behandlung"] = deepcopy(previous_treatment)

    previous_positions = previous_data.get("positionen")
    corrected_positions = result_data.get("positionen")
    if not isinstance(previous_positions, list) or not isinstance(corrected_positions, list):
        return result

    corrected_positions[:] = [
        position
        for position in corrected_positions
        if not (
            isinstance(position, dict)
            and isinstance(position.get("bezeichnung"), str)
            and position["bezeichnung"].casefold() in revoked_names
        )
    ]
    existing_names = {
        position["bezeichnung"].casefold()
        for position in corrected_positions
        if isinstance(position, dict) and isinstance(position.get("bezeichnung"), str)
    }
    for position in previous_positions:
        if not isinstance(position, dict) or not isinstance(position.get("bezeichnung"), str):
            continue
        name = position["bezeichnung"].casefold()
        if name in valid_names and name not in existing_names:
            corrected_positions.append(deepcopy(position))
            existing_names.add(name)
    return result


def _retain_unflagged_positions(
    source_text: str, previous_result: dict[str, Any], corrected_result: dict[str, Any], issues: list[Any]
) -> dict[str, Any]:
    """Keep positions that KI 2 did not explicitly include in a correction issue."""
    previous_data = previous_result.get("strukturierte_daten")
    corrected_data = corrected_result.get("strukturierte_daten")
    if not isinstance(previous_data, dict) or not isinstance(corrected_data, dict):
        return corrected_result
    previous_positions = previous_data.get("positionen")
    corrected_positions = corrected_data.get("positionen")
    if not isinstance(previous_positions, list) or not isinstance(corrected_positions, list):
        return corrected_result

    revoked_names = _revoked_position_names(source_text, previous_positions)

    def restore_missing_positions(result: dict[str, Any], targeted_indexes: set[int]) -> dict[str, Any]:
        retained_positions = result["strukturierte_daten"]["positionen"]
        retained_positions[:] = [
            position
            for position in retained_positions
            if not (
                isinstance(position, dict)
                and isinstance(position.get("bezeichnung"), str)
                and position["bezeichnung"].casefold() in revoked_names
            )
        ]
        for index, position in enumerate(previous_positions):
            if not isinstance(position, dict):
                continue
            name = position.get("bezeichnung")
            if index in targeted_indexes or (isinstance(name, str) and name.casefold() in revoked_names):
                continue
            if position not in retained_positions:
                retained_positions.append(deepcopy(position))
        return result

    position_issues = [issue for issue in issues if "positionen" in issue.field]
    if not position_issues:
        result = deepcopy(corrected_result)
        return restore_missing_positions(result, set())

    targeted_indexes: set[int] = set()
    for issue in position_issues:
        marker = "positionen["
        if marker not in issue.field:
            return corrected_result
        index_text = issue.field.split(marker, 1)[1].split("]", 1)[0]
        if not index_text.isdigit():
            return corrected_result
        targeted_indexes.add(int(index_text))

    result = deepcopy(corrected_result)
    return restore_missing_positions(result, targeted_indexes)


def extract_and_validate(
    text: str, client: OpenAI | None = None, service_names: list[str] | None = None
) -> AIValidatedExtractionResponse:
    """Run KI 1, KI 2, and at most one KI 1 correction followed by one recheck."""
    first_result = extract_treatment_text(text, client=client, service_names=service_names)
    first_review = validate_ki1_result(
        text,
        first_result,
        stage="KI_2",
        client=client,
        service_names=service_names,
    )
    if first_review.status == "ok":
        return AIValidatedExtractionResponse(
            source_text=text,
            data=first_result,
            validation=first_review,
            correction_attempted=False,
            manual_review_required=False,
            ai_review_comment=None,
        )
    if first_review.status == "manual_review_required":
        return _manual_response(text, first_result, first_review, correction_attempted=False)

    correction_issues = [issue.model_dump() for issue in first_review.issues]
    corrected_result = correct_treatment_text(
        text,
        first_result,
        correction_issues,
        client=client,
        service_names=service_names,
    )
    corrected_result = _retain_unflagged_positions(text, first_result, corrected_result, first_review.issues)
    corrected_result = _preserve_self_correction_result(text, first_result, corrected_result)
    second_review = validate_ki1_result(
        text,
        corrected_result,
        stage="KI_2_RECHECK",
        client=client,
        service_names=service_names,
    )
    if second_review.status == "ok":
        return AIValidatedExtractionResponse(
            source_text=text,
            data=corrected_result,
            validation=second_review,
            correction_attempted=True,
            manual_review_required=False,
            ai_review_comment=None,
        )
    return _manual_response(text, corrected_result, second_review, correction_attempted=True)
