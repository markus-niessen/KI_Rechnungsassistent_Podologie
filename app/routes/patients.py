from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Invoice, InvoiceItem, Patient
from app.db.session import get_db
from app.schemas.patient import PatientCreate, PatientInvoiceRead, PatientRead, PatientUpdate


router = APIRouter(prefix="/patients", tags=["patients"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _next_patient_nr(db: Session) -> str:
    highest_id = db.scalar(select(func.max(Patient.id))) or 0
    return f"P-{highest_id + 1:06d}"


def _get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(patient_data: PatientCreate, db: DatabaseSession) -> Patient:
    patient_values = patient_data.model_dump()
    if not patient_values["deceased"]:
        patient_values["death_date"] = None
    patient = Patient(
        **patient_values,
        patient_nr=_next_patient_nr(db),
        active=not patient_data.deceased,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(
    db: DatabaseSession,
    include_inactive: bool = False,
    search: Annotated[str | None, Query()] = None,
) -> list[Patient]:
    statement = select(Patient).order_by(Patient.id)
    if not include_inactive:
        statement = statement.where(Patient.active.is_(True))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Patient.patient_nr.ilike(pattern),
                Patient.first_name.ilike(pattern),
                Patient.last_name.ilike(pattern),
            )
        )
    return list(db.scalars(statement))


@router.get("/{patient_id}/invoices", response_model=list[PatientInvoiceRead])
def list_patient_invoices(patient_id: int, db: DatabaseSession) -> list[PatientInvoiceRead]:
    _get_patient_or_404(db, patient_id)
    statement = (
        select(Invoice)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .where(InvoiceItem.patient_id == patient_id)
        .options(selectinload(Invoice.invoice_items))
        .distinct()
        .order_by(Invoice.id)
    )
    invoices = db.scalars(statement).unique().all()
    return [
        PatientInvoiceRead(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            document_type=invoice.document_type,
            status=invoice.status,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            subtotal=invoice.total_net,
            tax_total=invoice.total_vat,
            total=invoice.total_gross,
            item_count=len(invoice.invoice_items),
            pdf_available=invoice.status == "FINAL" and invoice.invoice_number is not None,
        )
        for invoice in invoices
    ]


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: int, db: DatabaseSession) -> Patient:
    return _get_patient_or_404(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: int, patient_data: PatientUpdate, db: DatabaseSession) -> Patient:
    patient = _get_patient_or_404(db, patient_id)
    for field, value in patient_data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    if patient.deceased:
        patient.active = False
    else:
        patient.death_date = None
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/deactivate", response_model=PatientRead)
def deactivate_patient(patient_id: int, db: DatabaseSession) -> Patient:
    patient = _get_patient_or_404(db, patient_id)
    patient.active = False
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/activate", response_model=PatientRead)
def activate_patient(patient_id: int, db: DatabaseSession) -> Patient:
    patient = _get_patient_or_404(db, patient_id)
    if patient.deceased:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deceased patient cannot be activated",
        )
    patient.active = True
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: DatabaseSession, confirm: bool = False) -> None:
    patient = _get_patient_or_404(db, patient_id)
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion requires confirm=true")
    if db.scalar(select(Invoice.id).where(Invoice.patient_id == patient.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient cannot be deleted because invoices exist",
        )
    db.delete(patient)
    db.commit()
