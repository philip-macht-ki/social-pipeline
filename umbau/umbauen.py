#!/usr/bin/env python3
"""Echte Aufnahme per KI umbauen (Standardmodell: black-forest-labs/flux-video-edit
über OpenRouter).

Aufruf: umbauen.py eingang.mp4 ziel.mp4 "prompt" [--modell runway/aleph-2] [--dauer 10]

Schickt NIE resolution oder aspect_ratio mit: flux-video-edit lehnt beide
Felder ab und übernimmt Format und Länge der Eingabe von selbst. Bei einer
503-Antwort (Dienst überlastet) wird bis zu vier Mal im Abstand von 30
Sekunden wiederholt. Lehnt der Dienst den Auftrag wegen Moderation ab (zum
Beispiel bei Marken- oder Werknamen im Prompt), wird das klar gemeldet statt
als gewöhnlicher Fehler durchgereicht.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from hochladen import kurzlebiger_link
import openrouter as orv

STANDARD_MODELL = "black-forest-labs/flux-video-edit"
WARTE_SEKUNDEN = 30
VERSUCHE = 4

MODERATIONS_HINWEIS = (
    "Der Auftrag wurde wegen Moderation abgelehnt. Vermutlich stand ein "
    "Marken- oder Werkname im Auftrag (zum Beispiel 'wie in Harry Potter'). "
    "Keine Marken- oder Werknamen im Auftrag, stattdessen beschreiben."
)


def ist_moderationsablehnung(text: str) -> bool:
    text = text.lower()
    return any(
        wort in text
        for wort in ("moderation", "protected content", "content_policy", "policy_violation")
    )


def starten(url: str, prompt: str, modell: str, dauer: int | None) -> dict:
    body: dict = {
        "model": modell,
        "prompt": prompt,
        "input_references": [{"type": "video_url", "video_url": {"url": url}}],
    }
    if dauer:
        body["duration"] = dauer
    for versuch in range(1, VERSUCHE + 1):
        status, antwort = orv.req("POST", "/videos", body)
        if status == 503:
            if versuch == VERSUCHE:
                raise RuntimeError("Dienst nach mehreren Versuchen weiter überlastet (503).")
            print(f"503 über Kapazität, Versuch {versuch}/{VERSUCHE}, warte {WARTE_SEKUNDEN}s …", flush=True)
            time.sleep(WARTE_SEKUNDEN)
            continue
        if status >= 300:
            text = antwort.decode(errors="replace")
            if ist_moderationsablehnung(text):
                raise RuntimeError(MODERATIONS_HINWEIS + f"\nAntwort: {text[:500]}")
            raise RuntimeError(f"FEHLER {status}: {text[:800]}")
        return json.loads(antwort)
    raise RuntimeError("Unerwarteter Zustand beim Starten des Auftrags.")


def umbauen(eingang: str, ziel: str, prompt: str, modell: str = STANDARD_MODELL, dauer: int | None = None) -> dict:
    with kurzlebiger_link(eingang) as url:
        auftrag = starten(url, prompt, modell, dauer)
        auftrag_id = auftrag.get("id") or auftrag.get("data", {}).get("id")
        print("Auftrag", auftrag_id, flush=True)
        ergebnis = orv.warten(auftrag_id)
        orv.laden(auftrag_id, ziel)
        print("OK", ziel, "Kosten:", ergebnis.get("usage") or ergebnis.get("cost"))
        return ergebnis


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("eingang")
    a.add_argument("ziel")
    a.add_argument("prompt")
    a.add_argument("--modell", default=STANDARD_MODELL)
    a.add_argument("--dauer", type=int, default=None)
    x = a.parse_args()
    try:
        umbauen(x.eingang, x.ziel, x.prompt, x.modell, x.dauer)
    except Exception as e:
        print("FEHLER", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
