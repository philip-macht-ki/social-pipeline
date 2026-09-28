"""uv run pipeline bilder [take]

Bildbeiträge je Take: ein Instagram-Bild, ein Karussell, ein TikTok-Fotobeitrag,
Pinterest-Pins (je_lauf in konfig/stile.toml) und Threads-Texte. Welcher Stil
drankommt, entscheidet redaktion.auswahl() im Wechsel; was draufsteht, schreibt
das Modell in einem Aufruf je Take (redaktion.texte_fuer_take). Die Layouts
leben in den Plattform-Modulen instagram, pinterest, tiktok, threads.

Passt ein Text nicht ins Bild, wird einmal mit dem Befund in Pixeln
nachgefragt; passt er dann immer noch nicht, entsteht kein Bild, sondern ein
Befund im Protokoll. Ein halbes Bild geht nie raus.
"""
from __future__ import annotations

import re
from datetime import date

from .. import rechtschreibung
from ..kern import konfig, lesen, log, pfad, schreiben, takes
from . import instagram, pinterest, threads, tiktok
from .gemeinsam import gesperrt
from . import redaktion
from ..urteil import frage
import json


def pinterest_auswahl(benutzt: dict, konfiguration: dict, heute: str | None = None):
    heute = heute or date.today().isoformat()
    pinterest_konfiguration = konfiguration.get("pinterest", {})
    gesperrte_stile = set(pinterest_konfiguration.get("gesperrt", []))
    kandidaten = []
    for reihenfolge, stil in enumerate(pinterest_konfiguration.get("pin", [])):
        stil_info = benutzt.get(stil, {})
        # Kein Stil zweimal am Tag: Die Rotation bleibt nachvollziehbar und vermeidet Wiederholungen.
        if stil not in gesperrte_stile and stil_info.get("datum") != heute:
            kandidaten.append((stil_info.get("anzahl", 0), reihenfolge, stil))
    return [kandidat[2] for kandidat in sorted(kandidaten)[:pinterest_konfiguration.get("je_lauf", 2)]]


def _save(im, ordner, nummer: int = 1):
    ordner.mkdir(parents=True, exist_ok=True)
    dateiname = f"{nummer:02d}.jpg"
    im.convert("RGB").save(ordner / dateiname, "JPEG", quality=90, subsampling=0)
    return dateiname


def _manifest(ident: str, take: str, plattform: str, art: str, stil: str, dateien: list, texte: dict, befunde: list | None = None):
    befunde = befunde or []
    return {"id": ident, "take": take, "plattform": plattform, "art": art, "stil": stil, "dateien": dateien, "texte": texte, "status": "befund" if befunde else "fertig", "befunde": befunde}


def _felder_fuer_renderer(plattform: str, felder: dict, take: str, stil: str) -> dict:
    """Übersetzt die Modellfelder in die Namen, die die Renderer lesen."""
    daten = dict(felder)
    daten.setdefault("saetze", felder.get("punkte", []))
    if "antwort" in felder:
        daten.setdefault("aussage", felder["antwort"])
    if "zahl" in felder:
        daten.setdefault("text", f"{felder['zahl']} {felder.get('aussage', '')}")
    if plattform == "instagram" and stil == "zitat_standbild":
        daten["standbild"] = redaktion.standbild(take, redaktion.satz_nr(felder.get("satz_nr", "")))
    daten["handle"] = konfig("marke").get("handle", "")
    return daten


def _rendern(plattform: str, art: str, stil: str, daten: dict):
    """(bilder, befund). bilder ist eine Liste, bei Einzelbildern mit einem Bild."""
    if art == "karussell":
        folien, befund = instagram.karussell(stil, daten, max(5, min(8, len(daten.get("punkte", [])) + 2)))
        return (folien if folien and not befund else []), befund
    if plattform == "instagram":
        bild, befund = instagram.bild_stil(stil, daten)
    elif plattform == "tiktok":
        bild, befund = tiktok.foto_stil(stil, daten)
    elif plattform == "pinterest":
        bild, befund = pinterest.pin(stil, daten)
    elif plattform == "threads" and stil == "bild_zeile":
        bild, befund = threads.zitatkarte(daten.get("text", ""))
    else:
        return [], ""
    return ([bild] if bild is not None and not befund else []), befund


# Felder, deren Satzzahl beim Kürzen unverändert bleiben muss (an . ! ? gezählt).
TITELFELDER = {"titel", "pin_titel", "frage"}


def _saetze_zahl(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s|$)", str(text or "")))


def _kuerzung_gueltig(alt: dict, neu: dict) -> bool:
    """Kürzen darf keine Felder verlieren und keine Listen verkürzen; Titelfelder
    behalten ihre Satzzahl. Sonst hat das Modell nicht gekürzt, sondern Inhalt
    gestrichen (Lehre aus dem Cashflow-Betrieb, 28.09.2026:
    `insta-sop/pinterest_bauen.py`, dort per Pixelmessung im Bild entdeckt,
    hier vorher als Strukturprüfung, damit erst gar kein beschädigtes Bild
    entsteht)."""
    for schluessel, wert in alt.items():
        if schluessel not in neu:
            return False
        if isinstance(wert, list) and len(neu.get(schluessel) or []) < len(wert):
            return False
        if schluessel in TITELFELDER and isinstance(wert, str):
            if _saetze_zahl(neu.get(schluessel)) != _saetze_zahl(wert):
                return False
    return True


def _kuerzen(plattform: str, stil: str, felder: dict, befund: str) -> tuple[dict | None, str | None]:
    """Eine Nachfrage mit dem Pixelbefund. Gibt (neue Felder, None) zurück, oder
    (None, Grund) wenn keine Antwort kam oder sie die Struktur verletzt hat."""
    auftrag = (f"Diese Bildtexte für den Stil {plattform}/{stil} passen nicht ins Bild. "
               f"Befund: {befund}\nKürze so, dass es passt. Gleiche Aussage, gleiche Felder, "
               f"Zahl im Titel gleich der Zahl der Punkte. Nur JSON mit den Feldern.\n"
               + json.dumps(felder, ensure_ascii=False))
    try:
        neu = frage(auftrag, zweck="bildtexte_kuerzen", rueckfall=lambda: None)
    except Exception:
        return None, None
    if not isinstance(neu, dict):
        return None, None
    if not _kuerzung_gueltig(felder, neu):
        return None, "Kürzung hat Inhalt gestrichen"
    return neu, None


def _textfelder(eintrag: dict) -> dict[str, str]:
    """Alle Textstücke eines Bildeintrags, flach, für die Rechtschreibprüfung."""
    ausgabe: dict[str, str] = {}
    for schluessel, wert in (eintrag.get("felder") or {}).items():
        if isinstance(wert, str):
            ausgabe[schluessel] = wert
        elif isinstance(wert, list):
            for index, teil in enumerate(wert):
                if isinstance(teil, str):
                    ausgabe[f"{schluessel}_{index}"] = teil
    for schluessel in ("text", "pin_titel"):
        if isinstance(eintrag.get(schluessel), str):
            ausgabe[schluessel] = eintrag[schluessel]
    return ausgabe


def _rechtschreibung_pruefen(ident: str, eintrag: dict) -> list[str]:
    """Rechtschreibprüfung nach dem Modellurteil, wie in texte.py: eine
    Nachfrage mit dem Befund, dann erneut prüfen. Bleiben Fehler, bleiben sie
    als Befund am Bild stehen; das Bild wird trotzdem gebaut (ARCHITEKTUR.md:
    ein Befund stoppt nichts, er muss sichtbar sein)."""
    befunde = rechtschreibung.pruefe(_textfelder(eintrag))
    if not befunde:
        return []
    auftrag = (
        f"Dieser Bildbeitrag ({ident}, JSON) hat Rechtschreib- oder Grammatikfehler:\n- "
        + "\n- ".join(befunde)
        + "\nKorrigiere genau das. Gleiche Aussage, gleiche Felder, gleiche Anzahl Punkte. "
          "Antworte nur mit dem vollständigen, korrigierten JSON-Objekt.\n\n"
        + json.dumps(eintrag, ensure_ascii=False)
    )
    try:
        neu = frage(auftrag, zweck="rechtschreibung_bild", rueckfall=lambda: None)
    except Exception:
        neu = None
    if not isinstance(neu, dict):
        return befunde
    eintrag.update({k: v for k, v in neu.items() if k in ("felder", "text", "pin_titel")})
    return rechtschreibung.pruefe(_textfelder(eintrag))


def _texte_je_plattform(plattform: str, eintrag: dict) -> dict:
    text = str(eintrag.get("text") or eintrag.get("felder", {}).get("text", "")).strip()
    if plattform == "pinterest":
        link = konfig("marke").get("link", "")
        link += ("&" if "?" in link else "?") + "utm_source=pinterest&utm_medium=social&utm_campaign=pipeline"
        titel = str(eintrag.get("pin_titel") or eintrag.get("felder", {}).get("titel", ""))[:100]
        return {"titel": titel, "beschreibung": text[:500], "text": text[:500], "link": link}
    return {"text": text, "titel": str(eintrag.get("felder", {}).get("titel", ""))[:100]}


def befehl(args) -> int:
    ziel = (getattr(args, "ziel", []) or [None])[0]
    neu = getattr(args, "neu", False)
    fertig_takes = [t for t in takes() if (not ziel or t.name == ziel) and list((t / "stuecke").glob("*/rezept.json"))]
    if not fertig_takes:
        log("nichts: kein zerlegter Take für Bilder.")
        return 0
    fehler = 0
    for take in fertig_takes:
        merker = take / "bilder.json"
        if merker.exists() and not neu:
            continue
        benutzt = lesen(pfad("arbeit", "stile_benutzt.json"), {}) or {}
        gewuenscht = redaktion.plan_fuer_take(benutzt)
        if not gewuenscht:
            log(f"nichts: {take.name}: keine Stile frei (alle heute schon benutzt oder gesperrt).")
            continue
        try:
            antwort = redaktion.texte_fuer_take(take.name, gewuenscht)
        except Exception as e:
            log(f"fehler: {take.name}: keine Bildtexte ({e})")
            fehler += 1
            continue
        erledigt = []
        for eintrag in antwort.get("stile", []):
            plattform, stil = eintrag.get("plattform"), eintrag.get("stil")
            art = next((a for p, a, s in gewuenscht if p == plattform and s == stil), None)
            if not art:
                continue
            ident = f"{take.name}-{plattform}-{stil}"
            if eintrag.get("passt_nicht"):
                log(f"befund: {ident}: passt nicht zu diesem Material ({eintrag['passt_nicht']})")
                continue
            rechtschreib_befunde = _rechtschreibung_pruefen(ident, eintrag)
            felder = eintrag.get("felder", {}) or {}
            ordner = pfad("ausgabe", "bilder", ident)
            dateien: list[str] = []
            if not (plattform == "threads" and stil != "bild_zeile"):
                bilder, befund = _rendern(plattform, art, stil, _felder_fuer_renderer(plattform, felder, take.name, stil))
                if not bilder and befund:
                    gekuerzt, kuerzungs_befund = _kuerzen(plattform, stil, felder, befund)
                    if gekuerzt:
                        felder = gekuerzt
                        bilder, befund = _rendern(plattform, art, stil,
                                                  _felder_fuer_renderer(plattform, felder, take.name, stil))
                    elif kuerzungs_befund:
                        befund = kuerzungs_befund
                if not bilder:
                    log(f"befund: {ident}: kein Bild ({befund or 'Renderer lieferte nichts'})")
                    continue
                dateien = [_save(bild, ordner, nummer + 1) for nummer, bild in enumerate(bilder)]
            if plattform == "threads" and not eintrag.get("text"):
                eintrag["text"] = felder.get("text", "")
            texte = {plattform: _texte_je_plattform(plattform, eintrag)}
            schreiben(ordner / "bild.json", _manifest(ident, take.name, plattform, "text" if plattform == "threads" else art,
                                                      stil, dateien, texte, rechtschreib_befunde))
            redaktion.vermerken(benutzt, plattform, stil)
            erledigt.append(ident)
            status = "befund" if rechtschreib_befunde else "ok"
            log(f"{status}: {ident} ({len(dateien)} Bild{'er' if len(dateien) != 1 else ''})"
                + ("; " + "; ".join(rechtschreib_befunde) if rechtschreib_befunde else ""))
        schreiben(merker, {"gebaut": erledigt})
    return 1 if fehler else 0
