from fastapi import APIRouter, HTTPException, status

from app.ai.ki1_extraction import AIConfigurationError, AIExtractionError, extract_treatment_text
from app.schemas.ai import AIExtractRequest


router = APIRouter(prefix="/ai", tags=["ai"])


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
