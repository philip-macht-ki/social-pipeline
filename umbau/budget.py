"""Monatsdeckel fuer kostenpflichtige KI-Videos."""
from __future__ import annotations

import subprocess
import sys
import uuid
from datetime import datetime

from pipeline.kern import jetzt, konfig, lesen, log, pfad, schreiben

PREIS = {"flux": 0.035, "seedance": 0.09, "ltx": 0.0}


def _monat() -> str:
    return jetzt().strftime("%Y-%m")


def _datei():
    return pfad("arbeit", "ki_budget.json")


def _daten() -> dict:
    daten = lesen(_datei(), {}) or {}
    if daten.get("monat") != _monat():
        daten = {"monat": _monat(), "buchungen": [], "gemeldet": False}
        schreiben(_datei(), daten)
    return daten


def _deckel() -> float:
    return float(konfig("pipeline").get("ki", {}).get("deckel_eur", 20))


def _preis(art: str, sekunden: float) -> float:
    if art not in PREIS:
        raise ValueError(f"Unbekannte KI-Art: {art}")
    if art == "seedance":
        sekunden = max(4.0, sekunden)
    return round(PREIS[art] * max(0.0, sekunden), 4)


def _verbrauch(daten: dict) -> float:
    return sum(float(b.get("kosten", b.get("geschaetzt", 0))) for b in daten["buchungen"]
               if b.get("status") == "gebucht")


def _melden(daten: dict) -> None:
    if daten.get("gemeldet"):
        return
    daten["gemeldet"] = True
    schreiben(_datei(), daten)
    if sys.platform != "darwin":
        return
    try:
        subprocess.run(["osascript", "-e", 'display notification "KI-Monatsdeckel erreicht." '
                        'with title "Social-Media-Pipeline"'], check=False, capture_output=True)
    except OSError as e:
        log(f"KI-Deckel-Mitteilung nicht gesendet: {e}")


def darf(art: str, sekunden: float) -> bool:
    """Prueft den Deckel. LTX bleibt auch nach dem Deckel erlaubt."""
    if art == "ltx":
        return True
    daten = _daten()
    erlaubt = _verbrauch(daten) + _preis(art, sekunden) <= _deckel()
    if not erlaubt or _verbrauch(daten) >= _deckel():
        _melden(daten)
    return erlaubt


def reservieren(art: str, sekunden: float, wofuer: str) -> str:
    """Bucht den vorsichtigen Schaetzwert vor dem externen Auftrag."""
    if not darf(art, sekunden):
        raise RuntimeError("KI-Monatsdeckel erreicht.")
    daten = _daten()
    nummer = uuid.uuid4().hex
    daten["buchungen"].append({"id": nummer, "zeit": jetzt().isoformat(timespec="seconds"),
                                "art": art, "sekunden": sekunden, "wofuer": wofuer,
                                "geschaetzt": _preis(art, sekunden), "kosten": _preis(art, sekunden),
                                "status": "gebucht"})
    schreiben(_datei(), daten)
    return nummer


def abschliessen(nummer: str, kosten_echt: float | None, ok: bool) -> None:
    """Schliesst eine Buchung ab oder storniert einen fehlgeschlagenen Auftrag."""
    daten = _daten()
    for buchung in daten["buchungen"]:
        if buchung.get("id") != nummer:
            continue
        if not ok:
            buchung["status"] = "storniert"
            buchung["kosten"] = 0.0
        elif kosten_echt is not None:
            buchung["kosten"] = float(kosten_echt)
        break
    else:
        raise KeyError(f"Unbekannte KI-Buchung: {nummer}")
    schreiben(_datei(), daten)
    if _verbrauch(daten) >= _deckel():
        _melden(daten)


def stand() -> str:
    daten = _daten()
    verbrauch = _verbrauch(daten)
    text = f"KI-Budget {_monat()}: {verbrauch:.2f} € von {_deckel():.2f} €"
    return "DECKEL ERREICHT. " + text if verbrauch >= _deckel() else text


def befehl(args) -> int:
    daten = _daten()
    print(stand())
    for b in daten["buchungen"]:
        print(f"{b['zeit']} {b['art']} {b['sekunden']} s {b['kosten']:.2f} € {b['status']} {b['wofuer']}")
    return 0
