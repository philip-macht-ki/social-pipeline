"""Schrift laden, messen, umbrechen. Pixel statt Zeichen.

Ob ein Text passt, entscheidet nie die Zeichenzahl ("W" ist breiter als "i"),
sondern die gerenderte Breite. Alles, was Text ins Bild setzt, nutzt diese
Funktionen, damit Messung und Darstellung dieselbe Schrift sehen.
"""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .kern import konfig, pfad


@lru_cache(maxsize=256)
def schrift(rolle_oder_datei: str, groesse: int) -> ImageFont.FreeTypeFont:
    """rolle aus konfig/marke.toml [schriften] (titel, text, block, hand …) oder Dateiname.

    Variable Schriften bekommen ihr Gewicht hinter einem @: "InstrumentSans-Variabel.ttf@700".
    Ohne @ bleibt die Voreinstellung der Datei, bei variablen Schriften meist 400."""
    rollen = konfig("marke").get("schriften", {})
    angabe = rollen.get(rolle_oder_datei, rolle_oder_datei)
    datei, _, gewicht = angabe.partition("@")
    font = ImageFont.truetype(str(pfad("schriften", datei)), groesse)
    if gewicht:
        try:
            achsen = font.get_variation_axes()
        except OSError:
            achsen = []
        if achsen:
            werte = []
            for a in achsen:
                name = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
                if name == "Weight":
                    werte.append(max(a["minimum"], min(a["maximum"], int(gewicht))))
                elif name == "Optical Size":
                    werte.append(max(a["minimum"], min(a["maximum"], groesse)))
                else:
                    werte.append(a["default"])
            font.set_variation_by_axes(werte)
    return font


def breite(text: str, font: ImageFont.FreeTypeFont) -> int:
    if not text:
        return 0
    links, _, rechts, _ = font.getbbox(text)
    return rechts - links


def hoehe(font: ImageFont.FreeTypeFont) -> int:
    """Zeilenhöhe aus Ober- und Unterlänge, damit Umlaute Platz haben."""
    auf, ab = font.getmetrics()
    return auf + ab


def umbrechen(text: str, font: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    """Bricht an Wortgrenzen um. "\\n" im Text erzwingt eine neue Zeile.
    Ein einzelnes Wort, das allein zu breit ist, bleibt als eigene Zeile stehen;
    `passt()` meldet es dann."""
    zeilen: list[str] = []
    for absatz in text.split("\n"):
        aktuell = ""
        for wort in absatz.split():
            probe = f"{aktuell} {wort}".strip()
            if breite(probe, font) <= max_px or not aktuell:
                aktuell = probe
            else:
                zeilen.append(aktuell)
                aktuell = wort
        zeilen.append(aktuell)
    return zeilen


def passt(text: str, rolle: str, groesse: int, max_px: int, max_zeilen: int,
          zeilenabstand: float = 1.1) -> tuple[bool, str, list[str]]:
    """(passt, befund, zeilen). Der Befund nennt Pixel, damit ein Modell kürzen kann:
    "Zeile 2 ist 113 px zu breit (Platz 590 px)" oder "4 Zeilen statt höchstens 3"."""
    font = schrift(rolle, groesse)
    zeilen = umbrechen(text, font, max_px)
    for i, z in enumerate(zeilen, 1):
        b = breite(z, font)
        if b > max_px:
            return False, f"Zeile {i} ist {b - max_px} px zu breit (Platz {max_px} px).", zeilen
    if len(zeilen) > max_zeilen:
        return False, f"{len(zeilen)} Zeilen statt höchstens {max_zeilen} bei {max_px} px Breite.", zeilen
    return True, "", zeilen


def groesste_passende(text: str, rolle: str, stufen: list[int], max_px: int, max_zeilen: int):
    """Probiert die Schriftgrade von groß nach klein. (grad, zeilen) oder (None, befund)."""
    befund = ""
    for grad in sorted(stufen, reverse=True):
        ok, befund, zeilen = passt(text, rolle, grad, max_px, max_zeilen)
        if ok:
            return grad, zeilen
    return None, befund


def zeichne_zeilen(bild: Image.Image, zeilen: list[str], rolle: str, groesse: int,
                   xy: tuple[int, int], farbe: str, zeilenabstand: float = 1.1,
                   ausrichtung: str = "links", breite_px: int | None = None,
                   kontur: int = 0, konturfarbe: str = "#000000") -> int:
    """Setzt Zeilen ab xy (oben links des Blocks). Gibt die Unterkante zurück."""
    font = schrift(rolle, groesse)
    d = ImageDraw.Draw(bild)
    x0, y = xy
    schritt = int(groesse * zeilenabstand)
    for z in zeilen:
        b = breite(z, font)
        if ausrichtung == "mitte" and breite_px:
            x = x0 + (breite_px - b) // 2
        elif ausrichtung == "rechts" and breite_px:
            x = x0 + breite_px - b
        else:
            x = x0
        links = font.getbbox(z)[0]
        d.text((x - links, y), z, font=font, fill=farbe,
               stroke_width=kontur, stroke_fill=konturfarbe)
        y += schritt
    return y
