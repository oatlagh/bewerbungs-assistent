# Bewerbungs-Assistent – Schritt 2: echte Stellensuche

Prototyp der Stellensuche mit der **Jobsuche-API der Bundesagentur für Arbeit** und Abgleich
der Anforderungen mit deinem Profil (Muss/Kann, belegt/teilweise/nicht belegt).

## Start (Windows, macOS, Linux)

```bash
cd bewerbungs-assistent
python -m venv .venv
.venv\Scripts\activate          # Windows   |   source .venv/bin/activate  (macOS/Linux)
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Dann im Browser: <http://localhost:8000>

Kein API-Schlüssel nötig. Die Jobsuche-API ist öffentlich und wird mit dem festen Header
`X-API-Key: jobboerse-jobsuche` angesprochen (gleicher Schlüssel wie die Jobsuche-Webseite).

## Täglicher Bericht

```bash
python daily_report.py          # schreibt data/bericht_JJJJ-MM-TT.html, merkt sich gesehene Stellen
python daily_report.py --mail   # zusätzlich per E-Mail (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM, MAIL_TO)
```

Zeitplan: Windows „Aufgabenplanung“ oder `cron`, z. B. täglich 07:00.

## Dateien

| Datei | Zweck |
|---|---|
| `ba_api.py` | API-Client: Suche (`pc/v6/jobs`), Details (`pc/v4/jobdetails/{base64(refnr)}`), Normalisierung |
| `matching.py` | Anforderungen aus der Anzeige ziehen, Muss/Kann trennen, mit Profil abgleichen, Ausschlüsse |
| `profile.json` | Dein Profil: Suchaufträge, Ausschlüsse, Kenntnisse mit Belegen und Suchwörtern |
| `app.py` | Web-Server (FastAPI) mit `/api/search` und `/api/job/{refnr}` |
| `static/index.html` | Oberfläche (Suche, Trefferliste, Detail mit Abgleich) |
| `daily_report.py` | Täglicher Bericht als HTML, optional per Mail |
| `data/` | Berichte, `gesehen.json`, später `beworben.json` |

## Profil pflegen (`profile.json`)

- `kenntnisse[]`: `name`, `beleg` (der Satz, der später im Anschreiben stehen darf) und `aliase`
  (Wörter, an denen eine Anforderung erkannt wird). Nur was hier steht, gilt als belegt.
- `ausbildung`: leer lassen, bis der Abschluss feststeht. Solange gilt jede Abschluss-Anforderung als „teilweise“.
- `nicht_belegt_hinweise`: Begriffe, die nie als belegt gelten (z. B. EPLAN, Revit, Führerschein).
- `ausschluesse`: Zeitarbeit, befristet, `max_km`, `firmen_sperrliste`.

## Was die API liefert (geprüft am 15.10.2026)

- Trefferliste: Titel, Firma, Ort/PLZ, Entfernung in km, Veröffentlichungsdatum, Vollzeit/Teilzeit,
  Vertragsdauer, teils Gehaltsspanne. Kein Zeitarbeits-Flag pro Treffer, daher Heuristik über den Firmennamen.
- Details: vollständige Beschreibung (Markdown). Kontaktdaten/E-Mail sind nicht immer enthalten;
  dann führt „Originalanzeige öffnen“ zur Anzeige auf arbeitsagentur.de.
- Suchbegriffe: exakte Phrasen finden wenig („Technischer Zeichner Elektrotechnik“: 1 Treffer).
  Besser mehrere kürzere Suchaufträge: „Technischer Zeichner“ (15), „Technischer Systemplaner Elektrotechnik“ (6),
  „CAD Elektrotechnik“ (32) – Stand 15.10.2026, Hannover + 25 km, letzte 30 Tage.

## Nächste Schritte

3. Lebenslauf einlesen (PDF/DOCX) und `profile.json` daraus vorbefüllen
4. Anschreiben-Generator (nur belegte Angaben, drei Tonlagen)
5. Bewerbungsmappe als PDF, Versand über eigenes Postfach, Verlauf (`data/beworben.json`)
6. Autopilot mit Freigabe-Warteschlange
