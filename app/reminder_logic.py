from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Invoice, Reminder, ReminderSetting
from app.invoice_logic import money


ACTIVE_REMINDER_STATUSES = ("DRAFT", "ISSUED")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def get_setting_or_404(db: Session, setting_id: int) -> ReminderSetting:
    setting = db.get(ReminderSetting, setting_id)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder setting not found")
    return setting


def get_reminder_or_404(db: Session, reminder_id: int) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


def validate_setting_sequence_type(sequence: int, reminder_type: str) -> None:
    if sequence == 0 and reminder_type != "PAYMENT_REMINDER":
        raise HTTPException(status_code=422, detail="Sequence 0 must use PAYMENT_REMINDER")
    if sequence > 0 and reminder_type != "REMINDER":
        raise HTTPException(status_code=422, detail="Sequences 1 through 10 must use REMINDER")


def active_reminder_for_stage(db: Session, invoice_id: int, sequence: int) -> Reminder | None:
    statement = (
        select(Reminder)
        .where(
            Reminder.invoice_id == invoice_id,
            Reminder.sequence == sequence,
            Reminder.status.in_(ACTIVE_REMINDER_STATUSES),
        )
        .order_by(Reminder.id.desc())
    )
    return db.scalars(statement).first()


def mark_paid_reminders_for_invoice(db: Session, invoice: Invoice) -> None:
    """Close active reminder workflows once the invoice is fully paid."""
    if invoice.remaining_amount != Decimal("0.00"):
        return
    statement = select(Reminder).where(
        Reminder.invoice_id == invoice.id,
        Reminder.status.in_(ACTIVE_REMINDER_STATUSES),
    )
    for reminder in db.scalars(statement):
        reminder.status = "PAID"


def _eligible_setting_for_invoice(
    db: Session, invoice: Invoice, as_of: date
) -> tuple[ReminderSetting, date] | None:
    if invoice.status != "FINAL" or invoice.remaining_amount <= Decimal("0.00"):
        return None

    reminders = list(
        db.scalars(
            select(Reminder)
            .where(Reminder.invoice_id == invoice.id)
            .order_by(Reminder.sequence, Reminder.id)
        )
    )
    drafts = [reminder for reminder in reminders if reminder.status == "DRAFT"]
    if drafts:
        draft = min(drafts, key=lambda reminder: (reminder.sequence, reminder.id))
        if draft.snoozed_until is not None and as_of < draft.snoozed_until:
            return None
        setting = db.scalar(select(ReminderSetting).where(ReminderSetting.sequence == draft.sequence))
        if setting is None:
            return None
        if draft.sequence == 0:
            return setting, invoice.due_date + timedelta(days=setting.deadline_days)
        previous = next(
            (
                reminder
                for reminder in reminders
                if reminder.sequence == draft.sequence - 1 and reminder.status == "ISSUED"
            ),
            None,
        )
        if previous is None or previous.issued_at is None:
            return None
        return setting, previous.issued_at.date() + timedelta(days=setting.deadline_days)

    issued = [reminder for reminder in reminders if reminder.status == "ISSUED"]
    if not issued:
        setting = db.scalar(
            select(ReminderSetting).where(ReminderSetting.sequence == 0, ReminderSetting.active.is_(True))
        )
        if setting is None:
            return None
        due_date = invoice.due_date + timedelta(days=setting.deadline_days)
        return (setting, due_date) if as_of >= due_date else None

    previous = max(issued, key=lambda reminder: reminder.sequence)
    if previous.snoozed_until is not None and as_of < previous.snoozed_until:
        return None
    next_sequence = previous.sequence + 1
    if next_sequence > 10 or previous.issued_at is None:
        return None
    setting = db.scalar(
        select(ReminderSetting).where(
            ReminderSetting.sequence == next_sequence,
            ReminderSetting.active.is_(True),
        )
    )
    if setting is None:
        return None
    due_date = previous.issued_at.date() + timedelta(days=setting.deadline_days)
    return (setting, due_date) if as_of >= due_date else None


def create_reminder_draft(db: Session, invoice: Invoice, setting: ReminderSetting) -> Reminder:
    if invoice.status != "FINAL":
        raise HTTPException(status_code=422, detail="Reminders require a FINAL invoice")
    if invoice.remaining_amount <= Decimal("0.00"):
        raise HTTPException(status_code=422, detail="Paid invoices cannot receive reminders")
    existing = active_reminder_for_stage(db, invoice.id, setting.sequence)
    if existing is not None:
        return existing
    reminder = Reminder(
        invoice_id=invoice.id,
        sequence=setting.sequence,
        type=setting.type,
        open_amount=money(invoice.remaining_amount),
        reminder_fee=money(Decimal(setting.reminder_fee)),
        postage_fee=money(Decimal(setting.postage_fee)),
        status="DRAFT",
    )
    db.add(reminder)
    db.flush()
    return reminder


def due_reminder_candidates(db: Session, as_of: date) -> list[tuple[Invoice, ReminderSetting, date]]:
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.status == "FINAL")
        .options(selectinload(Invoice.payments))
        .order_by(Invoice.id)
    )
    result: list[tuple[Invoice, ReminderSetting, date]] = []
    for invoice in invoices:
        mark_paid_reminders_for_invoice(db, invoice)
        eligible = _eligible_setting_for_invoice(db, invoice, as_of)
        if eligible is not None:
            setting, due_date = eligible
            result.append((invoice, setting, due_date))
    return result
