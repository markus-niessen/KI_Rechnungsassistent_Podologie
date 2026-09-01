from typing import Annotated

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.ki1_extraction import AIConfigurationError, AIExtractionError, extract_treatment_text
from app.ai.ki2_validation import AIValidationError, validate_ki1_result
from app.ai.matching import resolve_validated_case
from app.ai.orchestration import extract_and_validate
from app.db.models import Invoice
from app.db.session import get_db
from app.routes.invoices import add_draft_invoice_item, create_draft_invoice, recalculate_draft_invoice
from app.routes.payments import create_payment_record
from app.schemas.ai import AIDraftCreateRequest, AIExtractRequest, AIReviewResult, AIValidateRequest, AIValidatedExtractionResponse
from app.schemas.invoice import AIDraftCreateResponse, InvoiceCreate, InvoiceItemCreate, InvoiceRead
from app.schemas.payment import PaymentCreate


router = APIRouter(prefix="/ai", tags=["ai"])
DatabaseSession = Annotated[Session, Depends(get_db)]

_DOCUMENT_TYPES = {
    "rechnung": "INVOICE",
    "quittung": "RECEIPT",
    "sammelrechnung": "COLLECTIVE_INVOICE",
}
_PAYMENT_METHODS = {
    "bar": "CASH",
    "ueberweisung": "BANK_TRANSFER",
}


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _document_type_from_ai(structured_data: dict[str, object]) -> str | None:
    document = structured_data.get("dokument")
    if not isinstance(document, dict):
        return None
    return _DOCUMENT_TYPES.get(_normalized_text(document.get("typ")))


def _payment_is_confirmed(source_text: str, payment_method: str) -> bool:
    text = source_text.casefold()
    if payment_method == "CASH":
        return any(
            phrase in text
            for phrase in ("bar bezahlt", "bar gezahlt", "bar erhalten", "in bar bezahlt", "in bar gezahlt")
        )
    return any(
        phrase in text
        for phrase in (
            "überwiesen",
            "ueberwiesen",
            "überweisung erfolgt",
            "ueberweisung erfolgt",
            "per überweisung bezahlt",
            "per ueberweisung bezahlt",
            "zahlung per überweisung",
            "zahlung per ueberweisung",
        )
    )


def _payment_from_ai(
    structured_data: dict[str, object], invoice_id: int, invoice_date: date, source_text: str
) -> tuple[PaymentCreate | None, str | None, str | None]:
    payment = structured_data.get("zahlung")
    if payment in (None, {}):
        return None, None, None
    if not isinstance(payment, dict):
        return None, None, None

    payment_method = _PAYMENT_METHODS.get(_normalized_text(payment.get("zahlungsart")))
    amount = payment.get("betrag")
    payment_status = _normalized_text(payment.get("status"))
    if payment_method is None or amount is None:
        return None, "KI-Zahlungsdaten sind unvollständig; keine Zahlung wurde angelegt.", None
    if not _payment_is_confirmed(source_text, payment_method):
        return None, "KI-Zahlung ist nicht eindeutig als erfolgt erkannt; keine Zahlung wurde angelegt.", None
    payment_date = payment.get("payment_date", payment.get("zahlungsdatum", invoice_date))
    try:
        payment_data = PaymentCreate(
            invoice_id=invoice_id,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
        )
    except ValidationError:
        return None, "KI-Zahlungsdaten sind ungültig; keine Zahlung wurde angelegt.", None

    return payment_data, None, payment_status


def _payment_status_is_consistent(payment_status: str | None, amount: Decimal, total: Decimal) -> bool:
    if payment_status is None:
        return True
    if payment_status == "teilzahlung":
        return amount < total
    if payment_status in {"bezahlt", "vollstaendig", "vollständig"}:
        return amount == total
    return False


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


@router.post("/extract-and-create-draft", response_model=AIDraftCreateResponse, status_code=status.HTTP_201_CREATED)
def extract_and_create_draft(
    draft_request: AIDraftCreateRequest, db: DatabaseSession
) -> AIDraftCreateResponse:
    try:
        ai_result = extract_and_validate(draft_request.text)
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

    structured_data = ai_result.data.get("strukturierte_daten")
    if not isinstance(structured_data, dict) or "faelle" in structured_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI draft creation currently supports one structured case only",
        )

    matching = resolve_validated_case(db, structured_data)
    patient_id = matching.patient.patient_id if matching.patient.status == "matched" else None
    new_patient_data = (
        matching.patient.data.model_dump(mode="json") if matching.patient.status == "new_patient" else None
    )
    unresolved_items = [
        item.model_dump(mode="json") for item in matching.items if item.status != "matched"
    ]
    invoice = create_draft_invoice(
        db,
        InvoiceCreate(
            company_id=draft_request.company_id,
            document_type=_document_type_from_ai(structured_data) or draft_request.document_type,
            invoice_date=draft_request.invoice_date,
            due_date=draft_request.due_date,
        ),
        patient_id=patient_id,
        source_text=ai_result.source_text,
        ai_review_comment=ai_result.ai_review_comment,
        new_patient_data=new_patient_data,
        patient_resolution_required=matching.patient.status == "ambiguous",
        unresolved_items=unresolved_items,
    )
    for item in matching.items:
        if item.status != "matched" or item.service_id is None or item.quantity is None:
            continue
        add_draft_invoice_item(
            db,
            invoice,
            InvoiceItemCreate(
                service_id=item.service_id,
                patient_id=patient_id,
                quantity=item.quantity,
            ),
        )
    recalculate_draft_invoice(db, invoice)
    payment_data, payment_warning, payment_status = _payment_from_ai(
        structured_data, invoice.id, invoice.invoice_date, ai_result.source_text
    )
    if payment_warning is not None:
        matching.warnings.append(payment_warning)
    elif payment_data is not None:
        if not _payment_status_is_consistent(payment_status, payment_data.amount, invoice.total_gross):
            matching.warnings.append("KI-Zahlungsdaten sind widersprüchlich; keine Zahlung wurde angelegt.")
        else:
            try:
                create_payment_record(db, payment_data)
            except HTTPException:
                matching.warnings.append("KI-Zahlung überschreitet den Rechnungsbetrag; keine Zahlung wurde angelegt.")
    db.commit()

    stored_invoice = db.get(Invoice, invoice.id)
    if stored_invoice is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Draft invoice was not saved")
    return AIDraftCreateResponse(invoice=InvoiceRead.model_validate(stored_invoice), matching=matching)


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
