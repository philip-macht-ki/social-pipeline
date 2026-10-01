"""uv run pipeline transkript [take …] [--neu]

Whisper-Wortzeiten und Satzkanten. Schreibt arbeit/<take>/woerter.json,
transkript.txt und saetze.json.
"""
from __future__ import annotations

import difflib
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

    Die Antwort wird per difflib auf die Originalwörter ausgerichtet. Früher
    fiel der ganze Block, sobald das Modell ein einziges Wort anders schrieb
    ("e mail strecke" -> "E-Mail-Strecke"), und genau dort fehlte danach der
    Satz, der der beste Hook gewesen wäre (01.10.2026). Übernommen werden nur
    Zeichen, die sich eindeutig zuordnen lassen; die Wörter selbst bleiben.
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
            zeichen_uebernehmen(block, text.split())
        except Exception:
            pass
    return aus


def _nackt(wort: str) -> str:
    return "".join(_normal(wort))


def zeichen_uebernehmen(block: list[dict], neue: list[str]) -> int:
    """Hängt Satzzeichen aus `neue` an die passenden Wörter in `block`.

    Gleiche Wörter bekommen ihr Zeichen direkt; zusammengezogene oder
    getrennte Wörter mit denselben Buchstaben geben es an das letzte
    Originalwort. Weicht die Antwort im Großen ab (unter 85 % zuordenbar),
    bleibt der Block unverändert. Gibt die Zahl gesetzter Zeichen zurück.
    """
    a = [_nackt(w["w"]) for w in block]
    b = [_nackt(w) for w in neue]
    paare, zugeordnet = [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            paare += [(i1 + k, neue[j1 + k]) for k in range(i2 - i1)]
            zugeordnet += i2 - i1
        elif tag == "replace" and "".join(a[i1:i2]) == "".join(b[j1:j2]):
            paare.append((i2 - 1, neue[j2 - 1]))
            zugeordnet += i2 - i1
    if zugeordnet < .85 * len(block):
        return 0
    gesetzt = 0
    for i, wort in paare:
        zeichen = re.search(r"[.,!?;:]+$", wort)
        if zeichen and not re.search(r"[.,!?;:]$", block[i]["w"]):
            block[i]["w"] = block[i]["w"] + zeichen.group(0)
            gesetzt += 1
    return gesetzt


FENSTER = (12.0, 22.0)   # frühestens / spätestens nach so vielen Sekunden schneiden
SR = 16000


def schnitte(woerter: list[dict], dauer: float, fenster: tuple[float, float] = FENSTER) -> list[float]:
    """Schnittpunkte für die Fenster, jeweils in der Mitte der längsten Pause."""
    aus, start = [], 0.0
    while dauer - start > fenster[1]:
        luecken = [(woerter[i + 1]["s"] - woerter[i]["e"], i) for i in range(len(woerter) - 1)
                   if start + fenster[0] <= woerter[i]["e"] and woerter[i + 1]["s"] <= start + fenster[1]]
        if luecken:
            _, i = max(luecken)
            t = (woerter[i]["e"] + woerter[i + 1]["s"]) / 2
        else:
            t = start + fenster[1]
        aus.append(t)
        start = t
    return aus


def _hoerer(cfg: dict):
    """Gibt (Audio laden, hören) für das eingestellte Backend zurück."""
    backend = cfg.get("backend", "mlx")
    sprache = cfg.get("sprache", "de")
    if backend == "mlx":
        import mlx_whisper
        from mlx_whisper.audio import load_audio
        modell = cfg.get("modell", "mlx-community/whisper-large-v3-turbo")

        def hoeren(audio, prompt=None):
            daten = mlx_whisper.transcribe(audio, path_or_hf_repo=modell, language=sprache,
                word_timestamps=True, condition_on_previous_text=False, initial_prompt=prompt)
            return [{"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
                    for seg in daten.get("segments", [])
                    for w in seg.get("words", []) if w.get("word", "").strip()]
        return load_audio, hoeren
    if backend == "faster":
        from faster_whisper import WhisperModel, decode_audio
        modell = WhisperModel(cfg.get("modell", "small"))

        def hoeren(audio, prompt=None):
            segmente, _ = modell.transcribe(audio, language=sprache, word_timestamps=True,
                condition_on_previous_text=False, initial_prompt=prompt)
            return [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)}
                    for seg in segmente for w in (seg.words or []) if w.word.strip()]
        return lambda pfad: decode_audio(pfad, sampling_rate=SR), hoeren
    raise RuntimeError(f"Unbekanntes Transkript-Backend: {backend}")


def _transkribiere(audio: Path, cfg: dict) -> list[dict]:
    """Whisper in Fenstern von 12 bis 22 Sekunden, geschnitten in Sprechpausen.

    Am Stück über eine lange Aufnahme verliert Whisper nach einer Weile
    Satzzeichen und Großschreibung und verhört sich öfter. Im eigenen Betrieb
    hatte eine Aufnahme am 30.09.2026 auf 331 Wörtern vier Satzenden und
    "Körbchen ist King" statt "Köpfchen ist King" im Untertitel. In Fenstern:
    23 Satzenden, beide Wörter richtig. Kürzere Fenster (10 bis 18 s)
    erfanden ein Wort, längere (18 bis 30 s) ließen Passagen ohne Punkte.
    Der Lauf am Stück dient nur dazu, die Pausen zu finden, und als Rückfall.
    """
    laden, hoeren = _hoerer(cfg)
    ton = laden(str(audio))
    dauer = len(ton) / SR
    erst = hoeren(ton)
    if not cfg.get("fenster", True):
        return erst
    prompt = cfg.get("prompt") or None
    grenzen = [0.0] + schnitte(erst, dauer) + [dauer]
    woerter = []
    for a, b in zip(grenzen, grenzen[1:]):
        for w in hoeren(ton[int(a * SR):int(b * SR)], prompt):
            woerter.append({"w": w["w"], "s": round(w["s"] + a, 3), "e": round(w["e"] + a, 3)})
    woerter.sort(key=lambda w: w["s"])
    # Weicht die Wortzahl um mehr als zehn Prozent ab, hat ein Fenster
    # halluziniert oder verschluckt: dann lieber der Lauf am Stück.
    if erst and abs(len(woerter) - len(erst)) > .10 * len(erst):
        return erst
    return woerter


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
