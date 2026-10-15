"""Client für die Jobsuche-API der Bundesagentur für Arbeit.

Verifiziert am 15.10.2026:
- Suche:   GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
- Details: GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{base64(referenznummer)}
- Header:  X-API-Key: jobboerse-jobsuche  (öffentlicher Schlüssel der Jobsuche-Webseite)

Die Antwort der Suche liegt unter "ergebnisliste", die Trefferzahl unter "maxErgebnisse".
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/"
HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "bewerbungs-assistent/0.1"}

VERTRAGSDAUER = {
    "UNBEFRISTET": "unbefristet",
    "BEFRISTET": "befristet",
    "KEINE_ANGABE": "keine Angabe",
}


@dataclass
class Job:
    refnr: str
    titel: str
    firma: str
    ort: str
    plz: str
    entfernung_km: int | None
    veroeffentlicht: str
    vollzeit: bool
    vertragsdauer: str
    zeitarbeit: bool
    beruf: str
    gehalt_von: int | None = None
    gehalt_bis: int | None = None
    externe_url: str | None = None
    beschreibung: str = ""
    kontakt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _loc(hit: dict[str, Any]) -> tuple[str, str]:
    loks = hit.get("stellenlokationen") or []
    if loks and loks[0].get("adresse"):
        a = loks[0]["adresse"]
        return a.get("ort", ""), a.get("plz", "")
    return hit.get("arbeitsort", {}).get("ort", "") if isinstance(hit.get("arbeitsort"), dict) else "", ""


def normalize(hit: dict[str, Any]) -> Job:
    ort, plz = _loc(hit)
    firma = hit.get("firma") or hit.get("arbeitgeber") or ""
    return Job(
        refnr=hit.get("referenznummer") or hit.get("refnr") or "",
        titel=hit.get("stellenangebotsTitel") or hit.get("titel") or "",
        firma=firma,
        ort=ort,
        plz=plz,
        entfernung_km=hit.get("entfernung"),
        veroeffentlicht=hit.get("datumErsteVeroeffentlichung") or hit.get("aktuelleVeroeffentlichungsdatum") or "",
        vollzeit=bool(hit.get("arbeitszeitVollzeit")),
        vertragsdauer=VERTRAGSDAUER.get(hit.get("vertragsdauer", ""), hit.get("vertragsdauer", "") or "keine Angabe"),
        zeitarbeit=_looks_like_zeitarbeit(firma, hit),
        beruf=hit.get("hauptberuf") or "",
        gehalt_von=hit.get("gehaltsspanneVon"),
        gehalt_bis=hit.get("gehaltsspanneBis"),
        externe_url=hit.get("externeUrl"),
    )


ZEITARBEIT_WORTE = ("zeitarbeit", "personaldienst", "personalservice", "personalmanagement", "persona service",
                    "personalfinder", "hr gmbh", "arbeitnehmerüberlassung", "zag ", "randstad", "adecco", "manpower",
                    "hays", "ferchau", "brunel", "tempton", "orizon", "piening", "avanti", "job meets life")


def _looks_like_zeitarbeit(firma: str, hit: dict[str, Any]) -> bool:
    """Die API liefert in der Trefferliste kein Zeitarbeits-Flag pro Stelle, nur als Facette.
    Deshalb eine Heuristik über den Firmennamen; im Detail kann der Nutzer die Firma sperren."""
    f = firma.lower()
    return any(w in f for w in ZEITARBEIT_WORTE)


class BAClient:
    def __init__(self, timeout: float = 20.0):
        self._c = httpx.Client(base_url=BASE, headers=HEADERS, timeout=timeout)

    def search(self, was: str, wo: str = "Hannover", umkreis: int = 25, tage: int = 30,
               page: int = 1, size: int = 50, arbeitszeit: str | None = None,
               befristung: str | None = None, zeitarbeit: bool | None = None) -> tuple[list[Job], int]:
        params: dict[str, Any] = {
            "was": was, "wo": wo, "umkreis": umkreis, "veroeffentlichtseit": tage,
            "page": page, "size": size, "angebotsart": 1,
        }
        if arbeitszeit:
            params["arbeitszeit"] = arbeitszeit  # vz;tz;snw;ho;mj
        if befristung:
            params["befristung"] = befristung    # 1 befristet, 2 unbefristet
        if zeitarbeit is not None:
            params["zeitarbeit"] = "true" if zeitarbeit else "false"
        r = self._c.get("pc/v6/jobs", params=params)
        r.raise_for_status()
        data = r.json()
        hits = data.get("ergebnisliste") or data.get("stellenangebote") or []
        return [normalize(h) for h in hits], int(data.get("maxErgebnisse", len(hits)))

    def details(self, refnr: str) -> dict[str, Any]:
        code = base64.b64encode(refnr.encode()).decode()
        r = self._c.get(f"pc/v4/jobdetails/{code}")
        r.raise_for_status()
        return r.json()

    def job_with_details(self, refnr: str) -> Job:
        d = self.details(refnr)
        job = normalize(d)
        job.beschreibung = d.get("stellenangebotsBeschreibung") or ""
        job.kontakt = {
            "email": d.get("bewerbungsEmail") or (d.get("bewerbung") or {}).get("email") if isinstance(d.get("bewerbung"), dict) else d.get("bewerbungsEmail"),
            "url": d.get("externeUrl") or (d.get("bewerbung") or {}).get("url") if isinstance(d.get("bewerbung"), dict) else d.get("externeUrl"),
            "ansprechpartner": d.get("ansprechpartner") or d.get("arbeitgeberAnsprechpartner"),
            "adresse": (d.get("stellenlokationen") or [{}])[0].get("adresse"),
        }
        return job

    def close(self) -> None:
        self._c.close()


def web_url(refnr: str) -> str:
    """Link zur Anzeige auf arbeitsagentur.de."""
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
