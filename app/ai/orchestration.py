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


def extract_and_validate(text: str, client: OpenAI | None = None) -> AIValidatedExtractionResponse:
    """Run KI 1, KI 2, and at most one KI 1 correction followed by one recheck."""
    first_result = extract_treatment_text(text, client=client)
    first_review = validate_ki1_result(text, first_result, stage="KI_2", client=client)
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

    corrected_result = correct_treatment_text(
        text,
        first_result,
        [issue.model_dump() for issue in first_review.issues],
        client=client,
    )
    second_review = validate_ki1_result(text, corrected_result, stage="KI_2_RECHECK", client=client)
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
