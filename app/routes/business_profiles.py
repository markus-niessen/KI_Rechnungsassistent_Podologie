from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BusinessProfile, Invoice, InvoicePrefixReservation
from app.db.session import get_db
from app.schemas.business_profile import BusinessProfileCreate, BusinessProfileRead, BusinessProfileUpdate


router = APIRouter(prefix="/business-profiles", tags=["business-profiles"])
DatabaseSession = Annotated[Session, Depends(get_db)]
LOGO_DIRECTORY = Path("app/static/images/business_profiles")
MAX_LOGO_BYTES = 5 * 1024 * 1024
ALLOWED_LOGO_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _get_business_profile_or_404(db: Session, business_profile_id: int) -> BusinessProfile:
    business_profile = db.get(BusinessProfile, business_profile_id)
    if business_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found")
    return business_profile


def _next_invoice_prefix(db: Session, business_profile: BusinessProfile) -> str:
    if business_profile.location_code is None:
        if business_profile.id is None:
            raise ValueError("Business profile must be saved before assigning its invoice prefix.")
        return str(business_profile.id)

    location_code = business_profile.location_code
    existing_prefixes = set(db.scalars(select(InvoicePrefixReservation.invoice_prefix)))
    if location_code not in existing_prefixes:
        return location_code

    used_suffixes = [
        int(prefix.removeprefix(f"{location_code}-"))
        for prefix in existing_prefixes
        if prefix.startswith(f"{location_code}-") and prefix.removeprefix(f"{location_code}-").isdigit()
    ]
    return f"{location_code}-{max(used_suffixes, default=1) + 1}"


@router.post("", response_model=BusinessProfileRead, status_code=status.HTTP_201_CREATED)
def create_business_profile(profile_data: BusinessProfileCreate, db: DatabaseSession) -> BusinessProfile:
    for _ in range(5):
        business_profile = BusinessProfile(
            **profile_data.model_dump(),
            invoice_prefix=f"__pending__{uuid4().hex}",
            active=True,
        )
        db.add(business_profile)
        try:
            db.flush()
            business_profile.invoice_prefix = _next_invoice_prefix(db, business_profile)
            db.add(InvoicePrefixReservation(invoice_prefix=business_profile.invoice_prefix))
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(business_profile)
        return business_profile

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not allocate a unique invoice prefix")


@router.get("", response_model=list[BusinessProfileRead])
def list_business_profiles(
    db: DatabaseSession,
    include_inactive: bool = False,
    search: Annotated[str | None, Query()] = None,
) -> list[BusinessProfile]:
    statement = select(BusinessProfile).order_by(BusinessProfile.id)
    if not include_inactive:
        statement = statement.where(BusinessProfile.active.is_(True))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                BusinessProfile.business_name.ilike(pattern),
                BusinessProfile.location_name.ilike(pattern),
                BusinessProfile.location_code.ilike(pattern),
                BusinessProfile.invoice_prefix.ilike(pattern),
                BusinessProfile.street.ilike(pattern),
                BusinessProfile.postal_code.ilike(pattern),
                BusinessProfile.city.ilike(pattern),
                BusinessProfile.phone.ilike(pattern),
                BusinessProfile.email.ilike(pattern),
                BusinessProfile.tax_number.ilike(pattern),
                BusinessProfile.vat_id.ilike(pattern),
                BusinessProfile.ik_number.ilike(pattern),
                BusinessProfile.iban.ilike(pattern),
                BusinessProfile.bic.ilike(pattern),
                BusinessProfile.bank_name.ilike(pattern),
            )
        )
    return list(db.scalars(statement))


@router.get("/{business_profile_id}", response_model=BusinessProfileRead)
def get_business_profile(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    return _get_business_profile_or_404(db, business_profile_id)


@router.post("/{business_profile_id}/logo", response_model=BusinessProfileRead)
async def upload_business_profile_logo(
    business_profile_id: int, logo: Annotated[UploadFile, File()], db: DatabaseSession
) -> BusinessProfile:
    profile = _get_business_profile_or_404(db, business_profile_id)
    extension = ALLOWED_LOGO_TYPES.get(logo.content_type or "")
    if extension is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Logo must be PNG, JPEG or WebP")
    content = await logo.read(MAX_LOGO_BYTES + 1)
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Logo must not exceed 5 MB")
    directory = LOGO_DIRECTORY / str(profile.id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"logo.{extension}"
    (directory / filename).write_bytes(content)
    profile.logo_path = f"/static/images/business_profiles/{profile.id}/{filename}"
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{business_profile_id}/logo", response_model=BusinessProfileRead)
def remove_business_profile_logo(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    profile = _get_business_profile_or_404(db, business_profile_id)
    directory = LOGO_DIRECTORY / str(profile.id)
    for logo_file in directory.glob("logo.*") if directory.exists() else []:
        logo_file.unlink()
    profile.logo_path = None
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/{business_profile_id}", response_model=BusinessProfileRead)
def update_business_profile(
    business_profile_id: int,
    profile_data: BusinessProfileUpdate,
    db: DatabaseSession,
) -> BusinessProfile:
    business_profile = _get_business_profile_or_404(db, business_profile_id)
    for field, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(business_profile, field, value)
    db.commit()
    db.refresh(business_profile)
    return business_profile


@router.post("/{business_profile_id}/deactivate", response_model=BusinessProfileRead)
def deactivate_business_profile(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    business_profile = _get_business_profile_or_404(db, business_profile_id)
    business_profile.active = False
    db.commit()
    db.refresh(business_profile)
    return business_profile


@router.post("/{business_profile_id}/activate", response_model=BusinessProfileRead)
def activate_business_profile(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    business_profile = _get_business_profile_or_404(db, business_profile_id)
    business_profile.active = True
    db.commit()
    db.refresh(business_profile)
    return business_profile


@router.delete("/{business_profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_profile(business_profile_id: int, db: DatabaseSession, confirm: bool = False) -> None:
    business_profile = _get_business_profile_or_404(db, business_profile_id)
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion requires confirm=true")
    if db.scalar(select(Invoice.id).where(Invoice.business_profile_id == business_profile.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Business profile cannot be deleted because invoices exist",
        )
    db.delete(business_profile)
    db.commit()
