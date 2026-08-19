from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select

from app.db.models import BusinessProfile, InvoicePrefixReservation


DATABASE_PATH = Path("data/app.db")


def main() -> None:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before-prefix-reservations-{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    engine = create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")
    with engine.begin() as connection:
        InvoicePrefixReservation.__table__.create(connection, checkfirst=True)
        prefixes = list(connection.scalars(select(BusinessProfile.invoice_prefix)))
        connection.execute(
            InvoicePrefixReservation.__table__.insert().prefix_with("OR IGNORE"),
            [{"invoice_prefix": prefix} for prefix in prefixes],
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise RuntimeError(f"Foreign key check failed: {foreign_key_violations}")

    print(f"Backup created: {backup_path}")
    print(f"Reserved {len(prefixes)} existing invoice prefixes.")


if __name__ == "__main__":
    main()
