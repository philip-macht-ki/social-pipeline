"""Fertige Umbau- und Werbeclips als normale planbare Stücke aufnehmen."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import texte, titelband, transkript, urteil, video
from .kern import Ergebnis, dauer, lauf, lesen, pfad, schreiben


def _freier_name(art: str) -> str:
    praefix = "U" if art == "umbau" else "W"
    nummern = []
    for ordner in pfad("ausgabe").glob(f"{praefix}[0-9][0-9]"):
        try:
            nummern.append(int(ordner.name[1:]))
        except ValueError:
            continue
    for nummer in range(1, 100):
        if nummer not in nummern:
            return f"{praefix}{nummer:02d}"
    raise RuntimeError(f"Kein freier Name mit Präfix {praefix} gefunden.")


def _hat_ton(datei: Path) -> bool:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "default=nk=1:nw=1", str(datei)], capture_output=True, text=True
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def _normalisieren(quelle: Path, ziel: Path, hat_ton: bool) -> None:
    """Randet auf 9:16 und ergänzt bei Bedarf eine stille, normalisierte Tonspur."""
    # Querformat mit Rand mittig auf 9:16, nie beschneiden.
    bild = ("scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p")
    if hat_ton:
        graph = f"[0:v]{bild}[v];[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        audio_eingang = []
    else:
        graph = f"[0:v]{bild}[v];[1:a]anull[a]"
        audio_eingang = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    roh = ziel.with_name("_aufnahme_roh.mp4")
    lauf([
        "ffmpeg", "-y", "-i", str(quelle), *audio_eingang, "-filter_complex", graph,
        "-map", "[v]", "-map", "[a]", "-shortest", "-r", "30", "-c:v", "libx264", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(roh),
    ])
    video._instagram_fassung(roh, ziel, dauer(roh))
    roh.unlink(missing_ok=True)


def _inhalt(transkript_text: str, titel: str | None, beschreibung: str | None) -> tuple[str, str]:
    if titel and beschreibung:
        return titel, beschreibung
    antwort = urteil.frage(
        urteil.vorlage("aufnehmen", transkript=transkript_text, titel=titel or "",
                       beschreibung=beschreibung or ""),
        zweck="aufnehmen",
        rueckfall=lambda: {"titel": titel or "Fertiges Video", "aussage": beschreibung or ""},
        pruefe=lambda d: None if isinstance(d, dict) and isinstance(d.get("titel"), str)
        and isinstance(d.get("aussage"), str) and d["titel"].strip() and d["aussage"].strip()
        else "Titel oder Aussage fehlt.",
    )
    if not isinstance(antwort, dict):
        raise RuntimeError("Kein Urteil für Titel und Aussage.")
    return titel or antwort["titel"], beschreibung or antwort["aussage"]


def aufnehmen(datei: Path, name: str | None, art: str, titel: str | None, beschreibung: str | None,
              neu: bool = False) -> Ergebnis:
    if not datei.is_file():
        return Ergebnis("fehler", f"Datei nicht gefunden: {datei}")
    name = name or _freier_name(art)
    ausgabe = pfad("ausgabe", name)
    if ausgabe.exists() and not neu:
        return Ergebnis("fehler", f"{name} ist schon vorhanden. Mit --neu darfst du es neu aufnehmen.")
    arbeit = pfad("arbeit", name)
    ausgabe.mkdir(parents=True, exist_ok=True)
    arbeit.mkdir(parents=True, exist_ok=True)
    quellpfad = arbeit / f"quelle{datei.suffix.lower() or '.mp4'}"
    shutil.copy2(datei, quellpfad)
    take = {"id": name, "quelle": quellpfad.name, "dauer_s": dauer(datei), "status": "aufgenommen"}
    schreiben(arbeit / "take.json", take)
    hat_ton = _hat_ton(datei)
    _normalisieren(datei, ausgabe / "instagram.mp4", hat_ton)
    shutil.copyfile(ausgabe / "instagram.mp4", ausgabe / "tiktok.mp4")
    dauer_s = dauer(ausgabe / "instagram.mp4")

    woerter = []
    if hat_ton:
        ergebnis = transkript.verarbeite(arbeit, neu=True)
        if ergebnis.status == "fehler":
            return ergebnis
        woerter = lesen(arbeit / "woerter.json", []) or []
    if not woerter and not beschreibung:
        befund = "Beschreibung fehlt"
        schreiben(ausgabe / "stueck.json", {"id": name, "take": name, "nr": 1, "von_stuecken": 1,
                 "stil": art, "dauer_s": round(dauer_s, 2),
                 "dateien": {"instagram": "instagram.mp4", "tiktok": "tiktok.mp4"},
                 "status": "befund", "befunde": [befund]})
        return Ergebnis("befund", befund)

    transkript_text = (arbeit / "transkript.txt").read_text(encoding="utf-8") if woerter else ""
    titel, aussage = _inhalt(transkript_text, titel, beschreibung)
    rezept_ordner = arbeit / "stuecke" / "01"
    rezept_ordner.mkdir(parents=True, exist_ok=True)
    rezept = {"id": name, "take": name, "nr": 1, "von_stuecken": 1, "titel": titel, "aussage": aussage,
              "stil": {"reel": art}, "status": "gebaut", "befunde": []}
    schreiben(rezept_ordner / "rezept.json", rezept)
    text_ergebnis = texte._machen(rezept_ordner)
    dateien = {"instagram": "instagram.mp4", "tiktok": "tiktok.mp4"}
    befunde = list(lesen(ausgabe / "texte.json", {}).get("befunde", []))
    if text_ergebnis.status == "befund":
        befunde.append(text_ergebnis.meldung)
    if dauer_s <= 179:
        shutil.copyfile(ausgabe / "instagram.mp4", ausgabe / "youtube.mp4")
        dateien["youtube"] = "youtube.mp4"
    else:
        befunde.append(f"zu lang für ein Short ({dauer_s:.0f} s > 179 s), kein youtube.mp4.")
    cover = titelband.cover(ausgabe / "instagram.mp4", min(dauer_s * .3, max(0, dauer_s - .1)), titel,
                            "", ausgabe / "cover.jpg")
    if cover.meldung:
        befunde.append(cover.meldung)
    status = "befund" if befunde else "fertig"
    schreiben(ausgabe / "stueck.json", {"id": name, "take": name, "nr": 1, "von_stuecken": 1,
             "stil": art, "dauer_s": round(dauer_s, 2), "dateien": dateien,
             "status": status, "befunde": befunde})
    rezept["status"] = status
    rezept["befunde"] = befunde
    schreiben(rezept_ordner / "rezept.json", rezept)
    return Ergebnis(status if status == "befund" else "ok", f"{name} aufgenommen.")


def befehl(args) -> int:
    ziele = getattr(args, "ziel", [])
    if len(ziele) != 1:
        print("fehler: aufnehmen braucht genau eine Videodatei.")
        return 2
    ergebnis = aufnehmen(Path(ziele[0]), getattr(args, "name", None), getattr(args, "art", "umbau"),
                         getattr(args, "titel", None), getattr(args, "beschreibung", None),
                         getattr(args, "neu", False))
    print(f"{ergebnis.status}: {ergebnis.meldung}")
    return 1 if ergebnis.status == "fehler" else 0
