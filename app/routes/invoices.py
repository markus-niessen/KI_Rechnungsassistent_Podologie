from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BusinessProfile, Invoice, InvoiceItem, Patient, Service
from app.db.session import get_db
from app.invoice_logic import calculate_invoice_totals, finalize_invoice, money
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemRead,
    InvoiceItemUpdate,
    InvoiceRead,
    InvoiceUpdate,
)


router = APIRouter(prefix="/invoices", tags=["invoices"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _invoice_statement():
    return select(Invoice).options(
        selectinload(Invoice.business_profile),
        selectinload(Invoice.invoice_items),
    )


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(_invoice_statement().where(Invoice.id == invoice_id))
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def _require_draft(invoice: Invoice) -> None:
    if invoice.status != "DRAFT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only DRAFT invoices can be changed")


def _get_active_business_profile_or_error(db: Session, company_id: int) -> BusinessProfile:
    business_profile = db.get(BusinessProfile, company_id)
    if business_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found")
    if not business_profile.active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Business profile must be active")
    return business_profile


def _set_patient_snapshot(db: Session, item: InvoiceItem, patient_id: int | None) -> None:
    if patient_id is None:
        item.patient_id = None
        item.patient_name_snapshot = None
        return

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    item.patient_id = patient.id
    item.patient_name_snapshot = f"{patient.first_name} {patient.last_name}"


def _set_service_snapshot(db: Session, item: InvoiceItem, service_id: int) -> None:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    item.service_id = service.id
    item.service_name_snapshot = service.name
    item.description = service.name
    item.unit_net_price = service.net_price
    item.vat_rate = service.vat_rate
    item.line_net = money(item.quantity * item.unit_net_price)
    item.line_vat = money(item.line_net * item.vat_rate / 100)
    item.line_gross = money(item.line_net + item.line_vat)


def _recalculate_and_commit(db: Session, invoice: Invoice) -> None:
    db.flush()
    db.refresh(invoice, attribute_names=["invoice_items"])
    calculate_invoice_totals(invoice)
    db.commit()
    db.refresh(invoice, attribute_names=["invoice_items"])


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _has_complete_invoice_address(patient: Patient) -> bool:
    alternative_recipient = (
        patient.invoice_name,
        patient.invoice_street,
        patient.invoice_zip,
        patient.invoice_city,
    )
    if all(_has_text(value) for value in alternative_recipient):
        return True
    return all(_has_text(value) for value in (patient.street, patient.zip, patient.city))


def _validate_invoice_for_finalization(db: Session, invoice: Invoice) -> None:
    if not invoice.invoice_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice must contain at least one item",
        )
    if invoice.business_profile is None or not invoice.business_profile.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice requires an active business profile",
        )
    if invoice.invoice_date is None or invoice.due_date is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice date and due date are required",
        )

    for item in invoice.invoice_items:
        if item.service_id is None or db.get(Service, item.service_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Every invoice item requires a valid service",
            )
        if (
            not _has_text(item.service_name_snapshot)
            or not _has_text(item.description)
            or item.unit_net_price is None
            or item.vat_rate is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Every invoice item requires complete service snapshots",
            )

    if invoice.document_type != "INVOICE":
        return

    patient_ids = {item.patient_id for item in invoice.invoice_items if item.patient_id is not None}
    if invoice.patient_id is not None:
        patient_ids.add(invoice.patient_id)
    if len(patient_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An individual invoice requires exactly one patient recipient",
        )

    patient = db.get(Patient, patient_ids.pop())
    if patient is None or not _has_complete_invoice_address(patient):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An individual invoice requires a complete invoice address",
        )


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(invoice_data: InvoiceCreate, db: DatabaseSession) -> Invoice:
    business_profile = _get_active_business_profile_or_error(db, invoice_data.company_id)
    invoice = Invoice(
        business_profile_id=business_profile.id,
        document_type=invoice_data.document_type,
        status="DRAFT",
        invoice_number=None,
        invoice_date=invoice_data.invoice_date,
        due_date=invoice_data.due_date,
        total_net=money(0),
        total_vat=money(0),
        total_gross=money(0),
    )
    db.add(invoice)
    db.commit()
    return _get_invoice_or_404(db, invoice.id)


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    db: DatabaseSession,
    invoice_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[Invoice]:
    statement = _invoice_statement().order_by(Invoice.id)
    if invoice_status is not None:
        statement = statement.where(Invoice.status == invoice_status)
    return list(db.scalars(statement))


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: DatabaseSession) -> Invoice:
    return _get_invoice_or_404(db, invoice_id)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(invoice_id: int, invoice_data: InvoiceUpdate, db: DatabaseSession) -> Invoice:
    invoice = _get_invoice_or_404(db, invoice_id)
    _require_draft(invoice)
    updates = invoice_data.model_dump(exclude_unset=True)
    if "company_id" in updates:
        invoice.business_profile_id = _get_active_business_profile_or_error(db, updates.pop("company_id")).id
    for field, value in updates.items():
        setattr(invoice, field, value)
    db.commit()
    return _get_invoice_or_404(db, invoice.id)


@router.post("/{invoice_id}/finalize", response_model=InvoiceRead)
def finalize_invoice_endpoint(invoice_id: int, db: DatabaseSession) -> Invoice:
    invoice = _get_invoice_or_404(db, invoice_id)
    _require_draft(invoice)
    _validate_invoice_for_finalization(db, invoice)
    finalize_invoice(db, invoice)
    db.commit()
    return _get_invoice_or_404(db, invoice.id)


@router.get("/{invoice_id}/items", response_model=list[InvoiceItemRead])
def list_invoice_items(invoice_id: int, db: DatabaseSession) -> list[InvoiceItem]:
    return _get_invoice_or_404(db, invoice_id).invoice_items


@router.post("/{invoice_id}/items", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def add_invoice_item(invoice_id: int, item_data: InvoiceItemCreate, db: DatabaseSession) -> Invoice:
    invoice = _get_invoice_or_404(db, invoice_id)
    _require_draft(invoice)
    item = InvoiceItem(invoice=invoice, quantity=item_data.quantity)
    db.add(item)
    with db.no_autoflush:
        _set_service_snapshot(db, item, item_data.service_id)
        _set_patient_snapshot(db, item, item_data.patient_id)
    _recalculate_and_commit(db, invoice)
    return _get_invoice_or_404(db, invoice.id)


def _get_invoice_item_or_404(invoice: Invoice, item_id: int) -> InvoiceItem:
    for item in invoice.invoice_items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")


@router.patch("/{invoice_id}/items/{item_id}", response_model=InvoiceRead)
def update_invoice_item(
    invoice_id: int,
    item_id: int,
    item_data: InvoiceItemUpdate,
    db: DatabaseSession,
) -> Invoice:
    invoice = _get_invoice_or_404(db, invoice_id)
    _require_draft(invoice)
    item = _get_invoice_item_or_404(invoice, item_id)
    updates = item_data.model_dump(exclude_unset=True)
    if "quantity" in updates:
        item.quantity = updates["quantity"]
    if "patient_id" in updates:
        _set_patient_snapshot(db, item, updates["patient_id"])
    if "service_id" in updates:
        _set_service_snapshot(db, item, updates["service_id"])
    elif "quantity" in updates:
        item.line_net = money(item.quantity * item.unit_net_price)
        item.line_vat = money(item.line_net * item.vat_rate / 100)
        item.line_gross = money(item.line_net + item.line_vat)
    _recalculate_and_commit(db, invoice)
    return _get_invoice_or_404(db, invoice.id)


@router.delete("/{invoice_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice_item(invoice_id: int, item_id: int, db: DatabaseSession) -> None:
    invoice = _get_invoice_or_404(db, invoice_id)
    _require_draft(invoice)
    item = _get_invoice_item_or_404(invoice, item_id)
    db.delete(item)
    _recalculate_and_commit(db, invoice)
