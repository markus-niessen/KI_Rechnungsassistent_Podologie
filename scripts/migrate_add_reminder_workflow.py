"""Additive SQLite migration for reminder settings and reminder drafts."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine

from app.db.models import Reminder, ReminderSetting


DATABASE_PATH = Path("data/app.db")


def main() -> None:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before-reminder-workflow-{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    engine = create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")
    with engine.begin() as connection:
        ReminderSetting.__table__.create(connection, checkfirst=True)
        Reminder.__table__.create(connection, checkfirst=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Foreign-key check failed: {violations}")

    print(f"Backup created: {backup_path}")
    print("Migration completed: reminder_settings and reminders added")


if __name__ == "__main__":
    main()
