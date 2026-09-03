from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.matching import (
    resolve_patient_candidates,
    resolve_service_candidates,
    resolve_validated_case,
)
from app.ai.service_context import get_active_service_names
from app.db.base import Base
from app.db.models import Patient, Service


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def _patient(
    patient_nr: str,
    first_name: str = "Peter",
    last_name: str = "Wagner",
    active: bool = True,
    deceased: bool = False,
    home_name: str | None = "Testheim",
) -> Patient:
    return Patient(
        patient_nr=patient_nr,
        first_name=first_name,
        last_name=last_name,
        birth_date=date(1950, 1, 2),
        street="Musterweg 1",
        zip="50667",
        city="Köln",
        home_name=home_name,
        room="12",
        active=active,
        deceased=deceased,
        death_date=date(2026, 1, 3) if deceased else None,
    )


def _service(name: str, active: bool = True, net_price: str = "58.00", vat_rate: str = "19.00") -> Service:
    return Service(
        name=name,
        active=active,
        net_price=Decimal(net_price),
        vat_rate=Decimal(vat_rate),
    )


def test_active_service_context_excludes_inactive_and_deactivated_services(db: Session) -> None:
    active_service = _service("Fußpflege groß")
    inactive_service = _service("Nicht mehr angebotene Leistung", active=False)
    db.add_all([active_service, inactive_service])
    db.commit()

    assert get_active_service_names(db) == ["Fußpflege groß"]

    active_service.active = False
    db.commit()

    assert get_active_service_names(db) == []


def test_patient_candidate_resolution_matches_one_active_exact_name(db: Session) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller")
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "sabine", "KELLER")

    assert result.status == "matched"
    assert result.patient_id == patient.id
    assert result.candidates == []


def test_patient_candidate_resolution_returns_not_found_when_no_candidate_exists(db: Session) -> None:
    result = resolve_patient_candidates(db, "Peter", "Wagner")

    assert result.status == "not_found"
    assert result.patient_id is None
    assert result.candidates == []


def test_patient_candidate_resolution_returns_one_active_first_name_match_as_ambiguous(db: Session) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller")
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "Sabine", None)

    assert result.status == "ambiguous"
    assert result.patient_id is None
    assert [candidate.patient_id for candidate in result.candidates] == [patient.id]


def test_patient_candidate_resolution_returns_multiple_active_first_name_matches_as_ambiguous(db: Session) -> None:
    first = _patient("P-000001", first_name="Sabine", last_name="Keller")
    second = _patient("P-000002", first_name="Sabine", last_name="Meier")
    db.add_all([first, second])
    db.commit()

    result = resolve_patient_candidates(db, "Sabine", None)

    assert result.status == "ambiguous"
    assert result.patient_id is None
    assert [candidate.patient_id for candidate in result.candidates] == [first.id, second.id]


@pytest.mark.parametrize("deceased, expected_status", [(False, "inactive"), (True, "deceased")])
def test_patient_candidate_resolution_returns_inactive_or_deceased_first_name_candidates(
    db: Session, deceased: bool, expected_status: str
) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller", active=False, deceased=deceased)
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "Sabine", None)

    assert result.status == expected_status
    assert result.patient_id is None
    assert [candidate.patient_id for candidate in result.candidates] == [patient.id]


def test_patient_candidate_resolution_returns_not_found_for_unknown_first_name(db: Session) -> None:
    result = resolve_patient_candidates(db, "Unbekannt", None)

    assert result.status == "not_found"
    assert result.patient_id is None
    assert result.candidates == []


def test_patient_candidate_resolution_returns_inactive_candidate_without_auto_assignment(db: Session) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller", active=False)
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "Sabine", "Keller")

    assert result.status == "inactive"
    assert result.patient_id is None
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.patient_id == patient.id
    assert candidate.patient_nr == "P-000001"
    assert candidate.street == "Musterweg 1"
    assert candidate.zip == "50667"
    assert candidate.city == "Köln"
    assert candidate.home_name == "Testheim"
    assert candidate.room == "12"
    assert candidate.active is False
    assert candidate.deceased is False


def test_patient_candidate_resolution_returns_deceased_candidate_without_auto_assignment(db: Session) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller", active=False, deceased=True)
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, "Sabine", "Keller")

    assert result.status == "deceased"
    assert result.patient_id is None
    assert result.candidates[0].patient_id == patient.id
    assert result.candidates[0].deceased is True
    assert result.candidates[0].death_date == date(2026, 1, 3)


def test_patient_candidate_resolution_does_not_select_ambiguous_patients(db: Session) -> None:
    db.add_all([_patient("P-000001"), _patient("P-000002")])
    db.commit()

    result = resolve_patient_candidates(db, "Peter", "Wagner")

    assert result.status == "ambiguous"
    assert result.patient_id is None
    assert [candidate.patient_nr for candidate in result.candidates] == ["P-000001", "P-000002"]


def test_patient_candidate_resolution_returns_last_name_candidates_without_auto_assignment(db: Session) -> None:
    db.add_all(
        [
            _patient("P-000001", first_name="Sabine", last_name="Keller", home_name="Seniorenzentrum Sonnenhof"),
            _patient("P-000002", first_name="Marta", last_name="Keller", home_name="Haus Abendrot"),
        ]
    )
    db.commit()

    result = resolve_patient_candidates(db, None, "Keller")

    assert result.status == "ambiguous"
    assert result.patient_id is None
    assert [candidate.first_name for candidate in result.candidates] == ["Sabine", "Marta"]


def test_patient_candidate_resolution_matches_last_name_with_unique_home_context(db: Session) -> None:
    sabine = _patient(
        "P-000001", first_name="Sabine", last_name="Keller", home_name="Seniorenzentrum Sonnenhof"
    )
    db.add_all([sabine, _patient("P-000002", first_name="Marta", last_name="Keller", home_name="Haus Abendrot")])
    db.commit()

    result = resolve_patient_candidates(db, None, "Keller", "Seniorenzentrum Sonnenhof")

    assert result.status == "matched"
    assert result.patient_id == sabine.id


def test_patient_candidate_resolution_keeps_last_name_without_home_context_ambiguous(db: Session) -> None:
    db.add_all(
        [
            _patient("P-000001", first_name="Sabine", last_name="Keller", home_name="Seniorenzentrum Sonnenhof"),
            _patient("P-000002", first_name="Marta", last_name="Keller", home_name="Haus Abendrot"),
        ]
    )
    db.commit()

    result = resolve_patient_candidates(db, None, "Keller")

    assert result.status == "ambiguous"
    assert result.patient_id is None


def test_patient_candidate_resolution_falls_back_to_inactive_last_name_candidates(db: Session) -> None:
    patient = _patient("P-000001", first_name="Sabine", last_name="Keller", active=False)
    db.add(patient)
    db.commit()

    result = resolve_patient_candidates(db, None, "Keller")

    assert result.status == "inactive"
    assert result.patient_id is None
    assert [candidate.patient_id for candidate in result.candidates] == [patient.id]


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


def test_validated_case_keeps_an_unknown_patient_as_unpersisted_ai_data(db: Session) -> None:
    service = _service("Fußpflege groß")
    db.add(service)
    db.commit()
    patient_count_before = db.query(Patient).count()

    result = resolve_validated_case(
        db,
        {
            "patient": {"vorname": "Anna", "nachname": "Müller"},
            "positionen": [{"bezeichnung": "Fußpflege groß", "menge": 1}],
        },
    )

    assert result.patient.status == "new_patient"
    assert result.patient.patient_id is None
    assert result.patient.source == "ai_extraction"
    assert result.patient.data is not None
    assert result.patient.data.first_name == "Anna"
    assert result.patient.data.last_name == "Müller"
    assert result.patient.data.birth_date is None
    assert result.patient.data.street is None
    assert result.patient.data.zip is None
    assert result.patient.data.city is None
    assert result.patient.missing_fields == ["birth_date", "street", "zip", "city"]
    assert result.patient.warning is not None
    assert result.all_resolved is False
    assert db.query(Patient).count() == patient_count_before


def test_unpersisted_new_patient_data_uses_editable_patient_model_field_names(db: Session) -> None:
    result = resolve_validated_case(
        db,
        {
            "patient": {
                "vorname": "Anna",
                "nachname": "Müller",
                "strasse": "Musterstraße 1",
                "plz": "50667",
                "ort": "Köln",
            },
            "positionen": [],
        },
    )

    assert result.patient.status == "new_patient"
    assert result.patient.data is not None
    assert result.patient.data.model_dump() == {
        "first_name": "Anna",
        "last_name": "Müller",
        "birth_date": None,
        "street": "Musterstraße 1",
        "zip": "50667",
        "city": "Köln",
    }
    assert db.query(Patient).count() == 0


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
