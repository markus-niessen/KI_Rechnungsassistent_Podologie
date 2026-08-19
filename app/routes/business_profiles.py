from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BusinessProfile
from app.db.session import get_db
from app.schemas.business_profile import BusinessProfileCreate, BusinessProfileRead, BusinessProfileUpdate


router = APIRouter(prefix="/business-profiles", tags=["business-profiles"])
DatabaseSession = Annotated[Session, Depends(get_db)]


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
    existing_prefixes = set(db.scalars(select(BusinessProfile.invoice_prefix)))
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
                BusinessProfile.city.ilike(pattern),
            )
        )
    return list(db.scalars(statement))


@router.get("/{business_profile_id}", response_model=BusinessProfileRead)
def get_business_profile(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    return _get_business_profile_or_404(db, business_profile_id)


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
