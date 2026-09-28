"""TikTok-Fotobeiträge mit Sicherheitsrand.

Befund 28.09.2026: `foto_zitat` ging mit weißer Schrift auf hellem Beige raus
(unlesbar), `foto_schritte` mit viel zu kleinem Lesetext und einer Wortmarke,
die mitten in die Textbox ragte. TikTok-Fotobeiträge sind 1080x1920 und werden
oft aus der Ferne oder klein in der Vorschau gelesen, deshalb gilt hier ein
höherer Mindest-Lesetext als bei den anderen Stilen: 56 px.
"""
from __future__ import annotations

from .gemeinsam import TextPasstNicht, text, verlauf, wortmarke

# TikTok blendet oben Profil/Ton-Symbole und unten Bildunterschrift plus Buttons
# ein. Kein Text darf dort liegen, sonst verschwindet er unter der App-Oberfläche.
OBERER_SICHERHEITSRAND = 270
UNTERER_SICHERHEITSRAND = 520
LESETEXT_MINDESTGROESSE = 56


def foto_stil(stil: str, daten: dict):
    """Baut einen TikTok-Fotobeitrag. Gibt (Bild, "") oder (None, Befund) zurück."""
    boxen: list = []
    unterer_rand_y = 1920 - UNTERER_SICHERHEITSRAND
    try:
        if stil == "foto_zitat":
            # Dunkler Verlauf statt hellem Beige: weiße Schrift braucht einen
            # dunklen Untergrund, um die 4,5:1-Kontrastgrenze zu erreichen.
            im = verlauf(1080, 1920, "#2B2438", "#100C16")
            text(im, daten.get("aussage", "Ein klarer Gedanke."), "titel", (70, 820, 900, unterer_rand_y - 100 - 820),
                 "#FFFFFF", [92, 76, 64, 56], 5, boxen=boxen)
            wortmarke(im, y=unterer_rand_y - 60, boxen=boxen)
            im.textboxen = boxen
            return im, ""

        im = verlauf(1080, 1920, "#FBF5EC", "#E4D6C5")
        titel_unten = text(im, daten.get("titel", "Schritt für Schritt"), "titel",
                            (70, OBERER_SICHERHEITSRAND + 60, 850, 300), "#1B1A2E", [88, 72, 60, 48], 3, boxen=boxen)
        # Der Lesetext endet mit Abstand oberhalb der Wortmarke, die wiederum mit
        # Abstand oberhalb des unteren Sicherheitsrands sitzt. Vorher lagen beide
        # Boxen übereinander (Befund: Wortmarke mitten im Bild).
        wortmarke_y = unterer_rand_y - 90
        text_hoehe = wortmarke_y - 40 - titel_unten
        # Nur drei Sätze statt vier: bei 56 px Mindestgröße wickelt ein langer Satz
        # leicht in zwei Zeilen, vier Sätze sprengten damit die erlaubten Zeilen.
        text(im, "\n".join(daten.get("saetze", [])[:3]), "text", (90, titel_unten + 40, 850, text_hoehe),
             "#1B1A2E", [64, 56], 8, boxen=boxen)
        wortmarke(im, y=wortmarke_y, boxen=boxen)
        im.textboxen = boxen
        return im, ""
    except TextPasstNicht as fehler:
        return None, str(fehler)
