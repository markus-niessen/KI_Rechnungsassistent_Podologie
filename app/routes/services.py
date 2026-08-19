from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import InvoiceItem, Service
from app.db.session import get_db
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate


router = APIRouter(prefix="/services", tags=["services"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _get_service_or_404(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(service_data: ServiceCreate, db: DatabaseSession) -> Service:
    service = Service(**service_data.model_dump(), active=True)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("", response_model=list[ServiceRead])
def list_services(
    db: DatabaseSession,
    include_inactive: bool = False,
    search: Annotated[str | None, Query()] = None,
) -> list[Service]:
    statement = select(Service).order_by(Service.id)
    if not include_inactive:
        statement = statement.where(Service.active.is_(True))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(or_(Service.name.ilike(pattern), Service.description.ilike(pattern)))
    return list(db.scalars(statement))


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: DatabaseSession) -> Service:
    return _get_service_or_404(db, service_id)


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, service_data: ServiceUpdate, db: DatabaseSession) -> Service:
    service = _get_service_or_404(db, service_id)
    for field, value in service_data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service


@router.post("/{service_id}/deactivate", response_model=ServiceRead)
def deactivate_service(service_id: int, db: DatabaseSession) -> Service:
    service = _get_service_or_404(db, service_id)
    service.active = False
    db.commit()
    db.refresh(service)
    return service


@router.post("/{service_id}/activate", response_model=ServiceRead)
def activate_service(service_id: int, db: DatabaseSession) -> Service:
    service = _get_service_or_404(db, service_id)
    service.active = True
    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: DatabaseSession, confirm: bool = False) -> None:
    service = _get_service_or_404(db, service_id)
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion requires confirm=true")
    if db.scalar(select(InvoiceItem.id).where(InvoiceItem.service_id == service.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service cannot be deleted because invoice items exist",
        )
    db.delete(service)
    db.commit()
