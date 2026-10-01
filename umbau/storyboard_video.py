#!/usr/bin/env python3
"""Storyboard-Bild zu Video mit bytedance/seedance-2.0 über OpenRouter.

Für Clips ohne eigene Aufnahme: ein Storyboard (zum Beispiel 2 Spalten x 5
Zeilen, ein Feld je Sekunde) wird als Referenzbild mitgeschickt, Seedance setzt
es Feld für Feld in Video um. Seedance lehnt echte Gesichter ab (Schutz gegen
Deepfakes); für eine Aufnahme mit dem eigenen Gesicht gehört umbauen.py, nicht
dieses Werkzeug.

Aufruf: storyboard_video.py storyboard.png ziel.mp4 "prompt" [--dauer 10]
        [--modell bytedance/seedance-2.0-fast] [--size 1080x1920]
"""
from __future__ import annotations

import argparse
import json
import sys

from hochladen import kurzlebiger_link
import openrouter as orv

STANDARD_MODELL = "bytedance/seedance-2.0"


def erzeugen(
    bild: str,
    ziel: str,
    prompt: str,
    modell: str = STANDARD_MODELL,
    dauer: int = 10,
    size: str = "1080x1920",
) -> dict:
    with kurzlebiger_link(bild) as url:
        status, antwort = orv.req(
            "POST",
            "/videos",
            {
                "model": modell,
                "prompt": prompt,
                "duration": dauer,
                "size": size,
                "generate_audio": False,
                "input_references": [{"type": "image_url", "image_url": {"url": url}}],
            },
        )
        if status >= 300:
            raise RuntimeError(f"FEHLER {status}: {antwort.decode(errors='replace')[:800]}")
        auftrag = json.loads(antwort)
        auftrag_id = auftrag.get("id") or auftrag.get("data", {}).get("id")
        print("Auftrag", auftrag_id, flush=True)
        ergebnis = orv.warten(auftrag_id, intervall=15)
        orv.laden(auftrag_id, ziel)
        print("OK", ziel, "Kosten:", ergebnis.get("usage") or ergebnis.get("cost"))
        return ergebnis


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("bild")
    a.add_argument("ziel")
    a.add_argument("prompt")
    a.add_argument("--dauer", type=int, default=10)
    a.add_argument("--modell", default=STANDARD_MODELL)
    a.add_argument("--size", default="1080x1920")
    x = a.parse_args()
    try:
        erzeugen(x.bild, x.ziel, x.prompt, x.modell, x.dauer, x.size)
    except Exception as e:
        print("FEHLER", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
