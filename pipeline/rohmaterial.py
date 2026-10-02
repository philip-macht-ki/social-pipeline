"""uv run pipeline eingang

Übernimmt neue Videos aus eingang/ in die Arbeitsstruktur arbeit/<take>/.
"""

from __future__ import annotations

import re
import shutil
import os
import time
from pathlib import Path

from .kern import Ergebnis, dauer, jetzt, konfig, lesen, log, pfad, schreiben, takes

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


def _bekannter_name(datei: Path, eingang_ordner: Path) -> bool:
    """Prüft Namen, die im lokalen Eingang oder bereits als Take vorhanden sind."""
    name = datei.name.casefold()
    im_eingang = {p.name.casefold() for p in eingang_ordner.iterdir() if p.is_file()}
    return name in im_eingang or pfad("arbeit", take_name(datei.name)).exists()


def _weitere_ordner(eingang_ordner: Path) -> list[Ergebnis]:
    """Kopiert fertige Videos aus zusätzlichen Ordnern sicher in den lokalen Eingang."""
    ergebnisse: list[Ergebnis] = []
    weitere = konfig("pipeline").get("eingang", {}).get("weitere_ordner", [])
    beobachtet_pfad = pfad("arbeit", "eingang_beobachtet.json")
    beobachtet = lesen(beobachtet_pfad, {}) or {}
    jetzt_s = time.time()
    for eintrag in weitere:
        quellordner = Path(str(eintrag)).expanduser()
        if not quellordner.is_dir() or not os.access(quellordner, os.R_OK | os.X_OK):
            meldung = f"befund: Eingangsordner nicht erreichbar: {quellordner}"
            log(meldung)
            ergebnisse.append(Ergebnis("befund", meldung))
            continue
        for datei in sorted(quellordner.iterdir()):
            if (
                not datei.is_file()
                or datei.name.startswith(".")
                or datei.suffix.lower() not in ENDUNGEN
            ):
                continue
            if _bekannter_name(datei, eingang_ordner):
                beobachtet.pop(str(datei), None)
                continue
            stand = datei.stat()
            kennung = str(datei)
            vorher = beobachtet.get(kennung, {})
            gleich = (
                vorher.get("groesse") == stand.st_size
                and vorher.get("mtime_ns") == stand.st_mtime_ns
            )
            seit = float(vorher.get("seit", jetzt_s)) if gleich else jetzt_s
            beobachtet[kennung] = {
                "groesse": stand.st_size,
                "mtime_ns": stand.st_mtime_ns,
                "seit": seit,
            }
            if not gleich or jetzt_s - seit < 180:
                continue
            teil = eingang_ordner / f".{datei.name}.teil"
            try:
                erwartete_groesse = stand.st_size
                erwartete_mtime = stand.st_mtime_ns
                shutil.copyfile(datei, teil)
                kopierte_groesse = teil.stat().st_size
                aktuell = datei.stat()
                aktuelle_groesse = aktuell.st_size
                vollstaendig = (
                    kopierte_groesse and kopierte_groesse == erwartete_groesse
                )
                unveraendert = (
                    aktuelle_groesse == erwartete_groesse
                    and aktuell.st_mtime_ns == erwartete_mtime
                )
                if not vollstaendig or not unveraendert:
                    teil.unlink(missing_ok=True)
                    meldung = (
                        f"befund: Eingang {datei.name}: Kopie unvollständig, verworfen"
                    )
                    log(meldung)
                    ergebnisse.append(Ergebnis("befund", meldung))
                    continue
                teil.replace(eingang_ordner / datei.name)
                beobachtet.pop(kennung, None)
                uebernommen = quellordner / "übernommen"
                uebernommen.mkdir(exist_ok=True)
                shutil.move(str(datei), str(uebernommen / datei.name))
                ergebnisse.append(Ergebnis("ok", f"ok: Eingang {datei.name} kopiert"))
            except Exception as e:
                teil.unlink(missing_ok=True)
                meldung = f"fehler: Eingang {datei.name}: {e}"
                log(meldung)
                ergebnisse.append(Ergebnis("fehler", meldung))
    schreiben(beobachtet_pfad, beobachtet)
    return ergebnisse


def eingang() -> list[Ergebnis]:
    quelle = pfad("eingang")
    quelle.mkdir(parents=True, exist_ok=True)
    ergebnisse = _weitere_ordner(quelle)
    for datei in sorted(quelle.iterdir()):
        if not datei.is_file() or datei.suffix.lower() not in ENDUNGEN:
            continue
        try:
            take = _freier_name(take_name(datei.name))
            ziel = pfad("arbeit", take)
            ziel.mkdir(parents=True)
            medien = ziel / f"quelle.{datei.suffix.lower().lstrip('.')}"
            shutil.move(str(datei), str(medien))
            schreiben(
                ziel / "take.json",
                {
                    "id": take,
                    "quelle": medien.name,
                    "dauer_s": round(dauer(medien), 3),
                    "eingang_am": jetzt().isoformat(timespec="seconds"),
                    "status": "eingang",
                },
            )
            ergebnisse.append(Ergebnis("ok", f"ok: Eingang {take} übernommen"))
        except Exception as e:
            ergebnisse.append(Ergebnis("fehler", f"fehler: Eingang {datei.name}: {e}"))
    for take in takes():
        if not (take / "woerter.json").exists() or not any(
            (take / "stuecke").glob("*/rezept.json")
        ):
            ergebnisse.append(
                Ergebnis("befund", f"befund: {take.name} wird wieder aufgenommen")
            )
    return ergebnisse or [Ergebnis("nichts", "nichts: kein neues Eingangsvideo")]


def befehl_eingang(args) -> int:
    ergebnisse = eingang()
    for ergebnis in ergebnisse:
        print(ergebnis.meldung)
    return 1 if any(e.status == "fehler" for e in ergebnisse) else 0
