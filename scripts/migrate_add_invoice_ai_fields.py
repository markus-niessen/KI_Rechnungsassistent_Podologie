"""Additive SQLite migration for invoice AI source and review metadata."""

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
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before_invoice_ai_fields_{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    with sqlite3.connect(DATABASE_PATH) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(invoices)")}
        if "source_text" not in columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN source_text TEXT")
        if "ai_review_comment" not in columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN ai_review_comment TEXT")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    if violations:
        raise RuntimeError(f"Foreign-key check failed: {violations}")
    print(f"Backup created: {backup_path}")
    print("Migration completed: invoices.source_text, invoices.ai_review_comment")


if __name__ == "__main__":
    main()
