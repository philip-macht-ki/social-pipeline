"""Einwort- und Schwarzbild-Spuren, vollständig als Pillow-Ebenen."""

from __future__ import annotations

import re

from PIL import Image, ImageDraw, ImageFilter

from . import schrift

BREITE, HOEHE = 1080, 1920
FUELLWOERTER = {
    "ich",
    "du",
    "er",
    "sie",
    "es",
    "wir",
    "ihr",
    "und",
    "oder",
    "aber",
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "einen",
    "ist",
    "sind",
    "war",
    "auch",
    "nur",
    "halt",
    "mal",
}


def saetze(woerter: list[dict]) -> list[list[dict]]:
    out, aktuell = [], []
    for wort in woerter:
        aktuell.append(wort)
        if re.search(r"[.!?]$", wort["w"]):
            out.append(aktuell)
            aktuell = []
    if aktuell:
        out.append(aktuell)
    return out


def _inhalt(wort: str) -> str:
    return re.sub(r"[^\wäöüÄÖÜß-]", "", wort).lower()


def betonung(satz: list[dict]) -> str:
    kandidaten = [_inhalt(w["w"]) for w in satz]
    kandidaten = [w for w in kandidaten if w not in FUELLWOERTER and len(w) > 2]
    return max(kandidaten, key=len, default="")


def _font_fuer(
    text: str, rolle: str, max_breite: int, start: int
) -> tuple[object, int]:
    for grad in range(start, 23, -2):
        font = schrift.schrift(rolle, grad)
        if schrift.breite(text, font) <= max_breite:
            return font, grad
    return schrift.schrift(rolle, 24), 24


def _y(gesicht: dict | None, zeit: float, font: object) -> int:
    normal = 1060
    if not gesicht:
        return normal
    oben = int(gesicht["y"] * HOEHE)
    unten = int((gesicht["y"] + gesicht["h"]) * HOEHE)
    h = schrift.hoehe(font)
    if normal < unten and normal + h > oben:
        unter = unten + 40
        return unter if unter + h <= 1460 else max(0, oben - h - 40)
    return normal


def _bild(
    text: str,
    *,
    akzent: bool,
    stil: str,
    skala: float,
    links: int,
    rechts: int,
    gesicht: dict | None,
    zeit: float,
    akzentfarbe: str,
) -> Image.Image:
    rolle = "titel" if akzent else "text"
    font, _ = _font_fuer(text, rolle, rechts - links, 104 if akzent else 82)
    b, h = schrift.breite(text, font), schrift.hoehe(font)
    b, h = int(b * skala), int(h * skala)
    font, _ = _font_fuer(
        text, rolle, max(20, int((rechts - links) / skala)), 104 if akzent else 82
    )
    y = _y(gesicht, zeit, font)
    x = links + max(0, (rechts - links - schrift.breite(text, font)) // 2)
    bild = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    if stil == "pille":
        d.rounded_rectangle(
            (
                x - 24,
                y - 14,
                x + schrift.breite(text, font) + 24,
                y + schrift.hoehe(font) + 14,
            ),
            radius=28,
            fill=(20, 18, 18, 220),
        )
    if stil == "klar":
        schatten = Image.new("RGBA", bild.size, (0, 0, 0, 0))
        ImageDraw.Draw(schatten).text((x, y), text, font=font, fill=(0, 0, 0, 220))
        bild.alpha_composite(schatten.filter(ImageFilter.GaussianBlur(8)), (5, 5))
    kontur = 7 if stil == "kontur" else 0
    d.text(
        (x, y),
        text,
        font=font,
        fill=akzentfarbe if akzent else "#FFFFFF",
        stroke_width=kontur,
        stroke_fill="#161313",
    )
    if skala != 1:
        box = bild.getbbox()
        if box:
            teil = bild.crop(box).resize((b, h), Image.Resampling.LANCZOS)
            bild = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
            bild.alpha_composite(teil, (max(links, min(rechts - teil.width, x)), y))
    return bild


def spur(
    woerter: list[dict],
    dauer: float,
    *,
    stil: str,
    links: int,
    rechts: int,
    akzentfarbe: str,
    gesichter: list[dict] | None = None,
    auslassen: list[dict] | None = None,
    schwarz: bool = False,
    zoom: bool = False,
) -> list[tuple[float, float, Image.Image | None]]:
    """Eine lückenlose Wortspur. Schwarzbild betrifft immer den zweiten Satz."""
    from .gesicht import bei

    auslassen = auslassen or []
    out: list[tuple[float, float, Image.Image | None]] = []
    letzte = 0.0
    for nr, satz in enumerate(saetze(woerter)):
        betont = betonung(satz)
        gruppen = [satz]
        if schwarz and nr % 2 == 1:
            gruppen = []
            aktuell = []
            for wort in satz:
                aktuell.append(wort)
                if len(aktuell) >= (1 if len(_inhalt(wort["w"])) > 8 else 3):
                    gruppen.append(aktuell)
                    aktuell = []
            if aktuell:
                gruppen.append(aktuell)
        for gruppe in gruppen:
            for wort in [gruppe[0]] if schwarz and nr % 2 == 1 else gruppe:
                start, ende = max(letzte, wort["s"]), min(dauer, wort["e"])
                if ende <= start:
                    continue
                if start > letzte:
                    out.append((letzte, start, None))
                text = wort["w"]
                verborgen = any(
                    a["wort"].lower() == _inhalt(text) and a["von"] <= start <= a["bis"]
                    for a in auslassen
                )
                if verborgen:
                    out.append((start, ende, None))
                elif schwarz and nr % 2 == 1:
                    bild = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 255))
                    text = " ".join(x["w"] for x in gruppe)
                    font, _ = _font_fuer(text.upper(), "block", rechts - links, 110)
                    b = schrift.breite(text.upper(), font)
                    ImageDraw.Draw(bild).text(
                        (links + (rechts - links - b) // 2, 930),
                        text.upper(),
                        font=font,
                        fill="white",
                    )
                    out.append((gruppe[0]["s"], gruppe[-1]["e"], bild))
                else:
                    ist_akzent = _inhalt(text) == betont
                    face = bei(gesichter, start) if gesichter else None
                    if zoom and ist_akzent and nr % 2 == 1:
                        teile = [
                            (start, min(ende, start + 0.55), 1.12),
                            (min(ende, start + 0.55), ende, 1.0),
                        ]
                    else:
                        teile = [
                            (start, min(ende, start + 2 / 30), 0.86),
                            (
                                min(ende, start + 2 / 30),
                                min(ende, start + 4 / 30),
                                1.06,
                            ),
                            (min(ende, start + 4 / 30), ende, 1.0),
                        ]
                    for von, bis, skala in teile:
                        if bis > von:
                            out.append(
                                (
                                    von,
                                    bis,
                                    _bild(
                                        text,
                                        akzent=ist_akzent,
                                        stil=stil,
                                        skala=skala,
                                        links=links,
                                        rechts=rechts,
                                        gesicht=face,
                                        zeit=von,
                                        akzentfarbe=akzentfarbe,
                                    ),
                                )
                            )
                letzte = gruppe[-1]["e"] if schwarz and nr % 2 == 1 else ende
    if letzte < dauer:
        out.append((letzte, dauer, None))
    return out or [(0.0, dauer, None)]
