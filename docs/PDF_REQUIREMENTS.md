# PDF_REQUIREMENTS.md

# PDF- und Druckanforderungen

## 1. Ziel

Die bisherigen Papierbelege dienen nur als fachliche Beispiele. Das neue Layout soll deutlich professioneller, übersichtlicher und technisch flexibel sein.

Die Beleglogik wird von der Darstellung getrennt.

Ein Beleg enthält fachliche Daten. Ein Renderer entscheidet über Papierformat und Layout.

---

## 2. Standardformate

### Einzelrechnung
- A4 Hochformat

### Sammelrechnung
- A4 Hochformat
- mehrseitig möglich

### Quittung
- A5 Hochformat als Standard

Später erweiterbar um:

- A4
- A5 Querformat
- Thermodrucker
- benutzerdefinierte Papierbreite / Rollenpapier

Keine Geschäftslogik darf davon abhängen, ob die Quittung A5, A4 oder Thermopapier verwendet.

---

## 3. Einzelrechnung – Ziellayout

Mindestens:

- Praxisname / Logo
- vollständige Praxisanschrift
- Kontakt
- Steuerangaben soweit erforderlich
- Bankverbindung
- Rechnungsempfänger
- Überschrift `Rechnung`
- Rechnungsnummer
- Rechnungsdatum
- Leistungsdatum / Leistungszeitraum
- Positionstabelle
- Zwischensumme
- Steuerdarstellung
- Gesamtbetrag
- Zahlungsziel
- Bankdaten
- EPC-QR-Code / GiroCode
- Seitennummer bei mehr als einer Seite

Empfohlene Positionstabelle:

| Pos. | Beschreibung | Menge | Einzelpreis | Gesamt |
|---:|---|---:|---:|---:|

Patientenname kann bei einer normalen Einzelrechnung im Kopf oder sinnvoll bei der Position dargestellt werden.

---

## 4. Sammelrechnung – Ziellayout

Mindestens:

- Praxisname / Logo
- Praxisdaten
- Rechnungsempfänger
- Überschrift `Sammelrechnung`
- Rechnungsnummer
- Rechnungsdatum
- Leistungszeitraum
- strukturierte Positionstabelle

Empfohlene Spalten:

| Pos. | Patient | Leistungsdatum | Leistung | Zusatz | Betrag |
|---:|---|---|---|---|---:|

Jede Position muss einem Patienten nachvollziehbar zugeordnet bleiben.

---

## 5. Mehrseitige Sammelrechnung

### Auf jeder Seite

- Rechnungsnummer
- Seite X von Y
- klarer Tabellenkopf bzw. sinnvoll wiederholter Tabellenkopf

### Ende einer nicht letzten Seite

Ausgabe eines Übertrags bzw. einer laufenden Zwischensumme, z. B.:

`Übertrag / Zwischensumme: 487,00 €`

### Beginn der nächsten Seite

z. B.:

`Übertrag von Seite 1: 487,00 €`

### Letzte Seite

- Zwischensumme
- Steuer
- Gesamtbetrag
- Zahlungsziel
- Bankverbindung
- QR-Code

Wichtig:

Der Gesamtbetrag darf nicht durch die PDF-Bibliothek oder KI unabhängig neu berechnet werden. Er kommt aus der bereits geprüften Beleglogik.

---

## 6. Quittung – Ziellayout

Standard: A5 Hochformat.

Mindestens:

- Praxisname / Logo
- Überschrift `Quittung`
- Quittungsnummer
- Datum
- Patient
- Positionen
- Gesamtbetrag
- Zahlungsart
- Hinweis, dass der Betrag erhalten wurde
- Praxisanschrift
- optional Unterschriftsbereich

Beispielstruktur:

```text
QUITTUNG

Quittungsnummer: Q-2026-0001
Datum: 18.08.2026

Patient:
Max Mustermann

Kosmetische Fußpflege groß      58,00 €
Mehrarbeit                        5,00 €
                                 -------
Gesamtbetrag                     63,00 €

Zahlungsart: Bar
inkl. MwSt. / Steuerangabe nach gültiger Beleglogik

Betrag dankend erhalten.

Praxisdaten

____________________
Unterschrift
```

---

## 7. QR-Code / GiroCode

Für überweisbare Rechnungen wird ein EPC-QR-Code erzeugt.

Daten:

- Empfänger
- IBAN
- BIC soweit erforderlich
- Betrag
- Verwendungszweck

Verwendungszweck bevorzugt:

`Rechnung <RECHNUNGSNUMMER>`

Beispiel:

`Rechnung RE-EU-2026-000123`

Der QR-Code wird erst erzeugt, wenn:

- Rechnung finalisiert ist
- Rechnungsnummer feststeht
- Betrag feststeht
- Bankdaten vollständig sind

Bei Quittungen, die bereits bar bezahlt wurden, ist ein Zahlungs-QR-Code standardmäßig nicht erforderlich.

---

## 8. Professionelle Gestaltung

Das Layout soll:

- klar
- modern
- druckbar
- gut lesbar
- nicht überladen
- auch in Schwarz-Weiß verständlich

sein.

Keine unnötigen grafischen Elemente.

Zahlen rechtsbündig.

Euro-Beträge einheitlich formatieren.

Datumsformat in deutscher Darstellung.

Tabellenköpfe deutlich von Datenzeilen absetzen.

Genügend Rand für normale Drucker berücksichtigen.

---

## 9. Trennung von Beleg und Renderer

Empfohlene Architektur:

```text
Belegdaten
   |
   +--> A4 Invoice Renderer
   |
   +--> A4 Collective Invoice Renderer
   |
   +--> A5 Receipt Renderer
   |
   +--> später Thermal Renderer
```

Die Berechnungs- und Finalisierungslogik darf nicht dupliziert werden.

Renderer erhalten fertige, validierte Daten.

---

## 10. Druck

Im MVP reicht:

- PDF erzeugen
- PDF im Browser öffnen
- Benutzer druckt über Browser/PDF-Viewer

Keine direkte Druckersteuerung im MVP erforderlich.

Später kann ein spezielles Thermodrucker-Layout ergänzt werden.

---

## 11. Testfälle PDF

Mindestens prüfen:

1. Einzelrechnung mit einer Position
2. Einzelrechnung mit Mehrarbeit
3. Quittung A5
4. Sammelrechnung mit mehreren Patienten
5. Sammelrechnung mit mehreren Seiten
6. korrekter Übertrag zwischen Seiten
7. korrekter Gesamtbetrag auf letzter Seite
8. QR-Code vorhanden, wenn Bankdaten vollständig
9. kein QR-Code bei Barquittung
10. lange Patientennamen / Leistungsbezeichnungen brechen das Layout nicht
