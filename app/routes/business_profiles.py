from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


def _commit_or_location_code_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Location code already exists",
        ) from None


@router.post("", response_model=BusinessProfileRead, status_code=status.HTTP_201_CREATED)
def create_business_profile(profile_data: BusinessProfileCreate, db: DatabaseSession) -> BusinessProfile:
    business_profile = BusinessProfile(**profile_data.model_dump(), active=True)
    db.add(business_profile)
    _commit_or_location_code_conflict(db)
    db.refresh(business_profile)
    return business_profile


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
    _commit_or_location_code_conflict(db)
    db.refresh(business_profile)
    return business_profile


@router.post("/{business_profile_id}/deactivate", response_model=BusinessProfileRead)
def deactivate_business_profile(business_profile_id: int, db: DatabaseSession) -> BusinessProfile:
    business_profile = _get_business_profile_or_404(db, business_profile_id)
    business_profile.active = False
    _commit_or_location_code_conflict(db)
    db.refresh(business_profile)
    return business_profile
