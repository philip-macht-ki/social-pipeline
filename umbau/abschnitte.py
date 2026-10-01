#!/usr/bin/env python3
"""Schneidet aus einer Aufnahme die Vorlage master.mov und die Abschnitte für
den Umbau.

Erwartet abschnitte.json: eine Liste von {"name": "...", "von": 0.0, "bis": 0.0}
(Sekunden ab Videostart). Baut master.mov (1080x1920, 30 fps, Originalton) und
je Eintrag seg-<name>.mp4 (ohne Ton, für das Umbaumodell).

Aufruf: abschnitte.py eingang.mp4 arbeitsordner [--abschnitte abschnitte.json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def pruefen(abschnitte: list[dict]) -> None:
    """Prüft das Format von abschnitte.json, bevor irgendetwas geschnitten
    wird. Wirft ValueError mit einer verständlichen Meldung bei einem
    Formatfehler."""
    if not isinstance(abschnitte, list) or not abschnitte:
        raise ValueError("abschnitte.json muss eine nicht leere Liste sein.")
    namen: set[str] = set()
    for eintrag in abschnitte:
        if not isinstance(eintrag, dict):
            raise ValueError(f"Jeder Eintrag muss ein Objekt sein: {eintrag}")
        for feld in ("name", "von", "bis"):
            if feld not in eintrag:
                raise ValueError(f"Eintrag ohne Feld '{feld}': {eintrag}")
        if eintrag["name"] in namen:
            raise ValueError(f"Name mehrfach vergeben: {eintrag['name']}")
        namen.add(eintrag["name"])
        if isinstance(eintrag["von"], bool) or isinstance(eintrag["bis"], bool) or not isinstance(
            eintrag["von"], (int, float)
        ) or not isinstance(eintrag["bis"], (int, float)):
            raise ValueError(f"'von' und 'bis' müssen Zahlen sein: {eintrag}")
        if eintrag["bis"] <= eintrag["von"]:
            raise ValueError(f"'bis' muss größer als 'von' sein: {eintrag}")


def master_bauen(eingang: str, ziel: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", eingang,
            "-map", "0:v:0", "-map", "0:a:0",
            "-vf", "scale=1080:1920,fps=30,format=yuv420p",
            "-c:v", "libx264", "-crf", "12", "-c:a", "pcm_s16le", ziel,
        ],
        check=True,
    )


def abschnitt_schneiden(master: str, name: str, von: float, bis: float, ziel_ordner: str) -> str:
    ziel = os.path.join(ziel_ordner, f"seg-{name}.mp4")
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-ss", str(von), "-to", str(bis), "-i", master,
            "-an", "-c:v", "libx264", "-crf", "12", ziel,
        ],
        check=True,
    )
    return ziel


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("eingang")
    a.add_argument("arbeitsordner")
    a.add_argument("--abschnitte", default="abschnitte.json")
    x = a.parse_args()
    os.makedirs(x.arbeitsordner, exist_ok=True)
    pfad = x.abschnitte if os.path.isabs(x.abschnitte) else os.path.join(x.arbeitsordner, x.abschnitte)
    with open(pfad, encoding="utf-8") as f:
        abschnitte = json.load(f)
    try:
        pruefen(abschnitte)
    except ValueError as e:
        print("FEHLER", e, file=sys.stderr)
        sys.exit(1)
    master = os.path.join(x.arbeitsordner, "master.mov")
    print("Baue Vorlage", master)
    master_bauen(x.eingang, master)
    for eintrag in abschnitte:
        ziel = abschnitt_schneiden(master, eintrag["name"], eintrag["von"], eintrag["bis"], x.arbeitsordner)
        print("Abschnitt", eintrag["name"], "->", ziel)


if __name__ == "__main__":
    main()
