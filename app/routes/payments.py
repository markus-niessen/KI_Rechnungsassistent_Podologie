from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Invoice, Payment
from app.db.session import get_db
from app.invoice_logic import money
from app.schemas.payment import PaymentCreate, PaymentRead, PaymentUpdate


router = APIRouter(tags=["payments"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def _get_payment_or_404(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


def _paid_amount(db: Session, invoice_id: int, exclude_payment_id: int | None = None) -> Decimal:
    statement = select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(Payment.invoice_id == invoice_id)
    if exclude_payment_id is not None:
        statement = statement.where(Payment.id != exclude_payment_id)
    return money(Decimal(db.scalar(statement) or "0.00"))


def _validate_payment_total(db: Session, invoice: Invoice, amount: Decimal, exclude_payment_id: int | None = None) -> None:
    new_paid_amount = money(_paid_amount(db, invoice.id, exclude_payment_id) + amount)
    if new_paid_amount > money(Decimal(invoice.total_gross)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Payments must not exceed the invoice total",
        )


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(payment_data: PaymentCreate, db: DatabaseSession) -> Payment:
    invoice = _get_invoice_or_404(db, payment_data.invoice_id)
    _validate_payment_total(db, invoice, payment_data.amount)
    payment = Payment(**payment_data.model_dump())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/payments/{payment_id}", response_model=PaymentRead)
def get_payment(payment_id: int, db: DatabaseSession) -> Payment:
    return _get_payment_or_404(db, payment_id)


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentRead])
def list_invoice_payments(invoice_id: int, db: DatabaseSession) -> list[Payment]:
    _get_invoice_or_404(db, invoice_id)
    statement = select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.payment_date, Payment.id)
    return list(db.scalars(statement))


@router.patch("/payments/{payment_id}", response_model=PaymentRead)
def update_payment(payment_id: int, payment_data: PaymentUpdate, db: DatabaseSession) -> Payment:
    payment = _get_payment_or_404(db, payment_id)
    invoice = _get_invoice_or_404(db, payment.invoice_id)
    updates = payment_data.model_dump(exclude_unset=True)
    amount = updates.get("amount", payment.amount)
    _validate_payment_total(db, invoice, amount, exclude_payment_id=payment.id)
    for field, value in updates.items():
        setattr(payment, field, value)
    db.commit()
    db.refresh(payment)
    return payment


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(payment_id: int, db: DatabaseSession) -> None:
    payment = _get_payment_or_404(db, payment_id)
    db.delete(payment)
    db.commit()
