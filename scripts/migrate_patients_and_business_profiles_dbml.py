from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData, create_engine, text

from app.db.models import BusinessProfile, Patient


DATABASE_PATH = Path("data/app.db")
PATIENT_SOURCE_COLUMNS = (
    "id, patient_number, first_name, last_name, date_of_birth, street, postal_code, city, active, created_at"
)
BUSINESS_PROFILE_SOURCE_COLUMNS = (
    "id, business_name, location_name, location_code, invoice_prefix, street, postal_code, city, "
    "phone, email, tax_number, vat_id, ik_number, iban, bic, bank_name, active, created_at"
)


def _read_source_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        patient_rows = [
            {
                "id": row[0],
                "patient_nr": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "birth_date": row[4],
                "deceased": False,
                "death_date": None,
                "street": row[5],
                "zip": row[6],
                "city": row[7],
                "invoice_name": None,
                "invoice_street": None,
                "invoice_zip": None,
                "invoice_city": None,
                "home_name": None,
                "room": None,
                "active": row[8],
                "created_at": row[9],
                "updated_at": row[9],
            }
            for row in connection.execute(f"SELECT {PATIENT_SOURCE_COLUMNS} FROM patients ORDER BY id")
        ]
        business_profile_rows = [
            {
                "id": row[0],
                "business_name": row[1],
                "location_name": row[2],
                "location_code": row[3],
                "invoice_prefix": row[4],
                "street": row[5],
                "postal_code": row[6],
                "city": row[7],
                "phone": row[8],
                "email": row[9],
                "tax_number": row[10],
                "vat_id": row[11],
                "ik_number": row[12],
                "iban": row[13],
                "bic": row[14],
                "bank_name": row[15],
                "logo_path": None,
                "active": row[16],
                "created_at": row[17],
                "updated_at": row[17],
            }
            for row in connection.execute(
                f"SELECT {BUSINESS_PROFILE_SOURCE_COLUMNS} FROM business_profiles ORDER BY id"
            )
        ]
    return patient_rows, business_profile_rows


def _insert_statement(table_name: str, columns: list[str]) -> str:
    return (
        f"INSERT INTO {table_name} ({', '.join(columns)}) "
        f"VALUES ({', '.join(f':{column}' for column in columns)})"
    )


def main() -> None:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    patient_rows, business_profile_rows = _read_source_rows()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before-dbml-alignment-{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    metadata = MetaData()
    patients_new = Patient.__table__.to_metadata(metadata, name="patients_new")
    business_profiles_new = BusinessProfile.__table__.to_metadata(metadata, name="business_profiles_new")
    patient_columns = [column.name for column in Patient.__table__.columns]
    business_profile_columns = [column.name for column in BusinessProfile.__table__.columns]
    engine = create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        connection.commit()
        with connection.begin():
            connection.execute(text("DROP INDEX IF EXISTS idx_patients_name"))
            patients_new.create(connection)
            business_profiles_new.create(connection)
            connection.execute(text(_insert_statement("patients_new", patient_columns)), patient_rows)
            connection.execute(
                text(_insert_statement("business_profiles_new", business_profile_columns)),
                business_profile_rows,
            )
            connection.execute(text("DROP TABLE patients"))
            connection.execute(text("DROP TABLE business_profiles"))
            connection.execute(text("ALTER TABLE patients_new RENAME TO patients"))
            connection.execute(text("ALTER TABLE business_profiles_new RENAME TO business_profiles"))

        foreign_key_violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise RuntimeError(f"Foreign key check failed: {foreign_key_violations}")

    print(f"Backup created: {backup_path}")
    print(f"Migrated {len(patient_rows)} patients and {len(business_profile_rows)} business profiles.")


if __name__ == "__main__":
    main()
