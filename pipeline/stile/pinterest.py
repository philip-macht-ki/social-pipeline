"""Acht eigenständige Pinterest-Bauweisen, alle 1000 mal 1500 Pixel.

Titelversprechen (Regel aus dem Vorbild): enthält der Titel eine Zahl, muss
sie genau der Zahl der tatsächlich gezeigten Punkte entsprechen. Jeder Stil
mit Punkten hat eine eigene Höchstzahl, weil sein Layout nicht mehr Platz hat
(`szene` zeigt höchstens 3 Karten, `spickzettel` höchstens 7). Befund
28.09.2026: die Prüfung verglich den Titel bisher gegen die volle Punkteliste
statt gegen das, was der Stil wirklich zeichnet, darum passte "7 klare
Schritte" auch dann, wenn `szene` nur 3 davon zeigte.
"""
from __future__ import annotations

from PIL import ImageDraw

from .gemeinsam import PAARE, PAARE_BADGE, TextPasstNicht, bild, text, titel_zahl, verlauf, wortmarke

# Höchstzahl gezeigter Punkte je Stil. toolraster und statistik fehlen absichtlich:
# toolraster zeichnet immer ein festes 3x3-Raster (mit "Werkzeug" aufgefüllt),
# statistik zeigt Balken aus eigenen Werten, keine Nummernliste. Für beide gilt
# das Titelversprechen "N Punkte" nicht.
HOECHSTZAHL = {"spickzettel": 7, "szene": 3, "notizbuch": 6, "editorial": 4, "typomix": 5, "tabelle": 6}


def _punkte(daten: dict, maximum: int = 9) -> list[str]:
    roh_punkte = daten.get("punkte") or daten.get("saetze") or [daten.get("aussage", "Ein guter Start.")]
    return [punkt.get("kopf", punkt.get("satz", "")) if isinstance(punkt, dict) else str(punkt) for punkt in roh_punkte][:maximum]


def _karte(im, koordinaten, farbe: str) -> None:
    ImageDraw.Draw(im).rounded_rectangle(koordinaten, 25, fill=farbe)


def pin(stil: str, daten: dict):
    """Baut einen Pinterest-Pin. Gibt (Bild, "") oder (None, Befund) zurück."""
    alle_punkte = _punkte(daten, 9)
    titel = daten.get("titel", "Ein klarer Impuls")
    hoechstzahl = HOECHSTZAHL.get(stil)
    punkte = alle_punkte[:hoechstzahl] if hoechstzahl else alle_punkte
    titel_anzahl = titel_zahl(titel)
    if hoechstzahl is not None and titel_anzahl and titel_anzahl != len(punkte):
        return None, f"Titel verspricht {titel_anzahl} Punkte, der Pin zeigt {len(punkte)}."
    im = bild(1000, 1500, "#FBF5EC")
    zeichner = ImageDraw.Draw(im)
    boxen: list = []

    try:
        if stil == "spickzettel":
            # Akzent-Orange als Fließtext auf Creme verfehlt 4,5:1 (Befund 28.09.2026:
            # 3,3:1), darum die dunklere, noch klar orange lesbare Variante.
            text(im, str(len(punkte)), "block", (35, 80, 260, 300), "#A63E0A", [250, 190], 1, boxen=boxen)
            text(im, titel, "block", (45, 350, 880, 190), "#1B1A2E", [78, 64, 52, 40], 3, boxen=boxen)
            for index, punkt in enumerate(punkte):
                y_position = 565 + index * 112
                _karte(im, (42, y_position, 958, y_position + 90), "#FFFFFF")
                # Badge-Farbe statt PAARE[i][0]: Weiß auf dem hellen PAARE-Ton reichte
                # nur für 3,6:1 (Befund 28.09.2026), PAARE_BADGE ist überall dunkler genug.
                zeichner.rounded_rectangle((58, y_position + 14, 122, y_position + 78), 15, fill=PAARE_BADGE[index % 6])
                text(im, str(index + 1), "block", (74, y_position + 26, 35, 35), "#FFFFFF", [30], 1, boxen=boxen, haupttext=False)
                text(im, punkt, "text", (145, y_position + 22, 760, 55), "#1B1A2E", [34, 30], 2, boxen=boxen)
            zeichner.rectangle((0, 1380, 1000, 1500), fill="#1B1A2E")
            text(im, daten.get("unter", "Merke dir diesen Gedanken."), "text", (50, 1415, 800, 45), "#FFFFFF", [25], 1, boxen=boxen, haupttext=False)
        elif stil == "szene":
            # Dunkel oben, hell unten: der Titel in Weiß braucht dunklen Grund
            # (Befund 28.09.2026: hell-oben ergab nur 2,2:1 Kontrast). Die
            # Punktkarte ist ohnehin eine deckende weiße Fläche, unabhängig vom Verlauf.
            im = verlauf(1000, 1500, "#5A463A", "#D6C1A5")
            zeichner = ImageDraw.Draw(im)
            text(im, titel, "block", (55, 90, 860, 330), "#FFFFFF", [100, 82, 64, 52], 4, boxen=boxen)
            _karte(im, (45, 1050, 955, 1400), "#FFFFFF")
            for index, punkt in enumerate(punkte):
                text(im, f"{index + 1}. {punkt}", "text", (85, 1090 + index * 92, 800, 70), "#1B1A2E", [34, 30], 2, boxen=boxen)
        elif stil == "notizbuch":
            im = verlauf(1000, 1500, "#E9DDC2", "#B69B73")
            zeichner = ImageDraw.Draw(im)
            zeichner.rounded_rectangle((90, 100, 900, 1360), 15, fill="#FFFDF7")
            text(im, titel, "hand", (140, 155, 680, 175), "#262130", [76, 64, 52], 3, boxen=boxen)
            for index, punkt in enumerate(punkte):
                # PAARE[i][0] direkt auf dem fast weißen Blatt reichte nicht (Befund
                # 28.09.2026: Orange nur 3,5:1), PAARE_BADGE ist die dunklere, lesbare Variante.
                text(im, f"{index + 1}  {punkt}", "hand", (145, 410 + index * 135, 700, 100), PAARE_BADGE[index % 6], [50, 42, 36], 2, boxen=boxen)
            zeichner.rectangle((650, 1240, 900, 1340), fill="#F9D85C")
            text(im, "Merken", "hand", (680, 1260, 180, 50), "#302B3A", [36], 1, boxen=boxen, haupttext=False)
        elif stil == "editorial":
            im = verlauf(1000, 1500, "#ECE7E1", "#CBB9AC")
            _karte(im, (160, 280, 840, 1220), "#FFFDF9")
            text(im, str(daten.get("zahl", len(punkte))), "serif", (310, 340, 380, 230), "#8C4A38", [210, 170], 1, True, boxen=boxen)
            text(im, titel, "serif", (220, 610, 560, 260), "#3B2F2A", [64, 52, 44, 36], 4, True, boxen=boxen)
            # Lesetext auf Pins braucht mindestens 30 px (Befund 28.09.2026: editorial
            # war mit 24 px praktisch unlesbar), deshalb liegt die kleinste Stufe bei 32.
            text(im, "\n".join(punkte), "text_normal", (220, 950, 560, 220), "#4D403A", [40, 36, 32], 5, True, boxen=boxen)
        elif stil == "typomix":
            im = bild(1000, 1500, "#FBE2E6")
            zeichner = ImageDraw.Draw(im)
            for y_position in range(30, 1470, 24):
                zeichner.line((25, y_position, 35, y_position), fill="#DBA0AA", width=3)
            for x_position in range(30, 970, 24):
                zeichner.line((x_position, 25, x_position, 35), fill="#DBA0AA", width=3)
            # Teal auf dem hellen Rosa lag bei 4,2:1 (Befund 28.09.2026), diese
            # dunklere Variante liegt sicher über 4,5:1.
            text(im, daten.get("notiz", "clevere"), "schreibschrift", (100, 100, 800, 130), "#066361", [78, 64, 52], 2, True, boxen=boxen)
            text(im, titel, "block", (70, 280, 860, 210), "#1B1A2E", [84, 68, 52], 3, True, boxen=boxen)
            for index, punkt in enumerate(punkte):
                y_position = 570 + index * 145
                _karte(im, (80, y_position, 920, y_position + 120), "#FFFFFF")
                zeichner.ellipse((100, y_position + 20, 180, y_position + 100), fill="#0B7A78")
                text(im, punkt, "text", (210, y_position + 32, 650, 55), "#1B1A2E", [34, 30], 2, boxen=boxen)
        elif stil == "tabelle":
            im = bild(1000, 1500, "#F5F2FF")
            text(im, titel, "block", (55, 80, 880, 220), "#27203A", [78, 64, 52], 3, boxen=boxen)
            text(im, "DEINE AUFGABE", "text", (65, 350, 350, 50), "#4A3E73", [24], 1, boxen=boxen, haupttext=False)
            text(im, "SO HILFT KI", "text", (570, 350, 350, 50), "#4A3E73", [24], 1, boxen=boxen, haupttext=False)
            for index, punkt in enumerate(punkte):
                y_position = 430 + index * 145
                _karte(im, (55, y_position, 430, y_position + 110), "#FFFFFF")
                _karte(im, (560, y_position, 945, y_position + 110), "#E6DEFF")
                text(im, punkt, "text", (80, y_position + 15, 320, 85), "#282332", [34, 30], 2, boxen=boxen)
                text(im, "klar strukturieren", "text_normal", (585, y_position + 18, 320, 82), "#392C68", [34, 30], 2, boxen=boxen)
                text(im, "→", "text", (465, y_position + 30, 70, 50), "#7C3AED", [34], 1, boxen=boxen, haupttext=False)
        elif stil == "toolraster":
            im = verlauf(1000, 1500, "#17213A", "#6D3A67")
            zeichner = ImageDraw.Draw(im)
            text(im, titel, "block", (50, 70, 880, 280), "#FFFFFF", [78, 64, 52], 4, boxen=boxen)
            for index, punkt in enumerate((alle_punkte + ["Werkzeug"] * 9)[:9]):
                spalte = index % 3
                zeile = index // 3
                x_position = 45 + spalte * 310
                y_position = 470 + zeile * 285
                _karte(im, (x_position, y_position, x_position + 280, y_position + 250), "#FFFFFF")
                zeichner.rectangle((x_position, y_position, x_position + 280, y_position + 12), fill=PAARE[index % 6][0])
                text(im, punkt or "Werkzeug", "text", (x_position + 22, y_position + 48, 235, 140), "#1B1A2E", [34, 30], 4, boxen=boxen)
        elif stil == "statistik":
            werte = daten.get("statistik") or [(punkt, index + 1) for index, punkt in enumerate(alle_punkte[:5])]
            if not daten.get("quelle"):
                return None, "statistik braucht eine Quelle"
            im = bild(1000, 1500, "#FFF6EC")
            zeichner = ImageDraw.Draw(im)
            maximum = max(float(wert[1] if isinstance(wert, (list, tuple)) else wert.get("wert", 1)) for wert in werte)
            # Bei Statistik ist der Höchstwert die Aussage des Pins, nicht die Anzahl der Balken.
            text(im, str(daten.get("zahl", round(maximum))), "block", (50, 70, 700, 240), "#B4460B", [210, 170], 1, boxen=boxen)
            text(im, titel, "block", (50, 340, 880, 160), "#1B1A2E", [62, 52, 44], 3, boxen=boxen)
            for index, eintrag in enumerate(werte[:5]):
                name, wert = (eintrag[0], eintrag[1]) if isinstance(eintrag, (list, tuple)) else (eintrag.get("name", ""), eintrag.get("wert", 0))
                balkenhoehe = int(460 * float(wert) / maximum)
                x_position = 80 + index * 175
                zeichner.rectangle((x_position, 1130 - balkenhoehe, x_position + 110, 1130), fill=PAARE[index % 6][0])
                text(im, str(wert), "text", (x_position, 1085 - balkenhoehe, 110, 35), "#1B1A2E", [28], 1, True, boxen=boxen, haupttext=False)
                text(im, str(name), "text_normal", (x_position, 1150, 120, 60), "#1B1A2E", [20], 2, True, boxen=boxen, haupttext=False)
            text(im, "Quelle: " + str(daten["quelle"]), "text_normal", (55, 1400, 880, 35), "#5B5A6E", [18], 1, boxen=boxen, haupttext=False)
        else:
            return None, "unbekannter Pinterest-Stil"
    except TextPasstNicht as fehler:
        return None, str(fehler)
    wortmarke(im, boxen=boxen)
    im.textboxen = boxen
    return im, ""
