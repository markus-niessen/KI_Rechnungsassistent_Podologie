from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData, create_engine, text

from app.db.models import BusinessProfile


DATABASE_PATH = Path("data/app.db")


def _assign_prefixes(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    assigned_prefixes: set[str] = set()
    for row in rows:
        location_code = row["location_code"]
        normalized_code = location_code.strip() if isinstance(location_code, str) else None
        row["location_code"] = normalized_code or None

        if normalized_code:
            if normalized_code not in assigned_prefixes:
                prefix = normalized_code
            else:
                suffix = 2
                while f"{normalized_code}-{suffix}" in assigned_prefixes:
                    suffix += 1
                prefix = f"{normalized_code}-{suffix}"
        else:
            prefix = str(row["id"])

        if prefix in assigned_prefixes:
            raise RuntimeError(f"Cannot assign unique invoice prefix for business profile {row['id']}")
        row["invoice_prefix"] = prefix
        assigned_prefixes.add(prefix)
    return rows


def main() -> None:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        source_columns = [column.name for column in BusinessProfile.__table__.columns if column.name != "invoice_prefix"]
        rows = [
            dict(zip(source_columns, row, strict=True))
            for row in connection.execute(
                f"SELECT {', '.join(source_columns)} FROM business_profiles ORDER BY id"
            )
        ]

    rows = _assign_prefixes(rows)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before-invoice-prefix-migration-{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    metadata = MetaData()
    replacement_table = BusinessProfile.__table__.to_metadata(metadata, name="business_profiles_new")
    column_names = [column.name for column in BusinessProfile.__table__.columns]
    insert_statement = text(
        "INSERT INTO business_profiles_new "
        f"({', '.join(column_names)}) VALUES ({', '.join(f':{column_name}' for column_name in column_names)})"
    )
    engine = create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        connection.commit()
        with connection.begin():
            replacement_table.create(connection)
            connection.execute(insert_statement, rows)
            connection.execute(text("DROP TABLE business_profiles"))
            connection.execute(text("ALTER TABLE business_profiles_new RENAME TO business_profiles"))

        foreign_key_violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise RuntimeError(f"Foreign key check failed: {foreign_key_violations}")

    print(f"Backup created: {backup_path}")
    print(f"Migrated {len(rows)} business profiles.")


if __name__ == "__main__":
    main()
