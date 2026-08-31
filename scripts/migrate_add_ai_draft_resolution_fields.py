"""Additive SQLite migration for AI-created DRAFT resolution metadata."""

from datetime import datetime
from pathlib import Path
import shutil
import sqlite3


DATABASE_PATH = Path("data/app.db")


def main() -> None:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before_ai_draft_resolution_{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    with sqlite3.connect(DATABASE_PATH) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(invoices)")}
        if "new_patient_data" not in columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN new_patient_data JSON")
        if "patient_resolution_required" not in columns:
            connection.execute(
                "ALTER TABLE invoices ADD COLUMN patient_resolution_required BOOLEAN NOT NULL DEFAULT 0"
            )
        if "unresolved_items" not in columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN unresolved_items JSON NOT NULL DEFAULT '[]'")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    if violations:
        raise RuntimeError(f"Foreign-key check failed: {violations}")
    print(f"Backup created: {backup_path}")
    print("Migration completed: AI DRAFT resolution fields added to invoices")


if __name__ == "__main__":
    main()
