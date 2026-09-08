from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Reminder, ReminderSetting
from app.db.session import get_db
from app.reminder_logic import (
    ACTIVE_REMINDER_STATUSES,
    active_reminder_for_stage,
    create_reminder_draft,
    due_reminder_candidates,
    get_invoice_or_404,
    get_reminder_or_404,
    get_setting_or_404,
    mark_paid_reminders_for_invoice,
    validate_setting_sequence_type,
)
from app.schemas.reminder import (
    ReminderCreate,
    ReminderDueRead,
    ReminderRead,
    ReminderSettingCreate,
    ReminderSettingRead,
    ReminderSettingUpdate,
    ReminderSnoozeRequest,
    ReminderUpdate,
)


router = APIRouter(tags=["reminders"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _commit_or_conflict(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error


def _setting_for_sequence_or_422(db: Session, sequence: int) -> ReminderSetting:
    setting = db.scalar(select(ReminderSetting).where(ReminderSetting.sequence == sequence))
    if setting is None or not setting.active:
        raise HTTPException(status_code=422, detail="No active reminder setting exists for this sequence")
    return setting


def _require_currently_due(db: Session, invoice_id: int, sequence: int) -> ReminderSetting:
    for invoice, setting, _ in due_reminder_candidates(db, date.today()):
        if invoice.id == invoice_id and setting.sequence == sequence:
            return setting
    raise HTTPException(status_code=422, detail="Reminder stage is not due yet")


@router.post("/reminder-settings", response_model=ReminderSettingRead, status_code=status.HTTP_201_CREATED)
def create_reminder_setting(setting_data: ReminderSettingCreate, db: DatabaseSession) -> ReminderSetting:
    setting = ReminderSetting(**setting_data.model_dump())
    db.add(setting)
    _commit_or_conflict(db, "Reminder setting sequence already exists")
    db.refresh(setting)
    return setting


@router.get("/reminder-settings", response_model=list[ReminderSettingRead])
def list_reminder_settings(db: DatabaseSession) -> list[ReminderSetting]:
    return list(db.scalars(select(ReminderSetting).order_by(ReminderSetting.sequence)))


@router.get("/reminder-settings/{setting_id}", response_model=ReminderSettingRead)
def get_reminder_setting(setting_id: int, db: DatabaseSession) -> ReminderSetting:
    return get_setting_or_404(db, setting_id)


@router.patch("/reminder-settings/{setting_id}", response_model=ReminderSettingRead)
def update_reminder_setting(
    setting_id: int, setting_data: ReminderSettingUpdate, db: DatabaseSession
) -> ReminderSetting:
    setting = get_setting_or_404(db, setting_id)
    updates = setting_data.model_dump(exclude_unset=True)
    sequence = updates.get("sequence", setting.sequence)
    reminder_type = updates.get("type", setting.type)
    validate_setting_sequence_type(sequence, reminder_type)
    for field, value in updates.items():
        setattr(setting, field, value)
    _commit_or_conflict(db, "Reminder setting sequence already exists")
    db.refresh(setting)
    return setting


@router.get("/reminders/due", response_model=list[ReminderDueRead])
def list_due_reminders(db: DatabaseSession) -> list[ReminderDueRead]:
    result: list[ReminderDueRead] = []
    for invoice, setting, due_date in due_reminder_candidates(db, date.today()):
        reminder = active_reminder_for_stage(db, invoice.id, setting.sequence)
        auto_created = False
        if reminder is None and setting.auto_create_draft:
            reminder = create_reminder_draft(db, invoice, setting)
            auto_created = True
        result.append(
            ReminderDueRead(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                sequence=setting.sequence,
                type=setting.type,
                due_date=due_date,
                remaining_amount=invoice.remaining_amount,
                reminder=reminder,
                auto_created=auto_created,
            )
        )
    db.commit()
    return result


@router.post("/reminders", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(reminder_data: ReminderCreate, db: DatabaseSession) -> Reminder:
    invoice = get_invoice_or_404(db, reminder_data.invoice_id)
    if active_reminder_for_stage(db, invoice.id, reminder_data.sequence) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active reminder already exists for this invoice and sequence",
        )
    setting = _require_currently_due(db, invoice.id, reminder_data.sequence)
    reminder = create_reminder_draft(db, invoice, setting)
    _commit_or_conflict(db, "An active reminder already exists for this invoice and sequence")
    db.refresh(reminder)
    return reminder


@router.get("/reminders", response_model=list[ReminderRead])
def list_reminders(db: DatabaseSession, invoice_id: int | None = None) -> list[Reminder]:
    statement = select(Reminder).order_by(Reminder.invoice_id, Reminder.sequence, Reminder.id)
    if invoice_id is not None:
        statement = statement.where(Reminder.invoice_id == invoice_id)
    return list(db.scalars(statement))


@router.get("/reminders/{reminder_id}", response_model=ReminderRead)
def get_reminder(reminder_id: int, db: DatabaseSession) -> Reminder:
    return get_reminder_or_404(db, reminder_id)


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
def update_reminder(reminder_id: int, reminder_data: ReminderUpdate, db: DatabaseSession) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise HTTPException(status_code=409, detail="Only active reminders can be updated")
    for field, value in reminder_data.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/reminders/{reminder_id}/issue", response_model=ReminderRead)
def issue_reminder(reminder_id: int, db: DatabaseSession) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    invoice = get_invoice_or_404(db, reminder.invoice_id)
    mark_paid_reminders_for_invoice(db, invoice)
    if reminder.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only DRAFT reminders can be issued")
    if invoice.remaining_amount <= 0:
        raise HTTPException(status_code=422, detail="Paid invoices cannot issue reminders")
    reminder.status = "ISSUED"
    from app.reminder_logic import utc_now

    reminder.issued_at = utc_now()
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/reminders/{reminder_id}/cancel", response_model=ReminderRead)
def cancel_reminder(reminder_id: int, db: DatabaseSession) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise HTTPException(status_code=409, detail="Only active reminders can be cancelled")
    reminder.status = "CANCELLED"
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/reminders/{reminder_id}/waive-fee", response_model=ReminderRead)
def waive_reminder_fee(reminder_id: int, db: DatabaseSession) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise HTTPException(status_code=409, detail="Only active reminders can be changed")
    reminder.reminder_fee_waived = True
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/reminders/{reminder_id}/waive-postage", response_model=ReminderRead)
def waive_postage_fee(reminder_id: int, db: DatabaseSession) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise HTTPException(status_code=409, detail="Only active reminders can be changed")
    reminder.postage_fee_waived = True
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/reminders/{reminder_id}/snooze", response_model=ReminderRead)
def snooze_reminder(
    reminder_id: int, snooze_data: ReminderSnoozeRequest, db: DatabaseSession
) -> Reminder:
    reminder = get_reminder_or_404(db, reminder_id)
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise HTTPException(status_code=409, detail="Only active reminders can be snoozed")
    reminder.snoozed_until = snooze_data.snoozed_until
    db.commit()
    db.refresh(reminder)
    return reminder
