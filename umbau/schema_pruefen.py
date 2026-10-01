#!/usr/bin/env python3
"""Feldschema eines OpenRouter-Videomodells ermitteln, ohne einen Auftrag zu
starten, der Geld kostet.

OpenRouter ignoriert unbekannte Felder in einem Auftrag still und lässt ihn
trotzdem laufen. Ein neues Modell mit einem echten Aufruf auszuprobieren
("Probeaufruf") kostet darum im schlimmsten Fall ein rechnendes Video, obwohl
der Auftrag nie ankam. Dieses Werkzeug schickt stattdessen absichtlich einen
falschen Typ (duration als Text statt Zahl) und ein paar vermutete Felder mit
ebenfalls falschem Typ. Die Fehlermeldung des Dienstes nennt in aller Regel die
erwarteten Felder und Typen, ohne dass irgendein Video gerechnet wird.

Aufruf: schema_pruefen.py MODELLNAME
"""
from __future__ import annotations

import sys

import openrouter as orv

VERMUTETE_FELDER_FALSCHER_TYP: dict = {
    "duration": "kaputt",
    "size": 12345,
    "resolution": 12345,
    "aspect_ratio": 12345,
    "generate_audio": "kaputt",
}


def pruefen(modell: str) -> tuple[int, str]:
    body = {"model": modell, "prompt": "x", **VERMUTETE_FELDER_FALSCHER_TYP}
    status, antwort = orv.req("POST", "/videos", body)
    return status, antwort.decode(errors="replace")[:3000]


def main() -> None:
    if len(sys.argv) < 2:
        print("Aufruf: schema_pruefen.py MODELLNAME", file=sys.stderr)
        sys.exit(1)
    status, text = pruefen(sys.argv[1])
    print(status, text)


if __name__ == "__main__":
    main()
