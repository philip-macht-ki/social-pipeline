"""uv run pipeline eingang

Übernimmt neue Videos aus eingang/ in die Arbeitsstruktur arbeit/<take>/.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .kern import Ergebnis, dauer, jetzt, pfad, schreiben, takes

ENDUNGEN = {".mov", ".mp4", ".m4v"}


def take_name(name: str) -> str:
    """Macht aus einem Dateinamen eine stabile, harmlose Take-ID."""
    text = re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")
    return text or "take"


def _freier_name(wunsch: str) -> str:
    kandidat, nr = wunsch, 2
    while pfad("arbeit", kandidat).exists():
        kandidat, nr = f"{wunsch}-{nr}", nr + 1
    return kandidat


def eingang() -> list[Ergebnis]:
    quelle = pfad("eingang")
    quelle.mkdir(parents=True, exist_ok=True)
    ergebnisse: list[Ergebnis] = []
    for datei in sorted(quelle.iterdir()):
        if not datei.is_file() or datei.suffix.lower() not in ENDUNGEN:
            continue
        try:
            take = _freier_name(take_name(datei.name))
            ziel = pfad("arbeit", take)
            ziel.mkdir(parents=True)
            medien = ziel / f"quelle.{datei.suffix.lower().lstrip('.')}"
            shutil.move(str(datei), str(medien))
            schreiben(ziel / "take.json", {"id": take, "quelle": medien.name,
                "dauer_s": round(dauer(medien), 3), "eingang_am": jetzt().isoformat(timespec="seconds"),
                "status": "eingang"})
            ergebnisse.append(Ergebnis("ok", f"ok: Eingang {take} übernommen"))
        except Exception as e:
            ergebnisse.append(Ergebnis("fehler", f"fehler: Eingang {datei.name}: {e}"))
    for take in takes():
        if not (take / "woerter.json").exists() or not any((take / "stuecke").glob("*/rezept.json")):
            ergebnisse.append(Ergebnis("befund", f"befund: {take.name} wird wieder aufgenommen"))
    return ergebnisse or [Ergebnis("nichts", "nichts: kein neues Eingangsvideo")]


def befehl_eingang(args) -> int:
    ergebnisse = eingang()
    for ergebnis in ergebnisse:
        print(ergebnis.meldung)
    return 1 if any(e.status == "fehler" for e in ergebnisse) else 0
