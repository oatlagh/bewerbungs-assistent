"""Abgleich Stellenbeschreibung ↔ Profil.

Grundregel: Was das Profil nicht belegt, wird nie behauptet. Jede Anforderung
bekommt einen Status: belegt / teilweise / nicht belegt, plus den Beleg aus dem Profil.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

KANN_MARKER = ("wünschenswert", "wuenschenswert", "von vorteil", "idealerweise", "gerne", "gern gesehen",
               "plus", "optional", "nice to have", "bevorzugt", "vorteilhaft", "schön wenn", "ideal")
SECTION_START = re.compile(
    r"^\s*(#+\s*)?(\*\*)?\s*(ihr profil|dein profil|das bringst du mit|das bringen sie mit|was du mitbringst|"
    r"was sie mitbringen|anforderungen|voraussetzungen|qualifikation|wir erwarten|das erwarten wir|"
    r"was für uns zählt|was wir uns wünschen|sie bringen mit|du bringst mit|profil)\b", re.I)
SECTION_END = re.compile(
    r"^\s*(#+\s*)?(\*\*)?\s*(wir bieten|das bieten wir|unser angebot|benefits|ihre vorteile|deine vorteile|"
    r"kontakt|bewerbung|ansprechpartner|über uns|ueber uns|das erwartet dich|ihre aufgaben|deine aufgaben|aufgaben)\b", re.I)
BULLET = re.compile(r"^\s*([-*•▪·]|\d+[.)])\s+(.*)$")


@dataclass
class Requirement:
    text: str
    muss: bool
    status: str          # "belegt" | "teilweise" | "nicht_belegt"
    beleg: str           # Profilbeleg oder Hinweis
    kenntnis: str | None


def extract_requirements(beschreibung: str) -> list[Requirement]:
    """Zieht Anforderungs-Zeilen aus dem Markdown-/Fließtext der Anzeige."""
    lines = beschreibung.replace("\r", "").split("\n")
    in_sec = False
    found: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if SECTION_START.search(line) and len(line) < 80:
            in_sec = True
            continue
        if in_sec and SECTION_END.search(line) and len(line) < 80:
            in_sec = False
            continue
        if in_sec:
            m = BULLET.match(line)
            txt = (m.group(2) if m else line).strip("*_ ").strip()
            if 8 <= len(txt) <= 220:
                found.append(txt)
    if not found:
        # Fallback: alle Aufzählungspunkte, die wie Anforderungen klingen
        for raw in lines:
            m = BULLET.match(raw.strip())
            if m:
                txt = m.group(2).strip("*_ ").strip()
                if re.search(r"(ausbildung|erfahrung|kenntnis|sicher|umgang|abgeschlossen|studium|führerschein|fuehrerschein)", txt, re.I):
                    found.append(txt)
    # Dubletten entfernen, Reihenfolge behalten
    seen, out = set(), []
    for t in found:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return [Requirement(text=t, muss=not any(k in t.lower() for k in KANN_MARKER), status="nicht_belegt", beleg="", kenntnis=None) for t in out]


def match(requirements: list[Requirement], profil: dict[str, Any]) -> list[Requirement]:
    kenntnisse = profil.get("kenntnisse", [])
    nicht = [w.lower() for w in profil.get("nicht_belegt_hinweise", [])]
    for r in requirements:
        low = r.text.lower()
        hits = []
        for k in kenntnisse:
            aliase = [a.lower() for a in k.get("aliase", [])] + [k["name"].lower()]
            n = sum(1 for a in aliase if a and a in low)
            if n:
                hits.append((n, k))
        hard_miss = any(w in low for w in nicht)
        fragt_abschluss = re.search(r"(ausbildung|abgeschlossen|studium|techniker|meister)", low)
        if fragt_abschluss and not profil.get("ausbildung"):
            r.status = "teilweise"
            r.beleg = "Abschluss im Profil nicht hinterlegt – bitte im Profil ergänzen (Feld „ausbildung“)"
            r.kenntnis = hits[0][1]["name"] if hits else None
            continue
        if hits and not hard_miss:
            hits.sort(key=lambda x: -x[0])
            best = hits[0][1]
            r.status = "belegt"
            r.beleg = best["beleg"]
            r.kenntnis = best["name"]
        elif hits and hard_miss:
            best = hits[0][1]
            r.status = "teilweise"
            r.beleg = f"Teilweise: {best['beleg']} – der genannte Punkt selbst ist im Profil nicht belegt"
            r.kenntnis = best["name"]
        else:
            r.status = "nicht_belegt"
            r.beleg = "Nicht im Profil – wird im Anschreiben nicht behauptet"
    return requirements


def score(reqs: list[Requirement]) -> dict[str, Any]:
    muss = [r for r in reqs if r.muss]
    kann = [r for r in reqs if not r.muss]
    def cnt(rs, st): return sum(1 for r in rs if r.status == st)
    muss_full, muss_part = cnt(muss, "belegt"), cnt(muss, "teilweise")
    fit = (muss_full + 0.5 * muss_part) / len(muss) if muss else None
    return {
        "muss_gesamt": len(muss), "muss_belegt": muss_full, "muss_teilweise": muss_part,
        "kann_gesamt": len(kann), "kann_belegt": cnt(kann, "belegt"),
        "passung": round(fit * 100) if fit is not None else None,
        "text": (f"{muss_full} von {len(muss)} Muss-Anforderungen belegt" + (f" · {muss_part} teilweise" if muss_part else "")) if muss else "Keine Anforderungen erkannt – bitte Anzeige lesen",
    }


def analyse(beschreibung: str, profil: dict[str, Any]) -> dict[str, Any]:
    reqs = match(extract_requirements(beschreibung), profil)
    return {"anforderungen": [asdict(r) for r in reqs], "bewertung": score(reqs)}


def excluded(job: dict[str, Any], profil: dict[str, Any], already: set[str] | None = None) -> str | None:
    """Gibt den Ausschlussgrund zurück oder None."""
    ex = profil.get("ausschluesse", {})
    if ex.get("zeitarbeit") and job.get("zeitarbeit"):
        return "Zeitarbeit"
    if ex.get("befristet") and job.get("vertragsdauer") == "befristet":
        return "Befristet"
    km = job.get("entfernung_km")
    if ex.get("max_km") and km is not None and km > ex["max_km"]:
        return f"Über {ex['max_km']} km"
    firma = (job.get("firma") or "").lower()
    for sperr in ex.get("firmen_sperrliste", []):
        if sperr.lower() in firma:
            return "Firma gesperrt"
    if already and (job.get("refnr") in already or firma in already):
        return "Bereits beworben"
    return None
