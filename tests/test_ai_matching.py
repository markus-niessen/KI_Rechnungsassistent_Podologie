from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.matching import (
    resolve_patient_candidates,
    resolve_service_candidates,
    resolve_validated_case,
)
from app.db.base import Base
from app.db.models import Patient, Service


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def _patient(patient_nr: str, first_name: str = "Peter", last_name: str = "Wagner", active: bool = True) -> Patient:
    return Patient(patient_nr=patient_nr, first_name=first_name, last_name=last_name, active=active)


def _service(name: str, active: bool = True, net_price: str = "58.00", vat_rate: str = "19.00") -> Service:
    return Service(
        name=name,
        active=active,
        net_price=Decimal(net_price),
        vat_rate=Decimal(vat_rate),
    )


def test_patient_candidate_resolution_matches_one_active_exact_name(db: Session) -> None:
    patient = _patient("P-000001")
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "peter", "WAGNER")

    assert result.status == "matched"
    assert result.patient_id == patient.id
    assert result.candidates == []


def test_patient_candidate_resolution_returns_not_found_for_no_or_inactive_match(db: Session) -> None:
    db.add(_patient("P-000001", active=False))
    db.commit()

    result = resolve_patient_candidates(db, "Peter", "Wagner")

    assert result.status == "not_found"
    assert result.patient_id is None
    assert result.candidates == []


def test_patient_candidate_resolution_does_not_select_ambiguous_patients(db: Session) -> None:
    db.add_all([_patient("P-000001"), _patient("P-000002")])
    db.commit()

    result = resolve_patient_candidates(db, "Peter", "Wagner")

    assert result.status == "ambiguous"
    assert result.patient_id is None
    assert [candidate.patient_nr for candidate in result.candidates] == ["P-000001", "P-000002"]


def test_service_candidate_resolution_returns_database_price_vat_and_ki_quantity(db: Session) -> None:
    service = _service("Fußpflege groß", net_price="58.00", vat_rate="19.00")
    db.add(service)
    db.commit()

    result = resolve_service_candidates(db, "fußpflege groß", Decimal("2"))

    assert result.status == "matched"
    assert result.service_id == service.id
    assert result.name == "Fußpflege groß"
    assert result.quantity == Decimal("2")
    assert result.net_price == Decimal("58.00")
    assert result.vat_rate == Decimal("19.00")


def test_service_candidate_resolution_returns_not_found_for_missing_or_inactive_service(db: Session) -> None:
    db.add(_service("Mehrarbeit", active=False))
    db.commit()

    missing = resolve_service_candidates(db, "Spirularin Gel", Decimal("1"))
    inactive = resolve_service_candidates(db, "Mehrarbeit", Decimal("1"))

    assert missing.status == "not_found"
    assert inactive.status == "not_found"
    assert inactive.service_id is None


def test_service_candidate_resolution_does_not_select_ambiguous_services(db: Session) -> None:
    db.add_all([_service("Mehrarbeit"), _service("Mehrarbeit", net_price="6.00")])
    db.commit()

    result = resolve_service_candidates(db, "Mehrarbeit", Decimal("1"))

    assert result.status == "ambiguous"
    assert result.service_id is None
    assert len(result.candidates) == 2


def test_validated_case_is_fully_resolved_when_patient_and_all_items_match(db: Session) -> None:
    patient = _patient("P-000001")
    service = _service("Fußpflege groß")
    extra_service = _service("Mehrarbeit", net_price="5.00")
    db.add_all([patient, service, extra_service])
    db.commit()

    result = resolve_validated_case(
        db,
        {
            "patient": {"vorname": "Peter", "nachname": "Wagner"},
            "positionen": [
                {"bezeichnung": "Fußpflege groß", "menge": 1},
                {"bezeichnung": "Mehrarbeit", "menge": 2},
            ],
        },
    )

    assert result.all_resolved is True
    assert result.patient.patient_id == patient.id
    assert [item.service_id for item in result.items] == [service.id, extra_service.id]
    assert [item.quantity for item in result.items] == [Decimal("1"), Decimal("2")]
    assert result.warnings == []


@pytest.mark.parametrize(
    "structured_case",
    [
        {
            "patient": {"vorname": "Unbekannt", "nachname": "Person"},
            "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
        },
        {
            "patient": {"vorname": "Peter", "nachname": "Wagner"},
            "positionen": [{"bezeichnung": "Nicht vorhandene Leistung", "menge": 1}],
        },
    ],
)
def test_validated_case_is_not_fully_resolved_when_patient_or_position_is_missing(
    db: Session, structured_case: dict[str, object]
) -> None:
    db.add_all([_patient("P-000001"), _service("Fußpflege groß")])
    db.commit()

    result = resolve_validated_case(db, structured_case)

    assert result.all_resolved is False
    assert result.warnings


def test_validated_case_is_not_fully_resolved_for_ambiguous_candidates(db: Session) -> None:
    db.add_all([_patient("P-000001"), _patient("P-000002"), _service("Mehrarbeit"), _service("Mehrarbeit")])
    db.commit()

    result = resolve_validated_case(
        db,
        {
            "patient": {"vorname": "Peter", "nachname": "Wagner"},
            "positionen": [{"bezeichnung": "Mehrarbeit", "menge": 1}],
        },
    )

    assert result.all_resolved is False
    assert result.patient.status == "ambiguous"
    assert result.items[0].status == "ambiguous"
