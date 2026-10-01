#!/usr/bin/env python3
"""Umbauten zeitgenau in die Vorlage setzen.

Standard ist die MASKE: Aus dem Umbau wird nur übernommen, was sich gegenüber
dem Original wirklich geändert hat (Hemd, Fensterblick, Gegenstand). Gesicht,
Arme, Hände und Raum bleiben echtes Video, damit stimmen Hautfarbe und Schärfe
von selbst. Setzt man stattdessen das ganze umgebaute Bild ein, sieht ein Arm
schnell unnatürlich aus und hat die falsche Farbe. Die Maske löst Farbe UND
Schärfe zugleich und kostet nichts zusätzlich.

Aufruf: einsetzen.py arbeitsordner --feld 200:180:860:60 [--modus maske|ganz] [--schwelle 28]

--feld ist Pflicht: ein Stück Wand, das in KEINEM Umbau verändert wird, als
B:H:X:Y in Pixeln (Breite:Höhe:X:Y). Es hängt an der jeweiligen Aufnahme
(Kameraposition, Raum) und lässt sich nicht sinnvoll erraten. Ohne eigenes
Feld bricht das Werkzeug mit einer klaren Meldung ab, statt still irgendein
Feld anzunehmen und einen falschen Farbabgleich zu rechnen.

Erwartet im Ordner: master.mov (1080x1920, 30 fps, Originalton), abschnitte.json
([{"name": "hawaii", "von": 39.74, "bis": 44.10}, ...]) und je Abschnitt
edit-<name>.mp4 (oder geschärft edit-<name>-scharf.mp4, das hat Vorrang).
Schreibt comp-<name>.mp4 je Abschnitt und master_umbau.mov (gleiche Zeitachse,
Originalton).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def farbfaktor(soll: list[float], ist: list[float]) -> list[float]:
    """Verhältnis der mittleren Farbwerte an einem unveränderten Wandfeld,
    Original gegen Umbau. Gleicht aus, dass das Umbaumodell das Bild oft 4 bis
    13 % dunkler zurückgibt."""
    return [p / max(q, 1) for p, q in zip(soll, ist)]


def gain_filter(faktoren: list[float]) -> str:
    """ffmpeg-Filterausdruck für den Farbabgleich aus `farbfaktor`."""
    r, g, b = faktoren
    return f"colorchannelmixer=rr={r:.4f}:gg={g:.4f}:bb={b:.4f}"


def masken_kette(von: float, bis: float, gain: str, schwelle: int) -> str:
    """ffmpeg-Filterkette für den Maskenmodus: Unterschied Original gegen
    Umbau, Schwelle, Sprenkel weg (erosion), Fläche etwas größer (dilation),
    weicher Rand (boxblur), dann als Alphakanal über das Original gelegt."""
    return (
        f"[0:v]trim={von}:{bis},setpts=PTS-STARTPTS,fps=30,format=yuv444p,split=2[o1][o2];"
        f"[1:v]scale=1080:1920:flags=lanczos,fps=30,{gain},format=yuv444p,split=2[e1][e2];"
        f"[o1][e1]blend=all_mode=difference,format=gray,"
        f"lutyuv=y='if(gt(val,{schwelle}),255,0)',"
        f"erosion,dilation,dilation,dilation,boxblur=10:2[mk];"
        f"[e2][mk]alphamerge[ea];[o2][ea]overlay=0:0:format=auto,format=yuv420p[v]"
    )


def ganz_kette(gain: str) -> str:
    """Filterkette für den alten Weg: das ganze umgebaute Bild einsetzen, nur
    mit Farbabgleich, ohne Maske."""
    return f"[1:v]scale=1080:1920:flags=lanczos,fps=30,{gain},format=yuv420p[v]"


def kette_bauen(modus: str, von: float, bis: float, gain: str, schwelle: int) -> str:
    if modus == "maske":
        return masken_kette(von, bis, gain, schwelle)
    return ganz_kette(gain)


def mittel(feld: str, datei: str, t: float) -> list[int]:
    """Mittlere Farbe (R, G, B) eines Wandstücks zur Sekunde `t`."""
    out = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-ss", str(t), "-i", datei, "-frames:v", "1",
            "-vf", f"scale=1080:1920,crop={feld},scale=1:1:flags=area,format=rgb24",
            "-f", "rawvideo", "-",
        ],
        capture_output=True, check=True,
    ).stdout
    return list(out[:3])


def feld_erzwingen(feld: str | None) -> str:
    """Bricht mit einer klaren Meldung ab, statt still ein Wandfeld zu raten.
    Das Feld hängt an der jeweiligen Aufnahme (Kameraposition, Raum) und ist
    in keiner Aufnahme automatisch richtig."""
    if not feld:
        raise ValueError(
            "einsetzen.py braucht --feld: ein Stück Wand, das in KEINEM Umbau "
            "verändert wird, als B:H:X:Y in Pixeln. Sag deinem Claude: "
            "Markiere auf einem Standbild ein Stück Wand, das in keinem Umbau "
            "verändert wird, und zeig es mir."
        )
    return feld


def quelle_waehlen(ordner: str, name: str) -> str:
    """Geschärfte Fassung hat Vorrang vor der unbearbeiteten."""
    geschaerft = os.path.join(ordner, f"edit-{name}-scharf.mp4")
    return geschaerft if os.path.exists(geschaerft) else os.path.join(ordner, f"edit-{name}.mp4")


def abschnitt_einsetzen(ordner: str, eintrag: dict, modus: str, schwelle: int, feld: str) -> tuple[str, list[float]]:
    name, von, bis = eintrag["name"], eintrag["von"], eintrag["bis"]
    master = os.path.join(ordner, "master.mov")
    quelle = quelle_waehlen(ordner, name)
    mitte = (bis - von) / 2
    soll = mittel(feld, master, von + mitte)
    ist = mittel(feld, quelle, mitte)
    faktoren = farbfaktor(soll, ist)
    gain = gain_filter(faktoren)
    kette = kette_bauen(modus, von, bis, gain, schwelle)
    comp = os.path.join(ordner, f"comp-{name}.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", master, "-i", quelle,
            "-filter_complex", kette, "-map", "[v]", "-an",
            "-c:v", "libx264", "-crf", "12", "-preset", "medium", comp,
        ],
        check=True,
    )
    return comp, faktoren


def zusammenfuegen(ordner: str, abschnitte: list[dict]) -> str:
    """Legt alle comp-<name>.mp4 zeitgenau über master.mov und behält den
    Originalton."""
    eingaben = ["-i", os.path.join(ordner, "master.mov")]
    ketten = []
    letzte = "[0:v]"
    for i, eintrag in enumerate(abschnitte, 1):
        von, bis, name = eintrag["von"], eintrag["bis"], eintrag["name"]
        comp = os.path.join(ordner, f"comp-{name}.mp4")
        eingaben += ["-itsoffset", str(von), "-i", comp]
        ketten.append(f"[{i}:v]fps=30,format=yuv420p[e{i}]")
        ketten.append(f"{letzte}[e{i}]overlay=0:0:eof_action=pass:enable='between(t,{von},{bis - 0.001})'[o{i}]")
        letzte = f"[o{i}]"
    ziel = os.path.join(ordner, "master_umbau.mov")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", *eingaben, "-filter_complex", ";".join(ketten),
            "-map", letzte, "-map", "0:a:0", "-c:v", "libx264", "-crf", "12", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "copy", ziel,
        ],
        check=True,
    )
    return ziel


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("ordner")
    a.add_argument("--modus", choices=["maske", "ganz"], default="maske")
    a.add_argument("--schwelle", type=int, default=28, help="Mindestunterschied (0-255), ab dem ein Pixel als umgebaut gilt")
    a.add_argument("--feld", default=None, help="Pflicht: Wandstück B:H:X:Y für den Farbabgleich, in keinem Umbau verändert")
    x = a.parse_args()
    try:
        feld = feld_erzwingen(x.feld)
    except ValueError as e:
        print("FEHLER", e, file=sys.stderr)
        sys.exit(1)
    with open(os.path.join(x.ordner, "abschnitte.json"), encoding="utf-8") as f:
        abschnitte = json.load(f)
    for eintrag in abschnitte:
        comp, faktoren = abschnitt_einsetzen(x.ordner, eintrag, x.modus, x.schwelle, feld)
        print(eintrag["name"], x.modus, "Farbfaktor", [round(v, 3) for v in faktoren], "->", comp)
    ziel = zusammenfuegen(x.ordner, abschnitte)
    print("OK", ziel)


if __name__ == "__main__":
    main()
