"""uv run pipeline transkript [take …] [--neu]

Whisper-Wortzeiten und Satzkanten. Schreibt arbeit/<take>/woerter.json,
transkript.txt und saetze.json.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import urteil
from .kern import Ergebnis, konfig, lauf, lesen, schreiben, takes


def saetze(woerter: list[dict]) -> list[dict]:
    """Sätze enden am Satzzeichen oder an 0,45 Sekunden Stille."""
    aus, start = [], 0
    for i, wort in enumerate(woerter):
        pause = i + 1 < len(woerter) and float(woerter[i + 1]["s"]) - float(wort["e"]) >= .45
        if re.search(r"[.!?][\"')\]]*$", str(wort["w"])) or pause or i == len(woerter) - 1:
            teil = woerter[start:i + 1]
            aus.append({"nr": len(aus), "von_wort": start, "bis_wort": i,
                        "s": teil[0]["s"], "e": teil[-1]["e"],
                        "text": " ".join(str(w["w"]) for w in teil)})
            start = i + 1
    return aus


def _normal(text: str) -> list[str]:
    return re.findall(r"[\wäöüß]+", text.lower())


def satzzeichen(woerter: list[dict]) -> list[dict]:
    """Setzt fehlende Satzzeichen per Modell nach.

    Whisper liefert bei langen Aufnahmen nur rund 3 % Satzzeichen, und ohne
    sie schneidet der Themenschnitt mitten in Sätze (siehe zerlegen.py,
    23.09.2026). Ist schon reichlich Interpunktion da, bleibt der Text
    unangetastet.
    """
    if sum(bool(re.search(r"[.!?]$", w["w"])) for w in woerter) * 25 >= len(woerter):
        return woerter
    aus = [dict(w) for w in woerter]
    for start in range(0, len(aus), 70):
        block = aus[start:start + 70]
        original = " ".join(w["w"] for w in block)
        try:
            antwort = urteil.frage(urteil.vorlage("satzzeichen", text=original), zweck="satzzeichen",
                rueckfall=lambda: {"text": original})
            text = antwort.get("text", "") if isinstance(antwort, dict) else ""
            # Nur übernehmen, wenn dieselben Wörter in derselben Zahl zurückkommen:
            # das Modell darf Zeichen setzen, aber keinen Text erfinden.
            if _normal(text) == _normal(original):
                neue = text.split()
                if len(neue) == len(block):
                    for wort, neu in zip(block, neue):
                        wort["w"] = neu
        except Exception:
            pass
    return aus


def _transkribiere(audio: Path, cfg: dict) -> list[dict]:
    backend = cfg.get("backend", "mlx")
    if backend == "mlx":
        import mlx_whisper
        modell = cfg.get("modell", "mlx-community/whisper-large-v3-turbo")
        daten = mlx_whisper.transcribe(str(audio), path_or_hf_repo=modell, language=cfg.get("sprache", "de"),
            word_timestamps=True, condition_on_previous_text=False)
        return [{"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
                for seg in daten.get("segments", [])
                for w in seg.get("words", []) if w.get("word", "").strip()]
    if backend == "faster":
        from faster_whisper import WhisperModel
        modell = WhisperModel(cfg.get("modell", "small"))
        segmente, _ = modell.transcribe(str(audio), language=cfg.get("sprache", "de"),
            word_timestamps=True, condition_on_previous_text=False)
        return [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)}
                for seg in segmente for w in (seg.words or []) if w.word.strip()]
    raise RuntimeError(f"Unbekanntes Transkript-Backend: {backend}")


def verarbeite(take: Path, neu: bool = False) -> Ergebnis:
    if (take / "woerter.json").exists() and not neu:
        return Ergebnis("nichts", f"nichts: {take.name} ist schon transkribiert")
    info = lesen(take / "take.json", {})
    quelle = take / info.get("quelle", "")
    audio = take / "audio.wav"
    try:
        lauf(["ffmpeg", "-y", "-i", quelle, "-ar", "16000", "-ac", "1", audio])
        cfg = dict(konfig("pipeline").get("transkript", {}))
        cfg.setdefault("sprache", konfig("pipeline").get("sprache", "de"))
        woerter = satzzeichen(_transkribiere(audio, cfg))
        schreiben(take / "woerter.json", woerter)
        (take / "transkript.txt").write_text(" ".join(w["w"] for w in woerter) + "\n", encoding="utf-8")
        schreiben(take / "saetze.json", saetze(woerter))
        return Ergebnis("ok", f"ok: {take.name} mit {len(woerter)} Wörtern transkribiert")
    except Exception as e:
        return Ergebnis("fehler", f"fehler: Transkript {take.name}: {e}")


def befehl(args) -> int:
    ziel = [t for t in takes() if not args.ziel or t.name in args.ziel]
    ergebnisse = [verarbeite(t, args.neu) for t in ziel]
    ergebnisse = ergebnisse or [Ergebnis("nichts", "nichts: kein Take für Transkript")]
    for e in ergebnisse:
        print(e.meldung)
    return int(any(e.status == "fehler" for e in ergebnisse))
