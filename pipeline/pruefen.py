"""uv run pipeline pruefen

Selbsttest der lokalen Voraussetzungen: ist alles da, was die Pipeline
braucht? Jede Zeile ist eine Ampel (GRUEN/GELB/ROT). Gelb und Rot bekommen
zusätzlich einen Handlungshinweis, damit ein Mitglied ohne Programmier-
erfahrung weiß, was als Nächstes zu tun ist.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .kern import jetzt, konfig, lesen, pfad
from .schrift import schrift

FILTER = {"scale", "crop", "overlay", "hflip", "curves", "eq", "unsharp", "loudnorm", "concat",
          "amix", "afade", "fps", "format"}


def befehl(args) -> int:
    rot = False

    def zeile(farbe: str, text: str, hinweis: str | None = None) -> None:
        nonlocal rot
        rot |= farbe == "ROT"
        zusatz = f" -> {hinweis}" if hinweis and farbe != "GRUEN" else ""
        print(f"{farbe}: {text}{zusatz}")

    if sys.version_info >= (3, 11):
        zeile("GRUEN", f"Python {sys.version.split()[0]}")
    else:
        zeile("ROT", f"Python {sys.version.split()[0]}", "Python 3.11 oder neuer installieren.")

    if shutil.which("uv"):
        zeile("GRUEN", "uv verfügbar")
    else:
        zeile("ROT", "uv fehlt", "uv installieren: https://docs.astral.sh/uv/getting-started/installation/")

    for cmd in ("ffmpeg", "ffprobe"):
        if shutil.which(cmd):
            zeile("GRUEN", f"{cmd} verfügbar")
        else:
            zeile("ROT", f"{cmd} fehlt", f"{cmd} installieren, z. B. mit `brew install ffmpeg`.")

    try:
        lauf = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        filters = lauf.stdout
        fehlend = FILTER - {x for x in FILTER if x in filters}
        if not fehlend:
            zeile("GRUEN", "ffmpeg-Filter vollständig")
        else:
            zeile("ROT", "ffmpeg-Filter fehlen: " + ", ".join(sorted(fehlend)),
                  "ffmpeg neu installieren, es fehlt ein Codec- oder Filterpaket.")
    except Exception as e:
        zeile("ROT", f"ffmpeg-Filter nicht prüfbar: {e}", "ffmpeg installieren und erneut prüfen.")

    for rolle in konfig("marke").get("schriften", {}):
        try:
            schrift(rolle, 30)
            zeile("GRUEN", f"Schrift {rolle} ladbar")
        except Exception as e:
            zeile("ROT", f"Schrift {rolle} fehlt: {e}", f"Schriftdatei für '{rolle}' in schriften/ ablegen.")

    transkript_cfg = konfig("pipeline").get("transkript", {})
    paket = "mlx_whisper" if transkript_cfg.get("backend", "mlx") == "mlx" else "faster_whisper"
    if importlib.util.find_spec(paket):
        zeile("GRUEN", f"Transkript {paket} ladbar")
    else:
        zeile("ROT", f"Transkript {paket} fehlt", f"`uv sync` erneut laufen lassen, {paket} fehlt im Paket.")

    kanaele_cfg = konfig("kanaele")
    youtube_cfg = kanaele_cfg.get("youtube", {})
    if youtube_cfg.get("an") and youtube_cfg.get("weg") == "youtube_api":
        fehlend = [p for p in ("googleapiclient", "google_auth_oauthlib") if not importlib.util.find_spec(p)]
        if fehlend:
            zeile("ROT", "YouTube-Pakete fehlen: " + ", ".join(fehlend), "`uv sync --extra youtube`.")
        else:
            zeile("GRUEN", "YouTube-Pakete verfügbar")

    instagram_cfg = kanaele_cfg.get("instagram", {})
    if instagram_cfg.get("weg") == "instagram_api":
        stand = lesen(pfad("arbeit", "instagram_token.json"), {}) or {}
        ablauf_text = stand.get("laeuft_ab")
        ablauf = None
        if ablauf_text:
            try:
                ablauf = datetime.fromisoformat(ablauf_text)
            except ValueError:
                ablauf = None
        hinweis = ("`uv run pipeline instagram-token verlaengern` ausführen, danach eine "
                   "monatliche geplante Aufgabe dafür einrichten.")
        if ablauf is None:
            zeile("GELB", "Instagram-Token: kein Ablaufdatum bekannt", hinweis)
        elif ablauf <= jetzt():
            zeile("ROT", "Instagram-Token ist abgelaufen", hinweis)
        elif ablauf - jetzt() < timedelta(days=14):
            zeile("GELB", f"Instagram-Token läuft am {ablauf:%d.%m.%Y} ab", hinweis)
        else:
            zeile("GRUEN", f"Instagram-Token gültig bis {ablauf:%d.%m.%Y}")

    rechtschreib_cfg = konfig("pipeline").get("rechtschreibung", {})
    if not rechtschreib_cfg.get("an", False):
        zeile("GELB", "Rechtschreibprüfung ist aus",
              "[rechtschreibung] an = true in konfig/pipeline.toml setzen, wenn gewünscht.")
    else:
        dienst = rechtschreib_cfg.get("dienst") or "https://api.languagetool.org/v2/check"
        try:
            probe = requests.post(dienst, data={"text": "Das ist ein Test.", "language": "de-DE"}, timeout=5)
            probe.raise_for_status()
            zeile("GRUEN", f"Rechtschreibprüfung erreichbar ({dienst})")
        except Exception as e:
            zeile("GELB", f"Rechtschreibprüfung nicht erreichbar: {e}",
                  "Netz prüfen, oder [rechtschreibung] an = false setzen, wenn nicht gebraucht.")

    urteil_backend = konfig("pipeline").get("urteil", {}).get("backend", "claude")
    if urteil_backend == "ohne" or shutil.which(urteil_backend):
        zeile("GRUEN", f"Urteil {urteil_backend} verfügbar")
    else:
        zeile("ROT", f"Urteil {urteil_backend} fehlt",
              f"'{urteil_backend}' installieren oder in konfig/pipeline.toml anderes Backend eintragen.")

    beispiel = pfad(".env.example")
    if beispiel.exists():
        for zeile_text in beispiel.read_text(encoding="utf-8").splitlines():
            name = zeile_text.partition("=")[0].strip()
            if not name or name.startswith("#"):
                continue
            if os.environ.get(name):
                zeile("GRUEN", f"Schlüssel {name}: ja")
            else:
                zeile("GELB", f"Schlüssel {name}: nein", f"{name} in .env eintragen, wenn gebraucht.")

    for ordner in ("eingang", "arbeit", "ausgabe"):
        try:
            p = pfad(ordner)
            p.mkdir(parents=True, exist_ok=True)
            testdatei = p / ".schreibtest"
            testdatei.touch()
            testdatei.unlink()
            zeile("GRUEN", f"Ordner {ordner} beschreibbar")
        except Exception as e:
            zeile("ROT", f"Ordner {ordner} nicht beschreibbar: {e}",
                  f"Zugriffsrechte für {ordner}/ prüfen.")

    for ordner in konfig("pipeline").get("eingang", {}).get("weitere_ordner", []):
        p = Path(str(ordner)).expanduser()
        erreichbar = p.is_dir() and os.access(p, os.R_OK | os.X_OK)
        zeile("GRUEN" if erreichbar else "GELB", f"Eingangsordner {ordner}: {'ja' if erreichbar else 'nein'}",
              "Pfad und Zugriffsrechte prüfen.")

    # Dieselben Schwellen wie im README, Abschnitt Voraussetzungen: 30 GB ist der Zielwert
    # für lange Rohvideos, 10 GB die harte Untergrenze.
    frei_gb = shutil.disk_usage(pfad()).free / 1024**3
    if frei_gb >= 30:
        zeile("GRUEN", f"Freier Platz {frei_gb:.1f} GB")
    elif frei_gb >= 10:
        zeile("GELB", f"Freier Platz {frei_gb:.1f} GB", "Für lange Aufnahmen 30 GB anstreben.")
    else:
        zeile("ROT", f"Freier Platz {frei_gb:.1f} GB", "Platz freiräumen, mindestens 10 GB nötig.")

    return int(rot)
