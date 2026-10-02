"""Zieht ungenaue Wortanfänge mit dem Ton aus dem Rohschnitt nach."""
from __future__ import annotations

import math
import subprocess
from array import array
from pathlib import Path

from .kern import Ergebnis, konfig, lesen, schreiben

FENSTER_S = 0.01
RATE = 16_000


def _pegel(roh: Path) -> list[float]:
    """Liest 16-kHz-Mono-PCM und misst RMS in 10-ms-Fenstern."""
    lauf = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(roh), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
        capture_output=True,
    )
    if lauf.returncode:
        fehler = lauf.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg konnte Ton nicht lesen: {fehler}")
    werte = array("h")
    werte.frombytes(lauf.stdout)
    pro_fenster = int(RATE * FENSTER_S)
    return [math.sqrt(sum(w * w for w in werte[i:i + pro_fenster]) / pro_fenster)
            for i in range(0, len(werte) - pro_fenster + 1, pro_fenster)]


def _perzentil(werte: list[float], anteil: float) -> float:
    if not werte:
        return 0.0
    sortiert = sorted(werte)
    return sortiert[min(len(sortiert) - 1, int((len(sortiert) - 1) * anteil))]


def _einsatz(pegel: list[float], start: float, ende: float, schwelle: float) -> float | None:
    von = max(0, math.ceil(start / FENSTER_S))
    bis = min(len(pegel), math.floor(ende / FENSTER_S) + 1)
    for nr in range(von, bis):
        if pegel[nr] >= schwelle:
            return round(nr * FENSTER_S, 3)
    return None


def nachziehen(ordner: Path) -> Ergebnis:
    """Korrigiert Wortanfänge nach Pausen ab 0,25 s, sofern der Schalter aktiv ist.

    Die Schwelle ist 20 Prozent des 95. Perzentils. Das passt sie an die Lautheit
    des Stücks an und bleibt unter typischen Sprachspitzen, ohne Stille zu werten.
    """
    if not konfig("pipeline").get("schnitt", {}).get("wortanfang_nachziehen", True):
        return Ergebnis("nichts", "Wortanfangskorrektur ist ausgeschaltet.")
    achsen_pfad = ordner / "zeitachse.json"
    achse = lesen(achsen_pfad)
    roh = ordner / "roh.mp4"
    if not achse or not roh.exists():
        return Ergebnis("fehler", "roh.mp4 oder zeitachse.json fehlt für die Wortanfangskorrektur.")
    woerter = achse.get("woerter", [])
    if not woerter:
        return Ergebnis("nichts", "keine Wörter für die Wortanfangskorrektur.")
    try:
        pegel = _pegel(roh)
    except Exception as e:
        return Ergebnis("fehler", f"Wortanfangskorrektur: {e}")
    schwelle = _perzentil(pegel, 0.95) * 0.20
    if schwelle <= 0:
        return Ergebnis("befund", "Wortanfangskorrektur: Ton ist durchgehend still.")
    korrigiert = 0
    for nr, wort in enumerate(woerter):
        start, ende = float(wort["s"]), float(wort["e"])
        luecke = nr == 0 or start - float(woerter[nr - 1]["e"]) >= 0.25
        if not luecke:
            continue
        einsatz = _einsatz(pegel, start, min(ende, start + 2.0), schwelle)
        if einsatz is None or not 0.3 <= einsatz - start <= 2.0:
            continue
        neuer_start = min(einsatz, ende - 0.05)
        if neuer_start > start:
            wort["s"] = neuer_start
            korrigiert += 1
    achse["wortanfang_korrigiert"] = korrigiert
    schreiben(achsen_pfad, achse)
    return Ergebnis("ok", f"Wortanfangskorrektur: {korrigiert} Wörter nachgezogen.")
