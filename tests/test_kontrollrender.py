"""Kontrollbilder für die menschliche Sichtprüfung aller Bildstile.

Die Titel sind bewusst je Stil verschieden: jeder Pinterest-Stil mit Punkten
hat eine eigene Höchstzahl an gezeichneten Karten (siehe HOECHSTZAHL in
pinterest.py), und das Titelversprechen verlangt, dass eine Zahl im Titel
genau dazu passt. Ein einziger geteilter Titel wie "7 klare Schritte" für
alle acht Stile hätte hier immer wieder einen Befund statt eines Bildes
erzeugt (Befund 28.09.2026: genau das kam heraus, weil szene/notizbuch/
editorial/typomix/tabelle nur 3 bis 6 der 7 Punkte zeichnen).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.kern import ROOT
from pipeline.stile import instagram, pinterest, threads, tiktok
from pipeline.stile.pinterest import HOECHSTZAHL


BEISPIELDATEN = {
    "titel": "7 klare Schritte für deinen Alltag",
    "aussage": "Ein klarer Satz schafft einen guten nächsten Schritt.",
    "saetze": [
        "Beginne mit einer Frage, die dein Problem klar eingrenzt.",
        "Ordne die Fakten, bevor du nach einer Lösung suchst.",
        "Wähle einen kleinen Schritt, den du heute wirklich gehen kannst.",
        "Prüfe danach, was schon besser funktioniert als gestern.",
        "Halte den nächsten Versuch so einfach wie möglich.",
        "Teile die Arbeit in einen klaren Anfang und ein Ende.",
        "Notiere, was du beim nächsten Mal anders machen willst.",
        "Lass dir für den Rest bewusst etwas Zeit.",
        "Wiederhole nur, was sich in der Praxis bewährt hat.",
    ],
    # Der Spickzettel zeichnet höchstens sieben Karten; die Kontrolle zeigt daher dieselbe Kappung wie der Betrieb.
    "punkte": [
        "Frage präzisieren",
        "Fakten ordnen",
        "Kleinen Schritt wählen",
        "Ergebnis prüfen",
        "Nächsten Versuch planen",
        "Arbeit sauber abschließen",
        "Erkenntnis notieren",
    ],
    "quelle": "Eigene Auswertung, 28.09.2026",
    "statistik": [("Plan", 20), ("Test", 40), ("Lernen", 60)],
    "einwand": "Das klingt nach mehr Arbeit.",
    "vorher": "Alles gleichzeitig anfangen.",
    "nachher": "Einen Schritt nach dem anderen gehen.",
    "frage": "Welchen Schritt gehst du heute?",
    "text": "7",
    "zahl": 7,
    "handle": "@deinhandle",
}

# Pinterest-Titel je Stil, passend zur Höchstzahl gezeichneter Punkte (siehe Docstring).
PINTEREST_TITEL = {
    "spickzettel": "7 klare Schritte für deinen Alltag",
    "szene": "3 Szenen für deinen Alltag",
    "notizbuch": "6 Notizen für deinen Alltag",
    "editorial": "4 Editorial-Punkte für deinen Alltag",
    "typomix": "5 Ideen im Mix",
    "tabelle": "6 Aufgaben im Vergleich",
    "toolraster": "9 Werkzeuge auf einen Blick",  # kein Titelversprechen, aber zufällig passend zum festen 3x3-Raster
    "statistik": "So verteilen sich die Phasen",  # keine Zahl im Titel, statistik zeichnet eigene Werte
}


def _speichern(im, ziel: Path) -> None:
    im.convert("RGB").save(ziel, "JPEG", quality=90, subsampling=0)


@pytest.mark.langsam
def test_kontrollrender_aller_stile():
    # Frühwarnung, falls ein neuer Pinterest-Stil mit Höchstzahl dazukommt, aber
    # PINTEREST_TITEL oben nicht mitgepflegt wurde.
    assert set(HOECHSTZAHL) <= set(PINTEREST_TITEL)

    zielordner = ROOT / "ausgabe" / "_kontrolle" / "stile"
    zielordner.mkdir(parents=True, exist_ok=True)

    erwartete_dateien = []
    for stil in ["zitat_standbild", "zahl", "einwand", "vorher_nachher", "raster", "notiz"]:
        im, befund = instagram.bild_stil(stil, BEISPIELDATEN)
        assert im is not None and not befund, (stil, befund)
        dateiname = f"instagram-{stil}.jpg"
        _speichern(im, zielordner / dateiname)
        erwartete_dateien.append(dateiname)

    for stil in ["schritte", "kette", "woche_hell"]:
        folien, befund = instagram.karussell(stil, BEISPIELDATEN, 6)
        assert not befund, (stil, befund)
        for nummer, folie in enumerate(folien[:2], 1):
            dateiname = f"instagram-{stil}-{nummer:02d}.jpg"
            _speichern(folie, zielordner / dateiname)
            erwartete_dateien.append(dateiname)

    for stil in ["foto_schritte", "foto_zitat"]:
        im, befund = tiktok.foto_stil(stil, BEISPIELDATEN)
        assert im is not None and not befund, (stil, befund)
        dateiname = f"tiktok-{stil}.jpg"
        _speichern(im, zielordner / dateiname)
        erwartete_dateien.append(dateiname)

    for stil in PINTEREST_TITEL:
        daten = {**BEISPIELDATEN, "titel": PINTEREST_TITEL[stil]}
        im, befund = pinterest.pin(stil, daten)
        assert im is not None and not befund, (stil, befund)
        dateiname = f"pinterest-{stil}.jpg"
        _speichern(im, zielordner / dateiname)
        erwartete_dateien.append(dateiname)

    im, befund = threads.zitatkarte(BEISPIELDATEN["saetze"][0])
    assert im is not None and not befund
    dateiname = "threads-bild-zeile.jpg"
    _speichern(im, zielordner / dateiname)
    erwartete_dateien.append(dateiname)

    for dateiname in erwartete_dateien:
        assert (zielordner / dateiname).exists()
