#!/usr/bin/env python3
"""Instrumentalmusik über ElevenLabs Music erzeugen (eigene Erzeugung, keine
Rechteprobleme mit fremder Musik).

Schlüssel aus der Umgebungsvariable ELEVENLABS_API_KEY, sonst aus dem
macOS-Schlüsselbund (Eintrag "elevenlabs-api-key"). Bei 429 (zu viele
Anfragen) wird bis zu sechs Mal im Abstand von 20 Sekunden wiederholt.

Aufruf: musik.py ziel.mp3 sekunden "prompt"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

VERSUCHE = 6
WARTE_SEKUNDEN = 20


def schluessel() -> str:
    """Liefert den ElevenLabs-Schlüssel. Nie den Wert selbst in eine
    Fehlermeldung oder einen Log schreiben."""
    wert = os.environ.get("ELEVENLABS_API_KEY")
    if wert:
        return wert
    out = subprocess.run(
        ["security", "find-generic-password", "-s", "elevenlabs-api-key", "-w"],
        capture_output=True, text=True,
    )
    wert = out.stdout.strip()
    if not wert:
        raise RuntimeError(
            "Kein ElevenLabs-Schlüssel gefunden. Setz ELEVENLABS_API_KEY oder "
            "leg ihn im Schlüsselbund unter 'elevenlabs-api-key' ab."
        )
    return wert


def erzeugen(ziel: str, sekunden: float, prompt: str) -> None:
    body = {
        "prompt": prompt,
        "music_length_ms": int(sekunden * 1000),
        "force_instrumental": True,
        "model_id": "music_v1",
    }
    daten = json.dumps(body).encode()
    for versuch in range(1, VERSUCHE + 1):
        anfrage = urllib.request.Request(
            "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192",
            data=daten,
            headers={"xi-api-key": schluessel(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=300) as f, open(ziel, "wb") as o:
                o.write(f.read())
            print("OK", ziel)
            return
        except urllib.error.HTTPError as e:
            if e.code == 429 and versuch < VERSUCHE:
                print(f"429 zu viele Anfragen, Versuch {versuch}/{VERSUCHE}, warte {WARTE_SEKUNDEN}s …", flush=True)
                time.sleep(WARTE_SEKUNDEN)
                continue
            print("FEHLER", e.code, e.read().decode(errors="replace")[:600])
            sys.exit(1)


def main() -> None:
    if len(sys.argv) < 4:
        print('Aufruf: musik.py ziel.mp3 sekunden "prompt"', file=sys.stderr)
        sys.exit(1)
    ziel, sekunden, prompt = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    erzeugen(ziel, sekunden, prompt)


if __name__ == "__main__":
    main()
