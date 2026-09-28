"""Welche Bildstile ein Take bekommt und was darauf steht.

Zwei Entscheidungen, sauber getrennt:
- **Code wählt die Stile.** Je Plattform und Art der am wenigsten benutzte Stil,
  kein Stil zweimal am selben Tag, gesperrte nie. So wechseln sich die Formen
  ab, statt dass jeder Take alles auf einmal erzeugt.
- **Das Modell schreibt die Texte**, in einem Aufruf je Take: Bildtexte und
  den Beitragstext je Plattform, nur aus dem, was in der Aufnahme gesagt wurde.
  Kann ein Stil aus dem Material nicht ehrlich gefüllt werden (keine 9 Beispiele
  für das Raster, keine genannte Zahl, keine Quelle für eine Statistik), sagt
  das Modell "passt_nicht", und der Stil fällt für diesen Take aus.

Ohne Modell (Urteil-Backend "ohne") entstehen einfache Texte aus den Sätzen.
"""
from __future__ import annotations

import json
import re
from datetime import date

from ..kern import konfig, lesen, pfad, schreiben
from ..urteil import frage, vorlage

# Wie viele Stile je Take gebaut werden. Pinterest nimmt je_lauf aus stile.toml.
JE_TAKE = {("instagram", "bild"): 1, ("instagram", "karussell"): 1,
           ("tiktok", "fotobeitrag"): 1, ("threads", "text"): 2}

# Die Felder, die jeder Stil braucht. Steht so auch im Auftrag ans Modell.
FELDER = {
    "instagram/zitat_standbild": '{"aussage": "ein Satz, fast wörtlich gesagt, höchstens 120 Zeichen", "satz_nr": <Nummer des Satzes, zu dem das Standbild passt>}',
    "instagram/zahl": '{"zahl": "eine Zahl, die in der Aufnahme genannt wurde", "aussage": "ein Satz dazu"}',
    "instagram/einwand": '{"einwand": "ein typischer Einwand der Zielgruppe", "antwort": "die Antwort aus der Aufnahme"}',
    "instagram/vorher_nachher": '{"vorher": "wie es vorher war", "nachher": "wie es danach ist"}',
    "instagram/raster": '{"titel": "kurze Überschrift mit der Zahl 9", "punkte": ["genau 9 kurze Beispiele, je höchstens 6 Wörter"]}',
    "instagram/notiz": '{"punkte": ["3 kurze Zeilen, je höchstens 5 Wörter"]}',
    "instagram/schritte": '{"titel": "Titel des Karussells", "punkte": ["4 bis 6 Folien, je ein Satz"], "frage": "Frage auf der letzten Folie"}',
    "instagram/kette": '{"titel": "Titel", "punkte": ["4 bis 6 Glieder einer Kette, je ein kurzer Satz"], "frage": "Frage am Ende"}',
    "instagram/woche_hell": '{"titel": "Titel", "punkte": ["4 bis 6 Folien"], "frage": "Frage", "quelle": "Primärquelle, die in der Aufnahme genannt wurde"}',
    "tiktok/foto_schritte": '{"titel": "kurzer Titel", "saetze": ["genau 3 Schritte, je ein kurzer Satz"]}',
    "tiktok/foto_zitat": '{"aussage": "ein Satz, fast wörtlich gesagt"}',
    "pinterest/spickzettel": '{"titel": "Titel mit der Zahl der Punkte", "unter": "kurzer Merksatz", "punkte": ["bis 7 kurze Punkte"]}',
    "pinterest/szene": '{"titel": "Schlagzeile, zwei kurze Zeilen", "punkte": ["genau 3 Schritte"]}',
    "pinterest/notizbuch": '{"titel": "Titel mit der Zahl der Punkte", "punkte": ["bis 6 kurze Punkte"]}',
    "pinterest/editorial": '{"titel": "Titel mit der Zahl der Punkte", "zahl": "<Zahl der Punkte>", "punkte": ["bis 4 kurze Punkte"]}',
    "pinterest/typomix": '{"notiz": "ein Wort in Schreibschrift", "titel": "Titel", "punkte": ["bis 5 kurze Punkte"]}',
    "pinterest/tabelle": '{"titel": "Titel", "punkte": ["bis 6 Paare als \\"Aufgabe | So hilft es\\""]}',
    "pinterest/toolraster": '{"titel": "Titel mit der Zahl 9", "punkte": ["genau 9 Kacheln als \\"Name | was es tut\\""]}',
    "pinterest/statistik": '{"titel": "Aussage der Zahl", "zahl": "Hauptzahl", "statistik": [["Beschriftung", <Wert>]], "quelle": "genannte Primärquelle"}',
    "threads/merksatz": '{"text": "ein Merksatz mit einem Satz Erklärung"}',
    "threads/einwand": '{"text": "Einwand, dann Antwort"}',
    "threads/zahl": '{"text": "eine genannte Zahl und was sie bedeutet"}',
    "threads/frage": '{"text": "eine offene Frage an die Leser, mit einem Satz Kontext"}',
    "threads/kette": '{"text": "3 bis 5 kurze Schritte als Kette"}',
    "threads/bild_zeile": '{"text": "ein Satz, der auch auf einem Bild stehen kann"}',
}

TEXTFELD = {
    "instagram": '"text": "Instagram-Caption: erste Zeile packt, kurze Absätze, eine Frage, dann {cta}, dann genau eine Zeile mit 2 bis 4 Hashtags"',
    "tiktok": '"text": "TikTok-Text, höchstens 300 Zeichen, höchstens 5 Hashtags, Verweis auf den Link im Profil"',
    "pinterest": '"pin_titel": "Pinterest-Titel, höchstens 100 Zeichen", "text": "Pinterest-Beschreibung, 60 bis 500 Zeichen"',
    "threads": "",
}


def _schluessel(plattform: str, stil: str) -> str:
    # Pinterest zählt unter dem blanken Stilnamen, wie in pinterest_auswahl().
    return stil if plattform == "pinterest" else f"{plattform}/{stil}"


def auswahl(plattform: str, art: str, anzahl: int, benutzt: dict, heute: str | None = None) -> list[str]:
    """Die `anzahl` am wenigsten benutzten Stile, keiner heute schon, keiner gesperrt."""
    heute = heute or date.today().isoformat()
    abschnitt = konfig("stile").get(plattform, {})
    gesperrt = set(abschnitt.get("gesperrt", []))
    kandidaten = []
    for reihe, stil in enumerate(abschnitt.get(art, [])):
        info = benutzt.get(_schluessel(plattform, stil), {})
        if stil in gesperrt or info.get("datum") == heute:
            continue
        kandidaten.append((info.get("anzahl", 0), reihe, stil))
    return [k[2] for k in sorted(kandidaten)[:anzahl]]


def vermerken(benutzt: dict, plattform: str, stil: str) -> None:
    k = _schluessel(plattform, stil)
    benutzt[k] = {"anzahl": benutzt.get(k, {}).get("anzahl", 0) + 1, "datum": date.today().isoformat()}
    schreiben(pfad("arbeit", "stile_benutzt.json"), benutzt)


def plan_fuer_take(benutzt: dict) -> list[tuple[str, str, str]]:
    """[(plattform, art, stil), …] für einen Take, nur für eingeschaltete Plattformen."""
    kanaele = konfig("kanaele")
    je_lauf_pins = konfig("stile").get("pinterest", {}).get("je_lauf", 2)
    wahl = []
    for (plattform, art), anzahl in list(JE_TAKE.items()) + [(("pinterest", "pin"), je_lauf_pins)]:
        if not kanaele.get(plattform, {}).get("an", False):
            continue
        for stil in auswahl(plattform, art, anzahl, benutzt):
            wahl.append((plattform, art, stil))
    return wahl


def _nummeriert(saetze: list[dict]) -> str:
    return "\n".join(f"{s.get('nr', i)}: {s.get('text', '')}" for i, s in enumerate(saetze))


def _pruefe(antwort, gewuenscht: list[tuple[str, str, str]]) -> str | None:
    from ..texte import _allgemein
    if not isinstance(antwort, dict) or not isinstance(antwort.get("stile"), list):
        return 'Antwort braucht {"stile": [...]}.'
    gefunden = {(e.get("plattform"), e.get("stil")) for e in antwort["stile"] if isinstance(e, dict)}
    fehlend = [f"{p}/{s}" for p, _, s in gewuenscht if (p, s) not in gefunden]
    if fehlend:
        return "Es fehlen Einträge für: " + ", ".join(fehlend)
    for e in antwort["stile"]:
        if e.get("passt_nicht"):
            continue
        roh = json.dumps(e.get("felder", {}), ensure_ascii=False) + " " + str(e.get("text", ""))
        befund = _allgemein(roh)
        if befund:
            return f"{e.get('plattform')}/{e.get('stil')}: {befund}"
        if e.get("plattform") in ("instagram", "tiktok", "pinterest") and not e.get("text"):
            return f"{e.get('plattform')}/{e.get('stil')}: Beitragstext fehlt."
        if e.get("plattform") == "threads" and len(str(e.get("felder", {}).get("text", ""))) > 500:
            return f"threads/{e.get('stil')}: über 500 Zeichen."
    return None


def _rueckfall(gewuenscht, saetze: list[dict], rezept: dict) -> dict:
    """Ohne Modell: einfache Texte aus den Sätzen, damit die Kette durchläuft."""
    texte = [s.get("text", "") for s in saetze if s.get("text")] or [rezept.get("aussage", "Ein klarer Gedanke.")]
    marke = konfig("marke")
    tags = " ".join(marke.get("hashtags", ["#tipps", "#alltag"])[:3])
    cta = marke.get("cta_zeile", "")
    caption = f"{texte[0]}\n\nWie machst du das bei dir?\n\n" + (f"{cta}\n\n" if cta else "") + tags
    eintraege = []
    for plattform, _, stil in gewuenscht:
        felder = {"titel": rezept.get("titel", texte[0][:60]), "aussage": texte[0], "punkte": texte[:3],
                  "saetze": texte[:3], "frage": "Wie machst du das?", "text": texte[0][:480]}
        eintraege.append({"plattform": plattform, "stil": stil, "felder": felder,
                          "text": caption if plattform != "pinterest" else texte[0][:480],
                          "pin_titel": rezept.get("titel", texte[0])[:100]})
    return {"stile": eintraege}


def texte_fuer_take(take: str, gewuenscht: list[tuple[str, str, str]]) -> dict:
    """Ein Modellaufruf für alle gewählten Stile eines Takes."""
    saetze = lesen(pfad("arbeit", take, "saetze.json"), []) or []
    rezepte = [lesen(p, {}) for p in sorted(pfad("arbeit", take, "stuecke").glob("*/rezept.json"))]
    rezept = rezepte[0] if rezepte else {}
    marke = konfig("marke")
    liste = []
    for plattform, _, stil in gewuenscht:
        textfeld = TEXTFELD[plattform].replace("{cta}", f'die Zeile "{marke.get("cta_zeile", "")}"'
                                               if marke.get("cta_zeile") else "kein Aufruf")
        liste.append(f'- plattform "{plattform}", stil "{stil}": "felder": {FELDER[f"{plattform}/{stil}"]}'
                     + (f", {textfeld}" if textfeld else ""))
    auftrag = vorlage("bildtexte", stile="\n".join(liste), saetze=_nummeriert(saetze),
                      titel=rezept.get("titel", ""), aussage=rezept.get("aussage", ""),
                      hashtags=" ".join(marke.get("hashtags", [])))
    return frage(auftrag, zweck="bildtexte",
                 rueckfall=lambda: _rueckfall(gewuenscht, saetze, rezept),
                 pruefe=lambda a: _pruefe(a, gewuenscht))


def standbild(take: str, satz_nr: int | None):
    """Ein echtes Bild aus der Aufnahme, in der Mitte des genannten Satzes,
    gespiegelt wie das Reel, auf 1080x1350 beschnitten."""
    import subprocess
    import tempfile
    from PIL import Image
    saetze = lesen(pfad("arbeit", take, "saetze.json"), []) or []
    quelle = next(iter(sorted(pfad("arbeit", take).glob("quelle.*"))), None)
    if not quelle or not saetze:
        return None
    satz = next((s for s in saetze if s.get("nr") == satz_nr), saetze[min(1, len(saetze) - 1)])
    sekunde = (float(satz.get("s", 0)) + float(satz.get("e", 0))) / 2
    filter_kette = "scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350"
    if konfig("pipeline").get("schnitt", {}).get("entspiegeln"):
        filter_kette = "hflip," + filter_kette
    with tempfile.TemporaryDirectory() as tmp:
        ziel = f"{tmp}/bild.jpg"
        r = subprocess.run(["ffmpeg", "-y", "-ss", f"{sekunde:.2f}", "-i", str(quelle), "-frames:v", "1",
                            "-vf", filter_kette, ziel], capture_output=True)
        if r.returncode != 0:
            return None
        return Image.open(ziel).convert("RGB").copy()


def satz_nr(text: str) -> int | None:
    zahl = re.search(r"\d+", str(text))
    return int(zahl.group()) if zahl else None
