from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Patient, Service
from app.schemas.ai import (
    NewPatientData,
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


def _extracted_value(data: dict[str, Any], *field_names: str) -> Any:
    for field_name in field_names:
        if field_name not in data or data[field_name] is None:
            continue
        value = data[field_name]
        if isinstance(value, str):
            value = _normalized_text(value)
        if value is not None:
            return value
    return None


def _new_patient_resolution(patient_data: dict[str, Any]) -> PatientCandidateResolution:
    data = NewPatientData(
        first_name=_extracted_value(patient_data, "vorname", "first_name"),
        last_name=_extracted_value(patient_data, "nachname", "last_name"),
        birth_date=_extracted_value(patient_data, "birth_date", "geburtsdatum"),
        street=_extracted_value(patient_data, "street", "strasse", "straße"),
        zip=_extracted_value(patient_data, "zip", "plz", "postal_code"),
        city=_extracted_value(patient_data, "city", "ort"),
    )
    missing_fields = [
        field_name
        for field_name in ("birth_date", "street", "zip", "city")
        if getattr(data, field_name) is None
    ]
    return PatientCandidateResolution(
        status="new_patient",
        first_name=data.first_name,
        last_name=data.last_name,
        source="ai_extraction",
        data=data,
        missing_fields=missing_fields,
        warning="Kein aktiver Patient in der Datenbank gefunden. Patient kann neu angelegt werden.",
    )


def _patient_candidate(patient: Patient) -> PatientMatchCandidate:
    return PatientMatchCandidate(
        patient_id=patient.id,
        patient_nr=patient.patient_nr,
        first_name=patient.first_name,
        last_name=patient.last_name,
        birth_date=patient.birth_date,
        street=patient.street,
        zip=patient.zip,
        city=patient.city,
        home_name=patient.home_name,
        room=patient.room,
        active=patient.active,
        deceased=patient.deceased,
        death_date=patient.death_date,
    )


def _patient_candidates(db: Session, first_name: str | None, last_name: str, *, active: bool) -> list[PatientMatchCandidate]:
    statement = select(Patient).where(
        Patient.active.is_(active),
        func.lower(Patient.last_name) == last_name.lower(),
    )
    if first_name is not None:
        statement = statement.where(func.lower(Patient.first_name) == first_name.lower())
    patients = list(db.scalars(statement.order_by(Patient.id)))
    return [_patient_candidate(patient) for patient in patients]


def _inactive_patient_status(candidates: list[PatientMatchCandidate]) -> str:
    if len(candidates) != 1:
        return "ambiguous"
    return "deceased" if candidates[0].deceased else "inactive"


def resolve_patient_candidates(
    db: Session, first_name: str | None, last_name: str | None
) -> PatientCandidateResolution:
    """Search active patients first and never auto-select inactive or incomplete-name candidates."""
    first_name = _normalized_text(first_name)
    last_name = _normalized_text(last_name)
    if last_name is None:
        return PatientCandidateResolution(
            status="not_found",
            first_name=first_name,
            last_name=last_name,
        )

    active_candidates = _patient_candidates(db, first_name, last_name, active=True)
    if first_name is not None and len(active_candidates) == 1:
        candidate = active_candidates[0]
        return PatientCandidateResolution(
            status="matched",
            patient_id=candidate.patient_id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
        )
    if active_candidates:
        return PatientCandidateResolution(
            status="ambiguous",
            first_name=first_name,
            last_name=last_name,
            candidates=active_candidates,
        )

    inactive_candidates = _patient_candidates(db, first_name, last_name, active=False)
    if inactive_candidates:
        return PatientCandidateResolution(
            status=_inactive_patient_status(inactive_candidates),
            first_name=first_name,
            last_name=last_name,
            candidates=inactive_candidates,
        )
    return PatientCandidateResolution(
        status="not_found",
        first_name=first_name,
        last_name=last_name,
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
    extracted_first_name = _extracted_value(patient_data, "vorname", "first_name")
    extracted_last_name = _extracted_value(patient_data, "nachname", "last_name")
    patient_resolution = resolve_patient_candidates(
        db,
        extracted_first_name,
        extracted_last_name,
    )
    if patient_resolution.status == "not_found":
        if patient_resolution.first_name is not None and patient_resolution.last_name is not None:
            patient_resolution = _new_patient_resolution(patient_data)
            warnings.append(str(patient_resolution.warning))
        else:
            warnings.append("No active patient matched the extracted first and last name.")
    elif patient_resolution.status == "ambiguous":
        warnings.append("Multiple active patients matched the extracted first and last name.")
    elif patient_resolution.status in {"inactive", "deceased"}:
        warnings.append("Only inactive or deceased patients matched the extracted name.")

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
