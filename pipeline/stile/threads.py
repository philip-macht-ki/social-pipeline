"""Threads-Textformen und die kleine Zitatkarte."""
from __future__ import annotations

from .gemeinsam import TextPasstNicht, bild, text, wortmarke


def textform(stil: str, satz: str) -> str:
    textzeile = str(satz).strip()
    if stil == "einwand":
        return f"Der Einwand: {textzeile}\nDie Antwort beginnt mit einem kleinen Test. #Alltag"
    if stil == "zahl":
        return f"{textzeile} Was sagt dir diese Zahl für deinen nächsten Schritt? #Alltag"
    if stil == "frage":
        return f"{textzeile} Was würdest du zuerst ausprobieren? #Alltag"
    if stil == "kette":
        return f"Beobachten. Ordnen. Ausprobieren. {textzeile} #Alltag"
    return f"{textzeile} #Alltag"


def zitatkarte(satz: str):
    """Baut die Bildkarte zu `bild_zeile`. Gibt (Bild, "") oder (None, Befund) zurück."""
    boxen: list = []
    im = bild(1080, 1350, "#F8FAFC")
    try:
        text(im, satz, "titel", (80, 410, 900, 430), "#111827", [86, 72, 60, 48, 36], 4, True, boxen=boxen)
    except TextPasstNicht as fehler:
        return None, str(fehler)
    wortmarke(im, boxen=boxen)
    im.textboxen = boxen
    return im, ""
