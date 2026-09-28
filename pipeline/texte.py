"""Texte je Plattform. Grenzen werden nach dem Urteil immer im Code geprüft."""
from __future__ import annotations

import re
from pathlib import Path

from .kern import Ergebnis, konfig, lesen, log, pfad, schreiben, stueck_ordner, stuecke
from .urteil import frage, vorlage

VERBOTEN = ("–", "—", "teile das", "schick das an", "sende das an", "leite das weiter")


def _utm(link: str) -> str:
    return link + ("&" if "?" in link else "?") + "utm_source=pinterest&utm_medium=social&utm_campaign=pipeline"


def _saetze(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s|$)", text))


def _allgemein(text: str) -> str | None:
    kleinbuchstaben = text.lower()
    for verbotenes_wort in VERBOTEN:
        if verbotenes_wort in kleinbuchstaben:
            return f"Verbotene Formulierung gefunden: {verbotenes_wort}."
    return None


def pruefe_instagram(daten: object, hook: str, marke: dict, rezept: dict) -> str | None:
    if not isinstance(daten, dict) or not isinstance(daten.get("caption"), str):
        return "Instagram braucht caption als Text."
    caption = daten["caption"].strip()
    befund = _allgemein(caption)
    if befund:
        return befund
    if len(caption) > 2200:
        return f"Instagram-Caption ist {len(caption)} Zeichen, Obergrenze 2200."
    zeilen = [zeile.strip() for zeile in caption.splitlines() if zeile.strip()]
    if not zeilen:
        return "Die erste Zeile fehlt."
    hook_woerter = {wort.lower() for wort in re.findall(r"\w+", hook) if len(wort) > 3}
    erste_zeile_woerter = re.findall(r"\w+", zeilen[0].lower())
    if hook_woerter and not hook_woerter.intersection(erste_zeile_woerter):
        return "Die erste Zeile greift den Hook nicht erkennbar auf."
    hashtag_zeilen = [zeile for zeile in zeilen if re.fullmatch(r"(?:#\w+\s*)+", zeile)]
    if len(hashtag_zeilen) != 1:
        return "Instagram braucht genau eine Hashtag-Zeile."
    hashtag_anzahl = len(re.findall(r"#\w+", hashtag_zeilen[0]))
    if not 2 <= hashtag_anzahl <= 4:
        return f"Instagram hat {hashtag_anzahl} Hashtags statt 2 bis 4."
    zeilen_vor_hashtags = zeilen[:zeilen.index(hashtag_zeilen[0])]
    cta_zeile = marke.get("cta_zeile", "").strip()
    if cta_zeile and cta_zeile not in zeilen:
        return "Die CTA-Zeile fehlt."
    if not any(zeile.endswith("?") for zeile in zeilen_vor_hashtags):
        return "Vor CTA und Hashtags fehlt eine Frage."
    if rezept.get("von_stuecken", 1) > 1:
        erwartete_teilzeile = f"Teil {rezept.get('nr')} von {rezept.get('von_stuecken')}."
        if zeilen[-1] != erwartete_teilzeile:
            return "Mehrteiler-Zeile fehlt am Caption-Ende."
    return None


def pruefe_tiktok(daten: object) -> str | None:
    if not isinstance(daten, dict) or not isinstance(daten.get("caption"), str):
        return "TikTok braucht caption als Text."
    caption = daten["caption"]
    befund = _allgemein(caption)
    if befund:
        return befund
    if len(caption) > 2200:
        return f"TikTok-Text ist {len(caption)} Zeichen, Obergrenze 2200."
    if len(re.findall(r"#\w+", caption)) > 5:
        return "TikTok hat mehr als fünf Hashtags."
    if not ("link" in caption.lower() and "profil" in caption.lower()):
        return "TikTok verweist nicht auf den Link im Profil."
    if re.search(r"schreib\s+[A-ZÄÖÜ]{2,}.*kommentar", caption, re.I):
        return "TikTok enthält ein Kommentar-Codewort."
    return None


def pruefe_youtube(daten: object, link: str, hook: str) -> str | None:
    if not isinstance(daten, dict):
        return "YouTube braucht ein Objekt."
    titel = daten.get("titel")
    beschreibung = daten.get("beschreibung")
    if not isinstance(titel, str) or not isinstance(beschreibung, str):
        return "YouTube braucht Titel und Beschreibung."
    if len(titel) > 100:
        return "YouTube-Titel ist länger als 100 Zeichen."
    if titel.strip() == hook.strip():
        return "YouTube-Titel ist identisch mit dem Hook."
    if not 2 <= _saetze(beschreibung) <= 4:
        return "YouTube-Beschreibung braucht zwei bis vier Sätze."
    if link not in beschreibung:
        return "YouTube-Beschreibung enthält den Link nicht."
    return _allgemein(titel + "\n" + beschreibung)


def pruefe_pinterest(daten: object) -> str | None:
    """Prüft nur, was ein Urteil beisteuert: Titel und Beschreibung. Den Link
    mit UTM-Parametern setzt immer der Code (siehe `_machen`), nie das Modell.
    Das ist keine inhaltliche Entscheidung, also gehört sie nach ARCHITEKTUR.md
    ("Zeiten, Maße, Dateien... das ist Code") nicht ins Urteil, und ein Modell,
    das eine exakte Tracking-URL wortgenau nachbauen soll, scheitert ohnehin
    fast immer daran und löst nur unnötige Nachfragen aus."""
    if not isinstance(daten, dict):
        return "Pinterest braucht ein Objekt."
    titel = daten.get("titel")
    beschreibung = daten.get("beschreibung")
    if not isinstance(titel, str) or not isinstance(beschreibung, str):
        return "Pinterest braucht Titel und Beschreibung."
    if len(titel) > 100:
        return "Pinterest-Titel ist länger als 100 Zeichen."
    if not 60 <= len(beschreibung) <= 500:
        return f"Pinterest-Beschreibung hat {len(beschreibung)} statt 60 bis 500 Zeichen."
    return _allgemein(titel + "\n" + beschreibung)


def pruefe_threads(daten: object) -> str | None:
    if not isinstance(daten, dict) or not isinstance(daten.get("text"), str):
        return "Threads braucht text als Text."
    beitrag = daten["text"]
    befund = _allgemein(beitrag)
    if befund:
        return befund
    if len(beitrag) > 500:
        return "Threads-Text ist länger als 500 Zeichen."
    if len(re.findall(r"#\w+", beitrag)) != 1:
        return "Threads braucht genau einen Topic-Tag."
    if re.search(r"\b(reel|video oben|wie ich drüben sagte|auf instagram)\b", beitrag, re.I):
        return "Threads verweist auf einen anderen Beitrag."
    return None


def _fallbacks(rezept: dict, hook: str, marke: dict) -> dict:
    titel = (rezept.get("titel") or "Ein Gedanke für deinen Alltag").replace("\n", " ")[:90]
    aussage = (rezept.get("aussage") or hook or titel).strip()
    hashtags = " ".join(marke.get("hashtags", ["#ideen", "#alltag"])[:4]) or "#ideen #alltag"
    instagram_caption = f"{hook}\n\n{aussage}\n\nWas nimmst du daraus mit?"
    if marke.get("cta_zeile"):
        instagram_caption += "\n" + marke["cta_zeile"]
    instagram_caption += "\n" + hashtags
    if rezept.get("von_stuecken", 1) > 1:
        instagram_caption += f"\nTeil {rezept.get('nr')} von {rezept.get('von_stuecken')}."
    link = marke.get("link", "")
    pin_beschreibung = (aussage + " Dieser Pin fasst den Gedanken klar zusammen und gibt dir einen einfachen Startpunkt für die eigene Arbeit.")[:500]
    if len(pin_beschreibung) < 60:
        pin_beschreibung += " Für deinen nächsten konkreten Schritt."
    return {
        "instagram": {"caption": instagram_caption},
        "tiktok": {"caption": f"{aussage}\nMehr dazu über den Link im Profil. #ideen"},
        "youtube": {"titel": f"{titel}: ein klarer Impuls", "beschreibung": f"{aussage}. Nimm den Gedanken als Anlass für deinen nächsten Schritt. {link}"},
        "pinterest": {"titel": titel, "beschreibung": pin_beschreibung, "link": _utm(link)},
        "threads": {"text": f"{aussage} Was wäre dein nächster Schritt? #Selbstständig"},
    }


def _machen(ordner: Path) -> Ergebnis:
    rezept = lesen(ordner / "rezept.json", {})
    take = rezept.get("take") or ordner.parents[2].name
    saetze = lesen(pfad("arbeit", take, "saetze.json"), [])
    satztexte = [satz.get("text", "") for satz in saetze if isinstance(satz, dict)]
    hook_daten = rezept.get("hook") or {}
    hook = ""
    if isinstance(hook_daten, dict):
        satznummer = hook_daten.get("von_satz")
        hook = next((satz.get("text", "") for satz in saetze if satz.get("nr") == satznummer), "")
    hook = hook or (satztexte[0] if satztexte else rezept.get("aussage", ""))
    marke = konfig("marke")
    rueckfaelle = _fallbacks(rezept, hook, marke)
    # Mehrteiler-Zeile und CTA sind feste Textbausteine (Code), keine Modellentscheidung.
    # Sie stehen trotzdem im Auftrag, sonst rät das Modell danach und die Prüfung
    # schlägt beim ersten Versuch fast immer fehl (unnötige Nachfrage, siehe urteil.frage).
    teil_zeile = ""
    if rezept.get("von_stuecken", 1) > 1:
        teil_zeile = f"Teil {rezept.get('nr')} von {rezept.get('von_stuecken')}."
    vorlagenwerte = {
        "titel": rezept.get("titel", ""), "aussage": rezept.get("aussage", ""), "hook": hook,
        "saetze": " ".join(satztexte), "link": marke.get("link", ""),
        "cta_zeile": marke.get("cta_zeile", ""), "hashtags": " ".join(marke.get("hashtags", [])[:4]),
        "teil_zeile": teil_zeile,
    }
    ergebnisse = {}
    pruefungen = [
        ("instagram", "caption_instagram", lambda antwort: pruefe_instagram(antwort, hook, marke, rezept)),
        ("tiktok", "caption_tiktok", pruefe_tiktok),
        ("youtube", "youtube", lambda antwort: pruefe_youtube(antwort, marke.get("link", ""), hook)),
        ("pinterest", "pinterest", pruefe_pinterest),
        ("threads", "threads", pruefe_threads),
    ]
    befunde = []
    for plattform, vorlagenname, pruefung in pruefungen:
        ergebnisse[plattform] = frage(vorlage(vorlagenname, **vorlagenwerte), zweck="texte_" + plattform, rueckfall=lambda name=plattform: rueckfaelle[name], pruefe=pruefung)
        befund = pruefung(ergebnisse[plattform])
        if befund:
            befunde.append(f"{plattform}: {befund}")
            ergebnisse[plattform] = rueckfaelle[plattform]
    # Der Link mit UTM-Parametern ist immer der Code, nie das Modellergebnis (siehe pruefe_pinterest).
    if isinstance(ergebnisse.get("pinterest"), dict):
        ergebnisse["pinterest"]["link"] = _utm(marke.get("link", ""))
    ergebnisse["befunde"] = befunde
    schreiben(pfad("ausgabe", rezept.get("id", f"{take}-{ordner.name}"), "texte.json"), ergebnisse)
    return Ergebnis("befund" if befunde else "ok", "; ".join(befunde) or "Texte gebaut.")


def befehl(args) -> int:
    ziel = (getattr(args, "ziel", []) or [None])[0]
    ordner = [stueck_ordner(ziel)] if ziel else stuecke()
    if not ordner:
        log("nichts: keine Stücke für Texte.")
        return 0
    for stueck in ordner:
        rezept = lesen(stueck / "rezept.json", {})
        ausgabedatei = pfad("ausgabe", rezept.get("id", stueck.name), "texte.json")
        if ausgabedatei.exists() and not getattr(args, "neu", False):
            log(f"nichts: {stueck.name}, Texte schon vorhanden.")
            continue
        try:
            ergebnis = _machen(stueck)
            log(f"{ergebnis.status}: {stueck.name}: {ergebnis.meldung}")
        except Exception as fehler:
            log(f"fehler: {stueck.name}: {fehler}")
    return 0
