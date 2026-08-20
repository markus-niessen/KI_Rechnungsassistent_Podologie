# KI-Rechnungsassistent für Podologie

Lokale Webanwendung für die schnelle Vorbereitung, Prüfung und Erstellung von Einzelrechnungen, Sammelrechnungen und Quittungen.

## Aktueller Stand

- FastAPI-Grundgerüst vorhanden
- SQLAlchemy-Grundkonfiguration vorhanden
- SQLite-Standardkonfiguration vorhanden
- Healthcheck unter `GET /health`

## Zahlungen und Teilzahlungen

- `POST /payments`, `GET /payments/{payment_id}`, `PATCH /payments/{payment_id}` und `DELETE /payments/{payment_id}` verwalten Zahlungen.
- `GET /invoices/{invoice_id}/payments` liefert Zahlungen chronologisch.
- Teilzahlungen werden als mehrere Datensätze in `payments` gespeichert. Erlaubt sind `CASH` und `BANK_TRANSFER`.
- Rechnungsstatus und abgeleiteter Zahlungsstatus sind getrennt. Rechnungsantworten enthalten `paid_amount`, `remaining_amount` sowie `OPEN`, `PARTIALLY_PAID` oder `PAID`.
- DATEV- und Steuerexport sind nicht implementiert.

## Entwicklung

Die Anwendung ist als lokale MVP-Basis aufgebaut und so vorbereitet, dass ein späterer Wechsel zu PostgreSQL unkompliziert bleibt.
