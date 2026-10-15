"""Web-App: Stellensuche über die Jobsuche-API der BA mit Profil-Abgleich.

Start:  uvicorn app:app --reload --port 8000   →  http://localhost:8000
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ba_api import BAClient, web_url
from matching import analyse, excluded

ROOT = Path(__file__).parent
PROFILE = ROOT / "profile.json"
SENT = ROOT / "data" / "beworben.json"

app = FastAPI(title="Bewerbungs-Assistent – Stellensuche")
client = BAClient()


def load_profile() -> dict[str, Any]:
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def load_sent() -> set[str]:
    if SENT.exists():
        return {e.get("refnr") for e in json.loads(SENT.read_text(encoding="utf-8"))} | \
               {(e.get("firma") or "").lower() for e in json.loads(SENT.read_text(encoding="utf-8"))}
    return set()


@app.get("/api/profile")
def api_profile() -> dict[str, Any]:
    return load_profile()


@app.get("/api/search")
def api_search(was: str = Query(..., min_length=2), wo: str = "Hannover", umkreis: int = 25,
               tage: int = 30, size: int = 50, page: int = 1, mit_ausgeschlossenen: bool = False) -> dict[str, Any]:
    profil = load_profile()
    try:
        jobs, total = client.search(was=was, wo=wo, umkreis=umkreis, tage=tage, size=size, page=page)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Jobsuche-API nicht erreichbar: {e}") from e
    already = load_sent()
    out, hidden = [], 0
    for j in jobs:
        d = j.to_dict()
        d["url"] = web_url(j.refnr)
        d["ausschluss"] = excluded(d, profil, already)
        if d["ausschluss"] and not mit_ausgeschlossenen:
            hidden += 1
            continue
        out.append(d)
    return {"treffer": out, "gesamt": total, "ausgeblendet": hidden, "page": page, "size": size}


@app.get("/api/job/{refnr}")
def api_job(refnr: str) -> dict[str, Any]:
    profil = load_profile()
    try:
        job = client.job_with_details(refnr)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Details nicht abrufbar: {e}") from e
    d = job.to_dict()
    d["url"] = web_url(refnr)
    d["abgleich"] = analyse(job.beschreibung, profil)
    return d


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
