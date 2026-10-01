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

# Ein "-fast"-Modell ist zum günstigen Testen da. Ohne ausdrückliche Angabe
# nimmt es automatisch 4 Sekunden in 720x1280 statt der teureren Standardwerte
# für den echten Clip (10 Sekunden, 1080x1920).
FAST_DAUER = 4
FAST_SIZE = "720x1280"
STANDARD_DAUER = 10
STANDARD_SIZE = "1080x1920"


def ist_fast_modell(modell: str) -> bool:
    return modell.endswith("-fast")


def standardwerte(modell: str) -> tuple[int, str]:
    """Liefert (Dauer, Größe), die gelten, wenn nichts ausdrücklich angegeben
    wurde: für ein "-fast"-Modell die günstigen Testwerte, sonst die
    Standardwerte für den echten Clip."""
    if ist_fast_modell(modell):
        return FAST_DAUER, FAST_SIZE
    return STANDARD_DAUER, STANDARD_SIZE


def erzeugen(
    bild: str,
    ziel: str,
    prompt: str,
    modell: str = STANDARD_MODELL,
    dauer: int | None = None,
    size: str | None = None,
) -> dict:
    auto_dauer, auto_size = standardwerte(modell)
    dauer = dauer if dauer is not None else auto_dauer
    size = size if size is not None else auto_size
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
    a.add_argument("--dauer", type=int, default=None, help="Standard: 10s, oder 4s bei einem -fast-Modell")
    a.add_argument("--modell", default=STANDARD_MODELL)
    a.add_argument("--size", default=None, help="Standard: 1080x1920, oder 720x1280 bei einem -fast-Modell")
    x = a.parse_args()
    try:
        erzeugen(x.bild, x.ziel, x.prompt, x.modell, x.dauer, x.size)
    except Exception as e:
        print("FEHLER", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
