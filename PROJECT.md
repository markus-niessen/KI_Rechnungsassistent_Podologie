# PROJECT.md

# KI-Rechnungsassistent für Podologie

## 1. Projektziel

Lokale Webanwendung für eine podologische Praxis zur schnellen Vorbereitung, Prüfung und Erstellung von:

- Einzelrechnungen
- Sammelrechnungen
- Quittungen

Der zentrale Nutzen ist die schnelle Mehrfacherfassung. Mit wenigen Stichworten sollen mehrere Belegentwürfe nacheinander erstellt, in einer Arbeitsliste gesammelt, kontrolliert und anschließend in einem Arbeitsgang finalisiert werden.

**Abgabetermin / MVP-Ziel: 15.09.2026**

Das MVP muss auch ohne KI vollständig nutzbar sein. Die KI unterstützt nur beim Erkennen und Strukturieren von Eingaben.

---

## 2. Kern-Workflow

1. Benutzer gibt Stichworte ein, z. B.:
   - `Müller Fußpflege groß Mehrarbeit Sammelrechnung`
2. Parser/KI erzeugt einen strukturierten Vorschlag.
3. Anwendung sucht passende Patienten.
4. Treffer werden mit mehreren Details angezeigt:
   - Patientennummer
   - Vorname/Nachname
   - Geburtsdatum
   - Ort
   - optional Heim/Zimmer
5. Benutzer bestätigt oder wechselt den Patienten.
6. Vorschau wird angezeigt und bleibt bearbeitbar.
7. Benutzer kann:
   - Patient ändern
   - Rechnungsadresse ergänzen
   - Leistung ändern
   - Position hinzufügen/löschen
   - Menge/Preis im erlaubten Rahmen prüfen
   - Leistungsdatum ändern
   - Belegart ändern
8. Entwurf wird zur Arbeitsliste hinzugefügt.
9. Weitere Vorgänge können sofort erfasst werden.
10. Arbeitsliste zeigt alle Entwürfe und Warnungen.
11. Benutzer korrigiert unvollständige Datensätze.
12. Entwürfe werden nach Belegart bzw. Rechnungsempfänger gruppiert.
13. Finalisierung:
   - Pflichtfelder prüfen
   - Patient bestätigt?
   - Rechnungsadresse vollständig?
   - mindestens eine Position?
   - Summen deterministisch berechnen
   - Belegnummer vergeben
   - Snapshots speichern
   - Status auf FINAL
   - PDF erzeugen
14. PDF anzeigen, speichern und drucken.

---

## 3. Pflichtumfang MVP

### Enthalten

- lokale Webanwendung
- FastAPI Backend
- SQLite
- SQLAlchemy
- PostgreSQL-kompatibles Datenmodell
- Firmen-/Praxisdaten
- Patienten
- Leistungen
- Patientensuche
- Einzelrechnung
- Sammelrechnung
- Quittung
- bearbeitbare Vorschau
- Arbeitsliste für mehrere Entwürfe
- Finalisierung
- Belegnummern
- PDF-Ausgabe
- mehrseitige Sammelrechnungen
- QR-Code für Überweisung auf Rechnungen
- zwei Prompt-Techniken
- zwei Text-KI-Anbindungen
- Dynamic Context Injection
- Vergleichsanalyse
- Speicherung relevanter KI-Vergleichsdaten
- automatisierte Tests
- Git/GitHub
- README
- laufende Projektdokumentation
- Demo-Daten ohne echte Patientendaten

### Bewusst nicht im ersten MVP

- Nagelpilz-/Hühneraugen-/Wund-/Zehendokumentation
- Fußgrafik
- Verordnung 13
- blaue Verordnung
- Thevea-Anbindung
- komplettes Mahnwesen
- Verzugszinsen
- DATEV
- Bankimport
- OCR
- komplexe Betreuer-/Angehörigenhistorie
- vollständige Heimverwaltung
- umfangreiche Preisversionierung außerhalb der Rechnungs-Snapshots

Diese Punkte dürfen später ergänzt werden, aber nicht den MVP-Termin gefährden.

---

## 4. Leistungen im MVP

Startwerte:

| Code | Leistung | Preis |
|---|---|---:|
| FPK | Kosmetische Fußpflege klein | 38,00 € |
| FPG | Kosmetische Fußpflege groß | 58,00 € |
| MA | Mehrarbeit | 5,00 € |

Wichtig:

- KI darf umgangssprachliche Formulierungen erkennen.
- Offizielle Bezeichnung, Preis und Steuersatz kommen aus `services`.
- Preis und Steuer dürfen nie vom LLM frei erfunden werden.

---

## 5. Datenbank – schlankes MVP

### `companies`

Speichert Rechnungssteller/Praxisdaten.

Vorgesehene Felder:

- id
- name
- street
- zip
- city
- phone
- email
- tax_number
- vat_id optional
- iban
- bic optional
- bank_name
- logo_path optional
- active

### `patients`

- id
- patient_nr
- first_name
- last_name
- birth_date optional
- street
- zip
- city
- invoice_name optional
- invoice_street optional
- invoice_zip optional
- invoice_city optional
- home_name optional
- room optional
- active

Regel:

Eine Einzelrechnung darf ohne vollständige Rechnungsadresse nicht finalisiert werden.

### `services`

- id
- code
- name
- price
- vat_rate
- active

### `invoices`

Speichert Entwurf und finalen Belegkopf.

- id
- document_type
- status
- invoice_number optional solange DRAFT
- company_id
- invoice_recipient_snapshot
- invoice_address_snapshot
- invoice_date
- due_date optional
- subtotal
- tax_total
- total
- payment_status
- created_at
- finalized_at optional

Belegarten:

- `INVOICE`
- `COLLECTIVE_INVOICE`
- `RECEIPT`

Status:

- `DRAFT`
- `FINAL`
- `CANCELLED` optional als Vorbereitung

### `invoice_items`

- id
- invoice_id
- patient_id optional
- patient_name_snapshot
- service_id optional
- service_name_snapshot
- service_date
- quantity
- unit_price
- vat_rate
- line_total

### `payments`

- id
- invoice_id
- amount
- payment_date
- payment_method
- note optional

Damit können später auch Teilzahlungen sauber ergänzt werden.

---

## 6. Patientensuche

Ein Patient darf nicht nur anhand seines Namens endgültig zugeordnet werden.

Beispielanzeige:

`P-000124 – Erika Müller – geb. 12.05.1940 – Euskirchen – Sonnenhof – Zimmer 105`

Bei mehreren Treffern:

`Patient nicht eindeutig zugeordnet`

Der Benutzer muss immer die Möglichkeit haben:

- anderen Treffer auszuwählen
- Patient zu ändern
- neuen Patienten anzulegen

---

## 7. Belegarten

### 7.1 Einzelrechnung

- Standardformat A4
- vollständiger Rechnungsempfänger
- Positionstabelle
- Leistungsdatum
- Zwischensumme
- Steuerdarstellung
- Gesamtbetrag
- Zahlungsziel
- Bankdaten
- EPC-QR-Code / GiroCode für Überweisung
- professionelle Gestaltung

### 7.2 Sammelrechnung

Mehrere Patienten/Leistungen für einen gemeinsamen Rechnungsempfänger.

Positionen enthalten mindestens:

- Position
- Patient
- Leistungsdatum
- Leistung
- Zusatz
- Betrag

Mehrseitigkeit muss unterstützt werden.

### 7.3 Quittung

- Standardformat A5
- professionelles Layout
- Quittungsnummer
- Datum
- Patient
- Positionen
- Gesamtbetrag
- Zahlungsart
- Hinweis auf erhaltene Zahlung
- Praxisdaten
- optional Unterschriftsbereich

Die Beleglogik darf nicht fest an A5 gekoppelt sein. Später sollen andere Ausgabeformate möglich sein, z. B.:

- A4
- A5 Hochformat
- A5 Querformat
- Thermodrucker / benutzerdefinierte Papierbreite

---

## 8. PDF-Regeln

Die vollständigen PDF-Regeln stehen in:

`docs/PDF_REQUIREMENTS.md`

Wichtige Grundsätze:

- professioneller als die bisherigen Papierbeispiele
- Rechnungen/Sammelrechnungen A4
- Quittung standardmäßig A5
- Papierformat und Beleglogik trennen
- mehrseitige Sammelrechnungen
- Seitenzahl auf jeder Seite
- Übertrag/Zwischensummen bei Seitenwechsel
- endgültiger Gesamtbetrag auf letzter Seite
- QR-Code bei überweisbaren Rechnungen
- keine KI zur PDF-Berechnung

---

## 9. QR-Code / GiroCode

QR-Code wird programmatisch erzeugt.

Inhalt:

- Empfänger
- IBAN
- BIC soweit erforderlich
- Betrag
- Verwendungszweck

Beispiel Verwendungszweck:

`Rechnung RE-EU-2026-000123`

Ablauf:

1. Rechnung finalisieren
2. Gesamtbetrag berechnen
3. Bankdaten aus `companies`
4. Rechnungsnummer als Verwendungszweck
5. EPC-QR-Code erzeugen
6. QR-Code in PDF einbetten

---

## 10. Mehrseitige Rechnungen

### Seite 1 / Zwischenseiten

- Kopf mit Rechnungsnummer
- Seitennummer
- Positionstabelle
- am Seitenende Übertrag/Zwischensumme

### Folgeseite

- Übertrag von vorheriger Seite
- weitere Positionen

### Letzte Seite

- Zwischensumme
- Steuer
- Gesamtbetrag
- Zahlungsziel
- Bankverbindung
- QR-Code

Beispiel:

`Rechnung SR-... | Seite 2 von 3`

---

## 11. Finalisierung und Unveränderbarkeit

DRAFT:

- bearbeitbar
- keine endgültige Belegnummer

FINAL:

- Pflichtfelder validiert
- eindeutige Nummer vergeben
- Snapshots gespeichert
- PDF erzeugt
- nicht einfach nachträglich überschreiben

Spätere Korrekturen sollen über Storno/Korrekturmechanismen aufgebaut werden, nicht durch Änderung des ursprünglichen FINAL-Belegs.

---

## 12. KI-Funktion

Die KI strukturiert nur Texteingaben.

Beispiel:

Eingabe:

`Müller groß Mehrarbeit Sammelrechnung 19.8.`

Zielausgabe:

```json
{
  "patient_query": "Müller",
  "service_code": "FPG",
  "extra_service_codes": ["MA"],
  "document_type": "COLLECTIVE_INVOICE",
  "service_date": "2026-08-19"
}
```

Danach prüft die Anwendung die Werte gegen Datenbank und erlaubte Werte.

---

## 13. Prompt-Techniken

### Prompt A – strukturierter Zero-Shot-Prompt

- klare Aufgabe
- festes JSON-Schema
- keine Beispiele

### Prompt B – Few-Shot-Prompt

- gleiches JSON-Schema
- zusätzlich mehrere Eingabe-/Ausgabe-Beispiele

Beide müssen mit denselben Testfällen verglichen werden.

---

## 14. Kontexttechnik

Verwendet wird:

**Dynamic Context Injection**

Dynamisch an das Modell übergeben werden nur für die jeweilige Anfrage relevante erlaubte Werte, z. B.:

- verfügbare Leistungscodes
- offizielle Leistungsnamen
- erlaubte Belegarten
- ggf. wenige passende Patientenkandidaten

Keine vollständige Patientendatenbank an eine Online-KI senden.

---

## 15. Zwei Text-KI-Anbindungen

Für die Ausbildungsanforderung werden zwei unterschiedliche Text-KI-Anbindungen implementiert.

Vorgesehen:

1. OpenAI
2. zweite API, z. B. Gemini oder Groq

Die zweite API muss für die Vergleichsanalyse funktionsfähig sein. Sie muss nicht zwingend die spätere Standard-API der Praxis werden.

---

## 16. Vergleichsanalyse

Für dieselben Eingaben werden verglichen:

- API/Modell
- Prompt-Technik
- richtige Patientensuche / Namensvorschlag
- richtige Leistung
- richtige Zusatzleistung
- richtige Belegart
- Vollständigkeit
- Halluzinationen
- ungültige Werte
- JSON-Schema eingehalten
- notwendige manuelle Korrekturen
- Laufzeit
- Tokenverbrauch soweit verfügbar
- Kosten soweit sinnvoll ermittelbar

Ergebnisse werden dokumentiert und nach Möglichkeit in der Datenbank oder einer strukturierten Vergleichsdatei gespeichert.

---

## 17. Datenschutz

- Anwendung lokal
- keine echten Patientendaten im Repository
- keine echten Patientendaten in Tests
- keine echten Patientendaten in Demo-Daten
- keine API-Keys im Repository
- Online-KI nur mit minimal notwendigem Kontext
- für Entwicklung ausschließlich erfundene Testpatienten verwenden

---

## 18. GitHub

Lokaler Projektordner:

`D:\Mein Projekt\KI_Rechnungsassistent für Podologie`

Vorgesehener Repository-Name:

`KI_rechnungsassistent_podologie`

`.gitignore` muss mindestens enthalten:

```gitignore
.env
.venv/
__pycache__/
*.pyc
*.db
data/
generated/
.idea/
```

Nach jedem funktionierenden Entwicklungsschritt committen.

---

## 19. Demo-Daten

Eine Seed-Funktion soll erfundene Demo-Daten erzeugen.

Beispiel:

`python seed_demo.py`

Zweck:

- Tests
- Screenshots
- Video
- Präsentation
- sichere Demo ohne echte Patientendaten

---

## 20. Ausbildungsanforderungen

Pflicht:

- Flask oder FastAPI API
- SQLite oder PostgreSQL
- use-case-spezifische Vergleichsanalyse
- 2 Prompt-Engineering-Techniken
- 2 unterschiedliche Text-API-Integrationen
- mindestens eine Kontexttechnik:
  - Retaining Conversation History
  - Dynamic Context Injection
  - RAG

Für dieses Projekt wird FastAPI + SQLite + Dynamic Context Injection verwendet.

Zusätzlich:

- strukturierter Output
- Benutzerprüfung vor Übernahme
- automatisierte Tests
- nachvollziehbare Entwicklungshistorie
- README
- Vergleichstabelle
- Datenbankschema
- Screenshots
- 5–10 Folien Präsentation
- 3–5 Minuten Projektvideo

---

## 21. Definition of Done – MVP

Das MVP ist fertig, wenn vollständig möglich ist:

1. mehrere Stichwort-Eingaben erfassen
2. Entwürfe erzeugen
3. Patienten eindeutig auswählen oder neu anlegen
4. Leistungen prüfen
5. Rechnungsadresse prüfen
6. Einzelrechnung / Sammelrechnung / Quittung auswählen
7. mehrere Entwürfe in Arbeitsliste sammeln
8. Warnungen korrigieren
9. gesammelt finalisieren
10. Belegnummern vergeben
11. Snapshots speichern
12. PDFs erzeugen
13. mehrseitige Sammelrechnung korrekt darstellen
14. QR-Code auf Rechnungen erzeugen
15. anzeigen / drucken
16. zwei Prompt-Strategien vergleichen
17. zwei Text-KI-Anbindungen vergleichen
18. Dynamic Context Injection nachweisen
19. Tests bestehen
20. README, Vergleichsdokumentation, Notion, Präsentation und Video fertigstellen
