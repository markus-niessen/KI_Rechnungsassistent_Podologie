from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData, create_engine, text

from app.db.models import BusinessProfile, Invoice, InvoiceItem, Patient, Service


DATABASE_PATH = Path("data/app.db")
INVOICE_SOURCE_COLUMNS = (
    "id, invoice_number, patient_id, invoice_date, due_date, status, "
    "total_net, total_vat, total_gross, created_at"
)
ITEM_SOURCE_COLUMNS = (
    "id, invoice_id, service_id, description, quantity, unit_net_price, vat_rate, "
    "line_net, line_vat, line_gross"
)


def _read_source_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        invoice_rows = [
            {
                "id": row[0],
                "invoice_number": row[1],
                "patient_id": row[2],
                "business_profile_id": None,
                "document_type": "INVOICE",
                "invoice_date": row[3],
                "due_date": row[4],
                "status": row[5],
                "total_net": row[6],
                "total_vat": row[7],
                "total_gross": row[8],
                "created_at": row[9],
            }
            for row in connection.execute(f"SELECT {INVOICE_SOURCE_COLUMNS} FROM invoices ORDER BY id")
        ]
        item_rows = [
            {
                "id": row[0],
                "invoice_id": row[1],
                "patient_id": None,
                "service_id": row[2],
                "patient_name_snapshot": None,
                "service_name_snapshot": row[3],
                "description": row[3],
                "quantity": row[4],
                "unit_net_price": row[5],
                "vat_rate": row[6],
                "line_net": row[7],
                "line_vat": row[8],
                "line_gross": row[9],
            }
            for row in connection.execute(f"SELECT {ITEM_SOURCE_COLUMNS} FROM invoice_items ORDER BY id")
        ]
    return invoice_rows, item_rows


def _insert_statement(table_name: str, columns: list[str]) -> str:
    return f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(f':{column}' for column in columns)})"


def main() -> None:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    invoice_rows, item_rows = _read_source_rows()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATABASE_PATH.with_name(f"{DATABASE_PATH.stem}.before-invoice-crud-{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)

    metadata = MetaData()
    Patient.__table__.to_metadata(metadata)
    BusinessProfile.__table__.to_metadata(metadata)
    Service.__table__.to_metadata(metadata)
    Invoice.__table__.to_metadata(metadata)
    invoices_new = Invoice.__table__.to_metadata(metadata, name="invoices_new")
    invoice_items_new = InvoiceItem.__table__.to_metadata(metadata, name="invoice_items_new")
    invoice_columns = [column.name for column in Invoice.__table__.columns]
    item_columns = [column.name for column in InvoiceItem.__table__.columns]
    engine = create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        connection.commit()
        with connection.begin():
            connection.execute(text("DROP TABLE IF EXISTS invoice_items_new"))
            connection.execute(text("DROP TABLE IF EXISTS invoices_new"))
            invoices_new.create(connection)
            invoice_items_new.create(connection)
            if invoice_rows:
                connection.execute(text(_insert_statement("invoices_new", invoice_columns)), invoice_rows)
            if item_rows:
                connection.execute(text(_insert_statement("invoice_items_new", item_columns)), item_rows)
            connection.execute(text("DROP TABLE invoice_items"))
            connection.execute(text("DROP TABLE invoices"))
            connection.execute(text("ALTER TABLE invoices_new RENAME TO invoices"))
            connection.execute(text("ALTER TABLE invoice_items_new RENAME TO invoice_items"))

        foreign_key_violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise RuntimeError(f"Foreign key check failed: {foreign_key_violations}")

    print(f"Backup created: {backup_path}")
    print(f"Migrated {len(invoice_rows)} invoices and {len(item_rows)} invoice items.")


if __name__ == "__main__":
    main()
