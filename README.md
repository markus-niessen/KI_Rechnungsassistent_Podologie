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

## KI 1: strukturierte Textextraktion

- `POST /ai/extract` sendet einen freien Behandlungs-Text an KI 1 und gibt ausschließlich dessen strukturiertes JSON zurück.
- Der API-Key steht lokal in `.env` als `OPENAI_API_KEY=`; `.env.example` enthält nur die leere Vorlage.
- Die Extraktion erzeugt keine Rechnung, keine Zahlungen und keine Datenbankzuordnungen.

## Entwicklung

Die Anwendung ist als lokale MVP-Basis aufgebaut und so vorbereitet, dass ein späterer Wechsel zu PostgreSQL unkompliziert bleibt.
