from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.ki1_extraction import AIConfigurationError, AIExtractionError, extract_treatment_text
from app.ai.ki2_validation import AIValidationError, validate_ki1_result
from app.ai.orchestration import extract_and_validate
from app.db.models import Invoice
from app.db.session import get_db
from app.schemas.ai import AIExtractRequest, AIReviewResult, AIValidateRequest, AIValidatedExtractionResponse


router = APIRouter(prefix="/ai", tags=["ai"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/extract", response_model=dict)
def extract_text(extraction_request: AIExtractRequest) -> dict:
    try:
        result = extract_treatment_text(extraction_request.text)
    except AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured",
        ) from error
    except AIExtractionError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="KI 1 extraction failed",
        ) from error
    return result


@router.post("/validate", response_model=AIReviewResult)
def validate_text(validation_request: AIValidateRequest) -> AIReviewResult:
    try:
        return validate_ki1_result(validation_request.text, validation_request.data)
    except AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured",
        ) from error
    except AIValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="KI 2 validation failed",
        ) from error


@router.post("/extract-and-validate", response_model=AIValidatedExtractionResponse)
def extract_and_validate_text(
    extraction_request: AIExtractRequest, db: DatabaseSession
) -> AIValidatedExtractionResponse:
    try:
        result = extract_and_validate(extraction_request.text)
    except AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured",
        ) from error
    except (AIExtractionError, AIValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI extraction or validation failed",
        ) from error

    if extraction_request.invoice_id is not None:
        invoice = db.get(Invoice, extraction_request.invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="AI extraction metadata can only be stored on DRAFT invoices",
            )
        invoice.source_text = result.source_text
        invoice.ai_review_comment = result.ai_review_comment
        db.commit()

    return result
