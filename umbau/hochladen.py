#!/usr/bin/env python3
"""Kurzlebige HTTPS-Adresse für eine Datei über rclone und Google Drive.

OpenRouter nimmt für Video- und Bildeingaben nur HTTPS-Adressen, keine lokalen
Dateien. Diese Datei legt eine Datei kurz auf ein Drive-Remote, baut daraus
einen Download-Link und löscht die Datei danach wieder, auch wenn der
umgebende Auftrag fehlschlägt.

Remote per Umgebungsvariable UMBAU_RCLONE_ZIEL konfigurierbar, Standard
"gdrive:umbau-tmp".
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from typing import Iterator

ZIEL_STANDARD = "gdrive:umbau-tmp"


def ziel() -> str:
    return os.environ.get("UMBAU_RCLONE_ZIEL", ZIEL_STANDARD)


def drive_id_zu_link(file_id: str) -> str:
    """Baut aus einer Google-Drive-Datei-ID den Download-Link."""
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download"


def _id_aus_rclone_link(text: str) -> str:
    treffer = re.search(r"id=([\w-]+)", text) or re.search(r"/d/([\w-]+)", text)
    if not treffer:
        raise RuntimeError(f"Konnte keine Datei-ID aus der rclone-Antwort lesen: {text[:200]}")
    return treffer.group(1)


def hochladen(pfad: str, remote: str | None = None) -> tuple[str, str]:
    """Lädt eine Datei auf das Remote hoch und gibt (Dateiname, HTTPS-Link)
    zurück."""
    remote = remote or ziel()
    name = os.path.basename(pfad)
    subprocess.run(["rclone", "copy", pfad, f"{remote}/"], check=True)
    out = subprocess.run(
        ["rclone", "link", f"{remote}/{name}"], capture_output=True, text=True, check=True,
    ).stdout
    file_id = _id_aus_rclone_link(out)
    return name, drive_id_zu_link(file_id)


def ist_noch_da(remote: str, name: str) -> bool:
    """Prüft mit `rclone lsf`, ob die Datei im Remote-Ordner noch auftaucht."""
    ergebnis = subprocess.run(
        ["rclone", "lsf", f"{remote}/"], capture_output=True, text=True,
    )
    return name in ergebnis.stdout.splitlines()


def weg(name: str, remote: str | None = None) -> None:
    """Löscht die Datei endgültig und kontrolliert danach mit `rclone lsf`,
    ob sie wirklich weg ist. Aus dem Papierkorb bleibt der Link weiter
    abrufbar, darum --drive-use-trash=false statt eines normalen Löschens.
    Schlägt das Löschen fehl oder taucht die Datei danach noch auf, wird laut
    gewarnt statt still weiterzumachen, mit dem genauen Befehl zum
    Nachlöschen."""
    remote = remote or ziel()
    pfad = f"{remote}/{name}"
    befehl = f"rclone deletefile --drive-use-trash=false {pfad}"
    ergebnis = subprocess.run(
        ["rclone", "deletefile", "--drive-use-trash=false", pfad], capture_output=True, text=True,
    )
    if ergebnis.returncode != 0:
        print(
            f"WARNUNG: Löschen von {pfad} ist fehlgeschlagen "
            f"(Rückgabecode {ergebnis.returncode}). Lösch von Hand mit: {befehl}",
            file=sys.stderr,
        )
        return
    if ist_noch_da(remote, name):
        print(
            f"WARNUNG: {pfad} steht nach dem Löschen noch in der Dateiliste. "
            f"Lösch von Hand mit: {befehl}",
            file=sys.stderr,
        )


@contextlib.contextmanager
def kurzlebiger_link(pfad: str, remote: str | None = None) -> Iterator[str]:
    """Lädt die Datei hoch, gibt den HTTPS-Link in den `with`-Block und löscht
    die Datei danach immer wieder, auch wenn im Block eine Ausnahme fliegt."""
    name, link = hochladen(pfad, remote)
    try:
        yield link
    finally:
        weg(name, remote)
