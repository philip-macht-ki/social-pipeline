"""Der ganze Lauf in fester Reihenfolge: uv run pipeline tag [--echt]

Jeder Schritt wird einzeln abgefangen. Scheitert einer, laufen die anderen
weiter, und am Ende steht eine Übersicht, was geklappt hat.

Zwei Lehren aus dem Vorbild stecken in der Reihenfolge:
- Erst planen, was schon fertig ist, dann bauen. Am 28.09.2026 riss ein
  Stundenlauf beim Bauen an der Zeitgrenze ab, und vier fertige Reels blieben
  ungeplant liegen, weil das Planen erst danach kam.
- Eine Gesamtzeitgrenze statt endlos laufen. Ist sie erreicht, hört der Lauf
  nach dem aktuellen Schritt sauber auf; posten und vorrat laufen trotzdem.
"""
from __future__ import annotations

import argparse
import importlib
import time
import traceback

from .kern import Sperre, konfig, log

SCHRITTE = [
    ("eingang", "rohmaterial", "befehl_eingang", False),
    ("transkript", "transkript", "befehl", False),
    ("zerlegen", "zerlegen", "befehl", False),
    ("hook", "hook", "befehl", False),
    ("planen (vorab)", "plan", "befehl_planen", True),
    ("bauen", "video", "befehl_bauen", False),
    ("fassungen", "video", "befehl_fassungen", False),
    ("texte", "texte", "befehl", False),
    ("bilder", "stile", "befehl", False),
    ("planen", "plan", "befehl_planen", True),
    ("posten", "posten", "befehl", True),
    ("vorrat", "betrieb", "befehl_vorrat", True),
]


def _args(vorlage: argparse.Namespace) -> argparse.Namespace:
    """Jeder Schritt bekommt dieselben Schalter, aber kein Ziel: er nimmt alles Offene."""
    return argparse.Namespace(
        befehl="tag", ziel=[], neu=False, echt=vorlage.echt, alle=False,
        kanal=None, tage=None, trocken=False,
    )


def befehl(args) -> int:
    grenze = konfig("pipeline").get("gesamtzeit_minuten", 50) * 60
    start = time.time()
    uebersicht: list[tuple[str, str]] = []
    try:
        sperre = Sperre()
        sperre.__enter__()
    except RuntimeError as e:
        log(f"nichts: {e}")
        return 0
    try:
        log(f"Tageslauf beginnt ({'echt' if args.echt else 'trocken'})")
        for name, modul, funktion, immer in SCHRITTE:
            if time.time() - start > grenze and not immer:
                uebersicht.append((name, "übersprungen, Zeitgrenze erreicht"))
                continue
            t0 = time.time()
            try:
                mod = importlib.import_module(f"pipeline.{modul}")
                code = int(getattr(mod, funktion)(_args(args)) or 0)
                zustand = "ok" if code == 0 else ("Lücken" if code == 3 else f"Exit {code}")
            except Exception as e:  # ein Schritt reißt die anderen nicht mit
                zustand = f"fehler: {e}"
                log(f"fehler in {name}: {e}\n{traceback.format_exc(limit=3)}")
            uebersicht.append((name, f"{zustand} ({time.time() - t0:.0f} s)"))
        log("Tageslauf fertig:")
        for name, zustand in uebersicht:
            log(f"  {name:16} {zustand}")
        return 1 if any(z.startswith("fehler") for _, z in uebersicht) else 0
    finally:
        sperre.__exit__()
