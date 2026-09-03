from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Service


def get_active_service_names(db: Session) -> list[str]:
    """Return unique active service names for KI 1's per-request context."""
    names = db.scalars(select(Service.name).where(Service.active.is_(True)).order_by(Service.id))
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        normalized = name.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
