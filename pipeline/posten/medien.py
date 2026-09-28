"""Stellt Instagram-Dateien kurz öffentlich bereit, für die Container-API.

Instagram lädt die Datei asynchron von der gegebenen URL, nicht als Upload.
Zwei Wege stehen in konfig/kanaele.toml unter [instagram].medien_weg:
"supabase" (eigener Storage-Bucket) oder "basis_url" (eigener Webordner).
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import requests

from ..kern import jetzt, konfig

# Instagram braucht den passenden Content-Type, um Video und Bild zu erkennen.
CONTENT_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _content_type(datei: Path) -> str:
    return CONTENT_TYPES.get(datei.suffix.lower(), "application/octet-stream")


def _eindeutiger_name(datei: Path) -> str:
    """Zeitstempel vor den Namen, damit kein älterer Beitrag dieselbe Datei
    überschreibt, während Instagram sie noch lädt (Falle aus dem Vorbild:
    ein Container liest eine Datei, die im selben Moment neu geschrieben
    wird, und bekommt ein falsches oder halbes Video)."""
    return f"{jetzt():%Y%m%d-%H%M%S}-{datei.name}"


def _supabase_bereitstellen(datei: Path, cfg: dict) -> tuple[str, callable]:
    name = _eindeutiger_name(datei)
    bucket = cfg.get("bucket", "medien")
    basis = os.environ["SUPABASE_URL"].rstrip("/")
    hochladen_url = f"{basis}/storage/v1/object/{bucket}/{name}"
    oeffentliche_url = f"{basis}/storage/v1/object/public/{bucket}/{name}"
    kopf = {
        "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_KEY"],
        "Content-Type": _content_type(datei),
        # x-upsert erlaubt das Überschreiben eines gleichnamigen Objekts. Der
        # eindeutige Name oben macht das eigentlich unnötig, aber ein zweiter
        # Lauf mit derselben Sekunde soll trotzdem nicht mit 409 scheitern.
        "x-upsert": "true",
    }
    antwort = requests.post(hochladen_url, headers=kopf, data=datei.read_bytes(), timeout=300)
    antwort.raise_for_status()

    def aufraeumen() -> None:
        requests.delete(hochladen_url, headers={"Authorization": kopf["Authorization"]}, timeout=60)

    return oeffentliche_url, aufraeumen


def _ordner_bereitstellen(datei: Path, cfg: dict) -> tuple[str, callable]:
    ziel_ordner = Path(cfg.get("medien_ordner", "arbeit/oeffentlich"))
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    name = _eindeutiger_name(datei)
    ziel = ziel_ordner / name
    shutil.copy2(datei, ziel)
    url = cfg.get("basis_url", "").rstrip("/") + "/" + name
    for _ in range(60):
        try:
            r = requests.get(url, headers={"Range": f"bytes={max(0, ziel.stat().st_size - 1)}-"}, timeout=10)
            if r.status_code in (200, 206):
                return url, lambda: ziel.unlink(missing_ok=True)
        except requests.RequestException:
            pass
        time.sleep(5)
    raise RuntimeError("Öffentliche Medienadresse war nach fünf Minuten nicht vollständig erreichbar.")


def bereitstellen(datei: str) -> tuple[str, callable]:
    """Gibt (öffentliche_url, aufraeumen) zurück. aufraeumen() nach dem Senden aufrufen."""
    cfg = konfig("kanaele")["instagram"]
    pfad_datei = Path(datei)
    if cfg.get("medien_weg") == "supabase":
        return _supabase_bereitstellen(pfad_datei, cfg)
    return _ordner_bereitstellen(pfad_datei, cfg)
