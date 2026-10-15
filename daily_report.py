"""Täglicher Bericht: führt alle Suchaufträge aus profile.json aus und schreibt eine HTML-Datei.

Aufruf:  python daily_report.py            → data/bericht_JJJJ-MM-TT.html
         python daily_report.py --mail     → zusätzlich per E-Mail (SMTP-Zugang über Umgebungsvariablen)

Umgebungsvariablen für --mail: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASS, MAIL_FROM, MAIL_TO
Zeitplan: Windows Aufgabenplanung oder cron, z. B. täglich 07:00.
"""
from __future__ import annotations

import html
import json
import os
import smtplib
import sys
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

from ba_api import BAClient, web_url
from matching import excluded

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SEEN = DATA / "gesehen.json"


def main(send_mail: bool = False) -> Path:
    profil = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    DATA.mkdir(exist_ok=True)
    seen: dict[str, str] = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    client = BAClient()
    neu, bekannt, ausgeschlossen = [], [], []
    for auftrag in profil["suchauftraege"]:
        jobs, _ = client.search(was=auftrag["was"], wo=auftrag.get("wo", "Hannover"),
                                umkreis=auftrag.get("umkreis", 25), tage=auftrag.get("tage", 7), size=100)
        for j in jobs:
            d = j.to_dict()
            grund = excluded(d, profil)
            if grund:
                ausgeschlossen.append((d, grund))
                continue
            if j.refnr in seen:
                bekannt.append(d)
            else:
                neu.append(d)
                seen[j.refnr] = date.today().isoformat()
    client.close()
    # Dubletten über mehrere Suchaufträge entfernen
    uniq = {}
    for d in neu:
        uniq.setdefault(d["refnr"], d)
    neu = sorted(uniq.values(), key=lambda d: (d["entfernung_km"] if d["entfernung_km"] is not None else 999))
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")

    heute = date.today().strftime("%d.%m.%Y")
    rows = "".join(
        f"<li style='margin:0 0 12px'><a href='{web_url(d['refnr'])}'><strong>{html.escape(d['titel'])}</strong></a><br>"
        f"{html.escape(d['firma'])} · {html.escape(d['ort'])}"
        f"{' · ' + str(d['entfernung_km']) + ' km' if d['entfernung_km'] is not None else ''}"
        f" · {'Vollzeit' if d['vollzeit'] else 'Teilzeit'} · {html.escape(d['vertragsdauer'])}</li>"
        for d in neu) or "<li>Keine neuen Stellen.</li>"
    doc = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>Stellenbericht {heute}</title>
<body style="font-family:system-ui,sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#15181B">
<h1 style="font-size:22px">Stellenbericht {heute}</h1>
<p><strong>{len(neu)} neue Stellen</strong> · {len(set(d['refnr'] for d in bekannt))} bereits bekannt · {len(ausgeschlossen)} ausgeschlossen
(Zeitarbeit, Entfernung, Sperrliste)</p>
<p style="color:#555B62;font-size:14px">Suchaufträge: {html.escape(' | '.join(a['was'] + ' – ' + a.get('wo','Hannover') for a in profil['suchauftraege']))}<br>
Quelle: Jobsuche der Bundesagentur für Arbeit · erstellt {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
<ol style="padding-left:20px">{rows}</ol>
<p style="color:#555B62;font-size:13px">Ausgeschlossen: {html.escape(', '.join(sorted(set(d['firma'] + ' (' + g + ')' for d, g in ausgeschlossen))) or '–')}</p>
</body></html>"""
    out = DATA / f"bericht_{date.today().isoformat()}.html"
    out.write_text(doc, encoding="utf-8")
    print(f"{len(neu)} neue Stellen · Bericht: {out}")

    if send_mail:
        msg = EmailMessage()
        msg["Subject"] = f"Stellenbericht {heute}: {len(neu)} neue Stellen"
        msg["From"], msg["To"] = os.environ["MAIL_FROM"], os.environ["MAIL_TO"]
        msg.set_content(f"{len(neu)} neue Stellen. Bericht im HTML-Teil.")
        msg.add_alternative(doc, subtype="html")
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(msg)
        print("Bericht per E-Mail gesendet.")
    return out


if __name__ == "__main__":
    main(send_mail="--mail" in sys.argv)
