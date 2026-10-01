#!/usr/bin/env python3
"""Zugriff auf die OpenRouter-Videoschnittstelle.

Der Schlüssel kommt aus der Umgebungsvariable OPENROUTER_API_KEY, sonst aus dem
macOS-Schlüsselbund (Eintrag "openrouter-api-key"). Er wird nie ausgegeben,
auch nicht in Fehlermeldungen.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

BASIS = "https://openrouter.ai/api/v1"

ENDZUSTAENDE_OK = ("completed", "succeeded", "success")
ENDZUSTAENDE_FEHLER = ("failed", "error", "cancelled")


def schluessel() -> str:
    """Liefert den OpenRouter-Schlüssel. Nie den Wert selbst in eine
    Fehlermeldung oder einen Log schreiben."""
    wert = os.environ.get("OPENROUTER_API_KEY")
    if wert:
        return wert
    out = subprocess.run(
        ["security", "find-generic-password", "-s", "openrouter-api-key", "-w"],
        capture_output=True, text=True,
    )
    wert = out.stdout.strip()
    if not wert:
        raise RuntimeError(
            "Kein OpenRouter-Schlüssel gefunden. Setz OPENROUTER_API_KEY oder "
            "leg ihn im Schlüsselbund unter 'openrouter-api-key' ab."
        )
    return wert


def req(method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
    """Ein Aufruf an die OpenRouter-API. Gibt (Statuscode, Rohantwort) zurück,
    auch bei einem Fehlerstatus, statt eine Ausnahme zu werfen."""
    daten = json.dumps(body).encode() if body is not None else None
    anfrage = urllib.request.Request(
        BASIS + path,
        data=daten,
        method=method,
        headers={"Authorization": "Bearer " + schluessel(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=120) as f:
            return f.status, f.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def warten(auftrag_id: str, intervall: int = 10, timeout: int = 1800) -> dict:
    """Fragt einen Videoauftrag ab, bis er fertig, fehlgeschlagen oder nach
    `timeout` Sekunden noch immer nicht fertig ist."""
    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"Auftrag {auftrag_id} nach {timeout}s nicht fertig.")
        time.sleep(intervall)
        status, body = req("GET", f"/videos/{auftrag_id}")
        d = json.loads(body)
        st = d.get("status") or d.get("data", {}).get("status")
        if st in ENDZUSTAENDE_OK:
            return d
        if st in ENDZUSTAENDE_FEHLER:
            raise RuntimeError(f"Auftrag {auftrag_id} fehlgeschlagen: {json.dumps(d)[:800]}")


def laden(auftrag_id: str, ziel: str, index: int = 0) -> None:
    """Lädt das fertige Ergebnis eines Auftrags in `ziel`."""
    anfrage = urllib.request.Request(
        f"{BASIS}/videos/{auftrag_id}/content?index={index}",
        headers={"Authorization": "Bearer " + schluessel()},
    )
    with urllib.request.urlopen(anfrage, timeout=300) as f, open(ziel, "wb") as o:
        o.write(f.read())
