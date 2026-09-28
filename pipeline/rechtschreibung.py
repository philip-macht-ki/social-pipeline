"""Rechtschreib- und Grammatikprüfung über LanguageTool.

Lehre aus dem Cashflow-Betrieb (28.09.2026, `insta-sop/pinterest_bauen.py`,
Funktion `rechtschreibung`): Tippfehler wie "Bestehene Folien" oder falsche
Zusammenschreibung wie "E Mail Entwurf" fallen dem Modellurteil selbst nicht
auf, weil es seinen eigenen Text für richtig hält. Deshalb prüft ein zweiter,
unabhängiger Dienst nach dem Urteil.

Geprüft werden nur Tippfehler (TYPOS), Grammatik (GRAMMAR), Zusammen- und
Getrenntschreibung (COMPOUNDING) und Groß-/Kleinschreibung (CASING); alles
andere (Stil, Kommasetzung als Empfehlung usw.) ist keine Fehlerkategorie im
Sinn dieser Prüfung. Die Regel UPPERCASE_SENTENCE_START ist ausgenommen, weil
Titelzeilen oft mitten im Satz anschließen und LanguageTool das sonst als
Fehler gegen Groß-/Kleinschreibung meldet, obwohl der Titel bewusst so steht.

Die Texte gehen als eigene Absätze (mit `\n\n` verbunden) in den Auftrag,
sonst hält LanguageTool das Satzende des einen Felds für den Satzanfang des
nächsten und schlägt fälschlich bei Kleinschreibung Alarm.

Hinweis: Die öffentliche LanguageTool-API (https://api.languagetool.org) hat
Mengengrenzen und bekommt dabei die Beitragstexte zu sehen. Wer das nicht
will, setzt `[rechtschreibung] an = false` in konfig/pipeline.toml oder trägt
dort unter `dienst` eine eigene, selbst betriebene LanguageTool-Instanz ein.
"""
from __future__ import annotations

import re

import requests

from .kern import konfig

KATEGORIEN = {"TYPOS", "GRAMMAR", "COMPOUNDING", "CASING"}

# Plattform- und Werkzeugnamen, die LanguageTool sonst als unbekannte Wörter
# markiert, obwohl sie in diesem Betrieb Fachbegriffe sind, keine Fehler.
WERKZEUGNAMEN = {
    "hook", "hooks", "prompt", "prompts", "reel", "reels", "short", "shorts",
    "pin", "pins", "karussell", "karussells", "caption", "captions",
    "instagram", "tiktok", "youtube", "pinterest", "threads",
}


def _ausnahmen() -> set[str]:
    marke = konfig("marke")
    cfg = konfig("pipeline").get("rechtschreibung", {})
    rohe = [marke.get("name", ""), marke.get("handle", ""), marke.get("wortmarke", "")]
    rohe += list(cfg.get("ausnahmen", []))
    ausnahmen = set(WERKZEUGNAMEN)
    for eintrag in rohe:
        for wort in re.findall(r"\S+", str(eintrag)):
            ausnahmen.add(wort.lower().strip(".,:;!?@"))
    return ausnahmen


def pruefe(felder: dict[str, str]) -> list[str]:
    """Schickt alle Werte von `felder` gemeinsam an LanguageTool (de-DE) und
    gibt eine Liste lesbarer Befunde zurück, leer wenn nichts auffällt.

    Ein Netzfehler bricht nichts ab: er kommt als ein einzelner Befund
    zurück ("Rechtschreibprüfung nicht erreichbar"), das Stück oder Bild läuft
    ohne Sperre weiter (siehe ARCHITEKTUR.md: "Nie still scheitern", aber auch
    kein Befund darf den Lauf stoppen).
    """
    cfg = konfig("pipeline").get("rechtschreibung", {})
    if not cfg.get("an", False):
        return []
    text = "\n\n".join(str(wert).strip() for wert in felder.values() if str(wert or "").strip())
    if not text:
        return []
    dienst = cfg.get("dienst") or "https://api.languagetool.org/v2/check"
    try:
        antwort = requests.post(dienst, data={"text": text, "language": "de-DE"}, timeout=40)
        daten = antwort.json()
    except Exception:  # noqa: BLE001 - jeder Netz- oder Formatfehler zählt gleich
        return ["Rechtschreibprüfung nicht erreichbar."]
    ausnahmen = _ausnahmen()
    befunde: list[str] = []
    for treffer in daten.get("matches") or []:
        regel = treffer.get("rule", {}) or {}
        if regel.get("category", {}).get("id") not in KATEGORIEN:
            continue
        if str(regel.get("id", "")).startswith("UPPERCASE_SENTENCE_START"):
            continue
        versatz, laenge = treffer.get("offset", 0), treffer.get("length", 0)
        wort = text[versatz : versatz + laenge]
        if wort.lower().strip(".,:;!?") in ausnahmen:
            continue
        vorschlaege = [r.get("value", "") for r in (treffer.get("replacements") or [])[:2] if r.get("value")]
        meldung = str(treffer.get("message", "")).strip()[:100]
        befund = f"„{wort}“: {meldung}" if meldung else f"„{wort}“: möglicher Fehler"
        if vorschlaege:
            befund += ", Vorschlag " + ", ".join(f"„{v}“" for v in vorschlaege)
        befunde.append(befund)
    return befunde
