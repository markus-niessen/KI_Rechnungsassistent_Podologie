from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Patient, Service
from app.schemas.ai import (
    PatientCandidateResolution,
    PatientMatchCandidate,
    ServiceCandidateResolution,
    ServiceMatchCandidate,
    ValidatedCaseResolution,
)


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _patient_candidate(patient: Patient) -> PatientMatchCandidate:
    return PatientMatchCandidate(
        patient_id=patient.id,
        patient_nr=patient.patient_nr,
        first_name=patient.first_name,
        last_name=patient.last_name,
        birth_date=patient.birth_date,
        city=patient.city,
        home_name=patient.home_name,
        room=patient.room,
    )


def resolve_patient_candidates(
    db: Session, first_name: str | None, last_name: str | None
) -> PatientCandidateResolution:
    """Return active exact-name patient candidates without selecting an ambiguous patient."""
    first_name = _normalized_text(first_name)
    last_name = _normalized_text(last_name)
    if first_name is None or last_name is None:
        return PatientCandidateResolution(
            status="not_found",
            first_name=first_name,
            last_name=last_name,
        )

    patients = list(
        db.scalars(
            select(Patient)
            .where(
                Patient.active.is_(True),
                func.lower(Patient.first_name) == first_name.lower(),
                func.lower(Patient.last_name) == last_name.lower(),
            )
            .order_by(Patient.id)
        )
    )
    candidates = [_patient_candidate(patient) for patient in patients]
    if len(candidates) == 1:
        candidate = candidates[0]
        return PatientCandidateResolution(
            status="matched",
            patient_id=candidate.patient_id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
        )
    return PatientCandidateResolution(
        status="ambiguous" if candidates else "not_found",
        first_name=first_name,
        last_name=last_name,
        candidates=candidates,
    )


def _service_candidate(service: Service) -> ServiceMatchCandidate:
    return ServiceMatchCandidate(
        service_id=service.id,
        name=service.name,
        net_price=service.net_price,
        vat_rate=service.vat_rate,
    )


def resolve_service_candidates(
    db: Session, name: str | None, quantity: Decimal | None = None
) -> ServiceCandidateResolution:
    """Return active exact-name service candidates without fuzzy or semantic matching."""
    input_name = _normalized_text(name) or ""
    if not input_name:
        return ServiceCandidateResolution(input_name=input_name, status="not_found", quantity=quantity)

    services = list(
        db.scalars(
            select(Service)
            .where(
                Service.active.is_(True),
                func.lower(Service.name) == input_name.lower(),
            )
            .order_by(Service.id)
        )
    )
    candidates = [_service_candidate(service) for service in services]
    if len(candidates) == 1:
        candidate = candidates[0]
        return ServiceCandidateResolution(
            input_name=input_name,
            status="matched",
            service_id=candidate.service_id,
            name=candidate.name,
            quantity=quantity,
            net_price=candidate.net_price,
            vat_rate=candidate.vat_rate,
        )
    return ServiceCandidateResolution(
        input_name=input_name,
        status="ambiguous" if candidates else "not_found",
        quantity=quantity,
        candidates=candidates,
    )


def _quantity(value: Any) -> Decimal | None:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return quantity if quantity > 0 else None


def resolve_validated_case(db: Session, structured_case: dict[str, Any]) -> ValidatedCaseResolution:
    """Resolve one validated KI case to master-data candidates without persisting anything."""
    case = structured_case.get("strukturierte_daten", structured_case)
    if not isinstance(case, dict):
        case = {}

    warnings: list[str] = []
    patient_data = case.get("patient")
    patient_data = patient_data if isinstance(patient_data, dict) else {}
    patient_resolution = resolve_patient_candidates(
        db,
        patient_data.get("vorname"),
        patient_data.get("nachname"),
    )
    if patient_resolution.status == "not_found":
        warnings.append("No active patient matched the extracted first and last name.")
    elif patient_resolution.status == "ambiguous":
        warnings.append("Multiple active patients matched the extracted first and last name.")

    raw_items = case.get("positionen")
    raw_items = raw_items if isinstance(raw_items, list) else []
    item_resolutions: list[ServiceCandidateResolution] = []
    for index, raw_item in enumerate(raw_items, start=1):
        item = raw_item if isinstance(raw_item, dict) else {}
        quantity = _quantity(item.get("menge"))
        item_resolution = resolve_service_candidates(db, item.get("bezeichnung"), quantity)
        item_resolutions.append(item_resolution)
        if quantity is None:
            warnings.append(f"Position {index} has no valid positive quantity.")
        if item_resolution.status == "not_found":
            warnings.append(f"No active service matched position {index}: {item_resolution.input_name!r}.")
        elif item_resolution.status == "ambiguous":
            warnings.append(f"Multiple active services matched position {index}: {item_resolution.input_name!r}.")

    if not raw_items:
        warnings.append("No positions were provided for the validated case.")

    all_resolved = (
        patient_resolution.status == "matched"
        and bool(item_resolutions)
        and all(item.status == "matched" and item.quantity is not None for item in item_resolutions)
    )
    return ValidatedCaseResolution(
        patient=patient_resolution,
        items=item_resolutions,
        warnings=warnings,
        all_resolved=all_resolved,
    )
