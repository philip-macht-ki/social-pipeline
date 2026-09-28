"""Instagram-Bilder und Karussells."""
from __future__ import annotations

import re

from PIL import Image, ImageDraw

from ..kern import konfig
from .gemeinsam import PAARE, TextPasstNicht, bild, nummer, text, verlauf, wortmarke


def _saetze(daten: dict) -> list:
    return daten.get("saetze") or daten.get("punkte") or [daten.get("aussage", "Ein klarer Gedanke.")]


def bild_stil(stil: str, daten: dict):
    """Baut ein einzelnes Instagram-Bild. Gibt (Bild, "") oder (None, Befund)
    zurück. Ein Text, der nicht passt oder zu wenig Kontrast hat, stoppt den
    Stil sofort (TextPasstNicht), statt ein halbes Bild auszuliefern
    (Befund 28.09.2026: instagram-notiz kam leer raus, weil das früher niemand prüfte)."""
    boxen: list = []
    im = bild(1080, 1350, "#FBF5EC")
    zeichner = ImageDraw.Draw(im)
    akzent = daten.get("akzent", PAARE[0][0])
    aussage = daten.get("aussage") or _saetze(daten)[0]
    try:
        if stil == "zahl":
            zahl = re.search(r"\d+", str(daten.get("text", aussage)) + " " + str(daten.get("titel", "")))
            if not zahl:
                return None, "keine Zahl für Stil zahl"
            text(im, zahl.group(), "block", (55, 90, 970, 340), "#1B1A2E", [280, 220, 170], 1, boxen=boxen)
            text(im, aussage, "titel", (60, 480, 900, 470), "#1B1A2E", [88, 72, 60, 48, 36], 4, boxen=boxen)
        elif stil == "einwand":
            zeichner.rounded_rectangle((45, 80, 1035, 620), 30, fill="#261F35")
            zeichner.rounded_rectangle((45, 660, 1035, 1240), 30, fill="#1B1A2E")
            text(im, daten.get("einwand", "Das klingt nach mehr Arbeit."), "titel", (90, 150, 880, 380),
                 "#FFFFFF", [76, 64, 52, 40, 36], 4, boxen=boxen)
            text(im, aussage, "titel", (90, 740, 880, 390), "#FFFFFF", [76, 64, 52, 40, 36], 4, boxen=boxen)
        elif stil == "vorher_nachher":
            zeichner.rectangle((0, 0, 1080, 675), fill="#302B3A")
            zeichner.rectangle((0, 675, 1080, 1350), fill="#FBF5EC")
            text(im, "VORHER", "text", (60, 80, 400, 80), "#FFFFFF", [36], 1, boxen=boxen, haupttext=False)
            text(im, daten.get("vorher", _saetze(daten)[0]), "titel", (60, 190, 900, 380), "#FFFFFF", [76, 60, 48, 36], 4, boxen=boxen)
            text(im, "NACHHER", "text", (60, 760, 400, 80), "#8A4413", [36], 1, boxen=boxen, haupttext=False)
            text(im, daten.get("nachher", aussage), "titel", (60, 870, 900, 350), "#1B1A2E", [76, 60, 48, 36], 4, boxen=boxen)
        elif stil == "raster":
            kacheln = _saetze(daten)
            if len(set(kacheln)) < 9:
                return None, "raster braucht neun unterschiedliche Aussagen"
            for index, kacheltext in enumerate(kacheln[:9]):
                spalte = index % 3
                zeile = index // 3
                x_position = 45 + spalte * 335
                y_position = 180 + zeile * 345
                kachelfarbe = PAARE[index % 6][1]
                zeichner.rounded_rectangle((x_position, y_position, x_position + 290, y_position + 290), 24, fill=kachelfarbe)
                text(im, str(kacheltext), "text", (x_position + 20, y_position + 30, 250, 230), "#1B1A2E",
                     [36, 30, 26], 6, boxen=boxen)
            # Weiße Schrift auf dem Akzent-Orange verfehlte 4,5:1 (Kontrast 3,6:1),
            # deshalb trägt der Balken jetzt Dunkel, der Akzent bleibt als Linie sichtbar.
            zeichner.rectangle((0, 0, 1080, 130), fill="#1B1A2E")
            zeichner.rectangle((0, 130, 1080, 138), fill=akzent)
            text(im, daten.get("titel", "9 Ideen"), "block", (45, 25, 950, 90), "#FFFFFF", [60, 48, 36], 1, boxen=boxen)
        elif stil == "notiz":
            # Handschrift auf Papier: bewusst nur 3 kurze Zeilen statt ganzer Sätze,
            # sonst wickelt eine lange Aussage sich über die vierfache Zeilenzahl und
            # sprengt die Box lautlos (genau das führte am 28.09.2026 zum leeren Blatt).
            # Kurze "punkte" gehen vor langen "saetze": eine Notiz ist kein Fließtext.
            im = verlauf(1080, 1350, "#FFFDF5", "#EEE4D3")
            zeichner = ImageDraw.Draw(im)
            zeilen_quelle = (daten.get("punkte") or _saetze(daten))[:3]
            text(im, "\n".join(zeilen_quelle), "hand", (110, 260, 870, 760), "#302B3A",
                 [96, 84, 72, 60, 52, 44], 8, boxen=boxen)
            zeichner.line((110, 1080, 900, 1080), fill=akzent, width=7)
        elif stil == "zitat_standbild":
            # Die einzige Bildform mit echtem Foto: ein Standbild aus der Aufnahme,
            # unten abgedunkelt, darauf nur das Zitat und klein der Name. Ohne
            # Wortmarke und ohne Band (Vorbild BF09, Entscheidung vom 24.09.2026:
            # es soll nicht aussehen wie ein Thumbnail).
            foto = daten.get("standbild")
            if foto is not None:
                im = foto.convert("RGB").resize((1080, 1350))
                schatten = verlauf(1080, 1350, "#000000", "#000000").convert("L")
                maske = Image.linear_gradient("L").resize((1080, 1350)).point(lambda v: int(max(0, v - 90) * 1.35))
                im = Image.composite(schatten.convert("RGB"), im, maske)
            else:
                im = verlauf(1080, 1350, "#726C65", "#111111")
            text(im, aussage, "titel", (70, 760, 900, 440), "#FFFFFF", [82, 70, 60, 48, 36], 4, boxen=boxen)
            text(im, konfig("marke").get("name", daten.get("handle", "")), "text", (70, 1210, 600, 55), "#F2A15D",
                 [28], 1, boxen=boxen, haupttext=False)
            im.textboxen = boxen
            return im, ""
        else:
            return None, "unbekannter Instagram-Stil"
    except TextPasstNicht as fehler:
        return None, str(fehler)
    try:
        wortmarke(im, boxen=boxen)
    except TextPasstNicht as fehler:
        return None, str(fehler)
    im.textboxen = boxen
    return im, ""


def karussell(stil: str, daten: dict, anzahl: int = 6):
    """Baut die Folien eines Karussells. Eine Folie, die nicht passt, stoppt das
    ganze Karussell mit Befund, statt eine Lücke stillschweigend auszuliefern."""
    saetze = _saetze(daten)
    anzahl = max(5, min(8, anzahl))
    folien = []
    # Das helle Akzent-Orange fällt als Fließtext auf Creme unter 4,5:1 (Befund
    # 28.09.2026: 3,3:1). Für Text auf hellem Grund gilt darum diese dunklere,
    # noch klar orange lesbare Variante; die Rahmenfarben behalten das helle Orange.
    akzent_text = "#A63E0A"
    try:
        for index in range(anzahl):
            boxen: list = []
            im = bild(1080, 1350, "#F8FAFC" if stil == "woche_hell" else "#FBF5EC")
            if index == 0:
                text(im, daten.get("titel", "Ein klarer Gedanke"), "titel", (70, 580, 900, 400), "#1B1A2E",
                     [104, 88, 72, 60, 48], 4, True, boxen=boxen)
            elif index == anzahl - 1:
                text(im, daten.get("frage", "Was nimmst du daraus mit?"), "titel", (80, 500, 880, 300), akzent_text,
                     [92, 76, 60, 48], 3, True, boxen=boxen)
            else:
                # Mittige Textblöcke nutzen die Fläche, ohne den bewussten Weißraum aufzugeben.
                text(im, str(saetze[(index - 1) % len(saetze)]), "titel", (80, 510, 880, 440), "#111827",
                     [88, 72, 60, 48, 36], 4, boxen=boxen)
                if stil == "kette":
                    # Auch Zwischenfolien zeigen den Anschluss, damit sie nicht wie Einzelbilder wirken.
                    text(im, "NÄCHSTER SCHRITT", "text", (330, 875, 420, 45), akzent_text, [25], 1, True, boxen=boxen, haupttext=False)
                    text(im, "→", "block", (430, 945, 220, 160), akzent_text, [130, 110], 1, True, boxen=boxen, haupttext=False)
                if stil == "woche_hell":
                    text(im, "Quelle: " + str(daten.get("quelle", "")), "text_normal", (70, 1210, 850, 45),
                         "#3E3D4E", [22], 1, boxen=boxen, haupttext=False)
            wortmarke(im, boxen=boxen)
            nummer(im, index + 1, anzahl, boxen=boxen)
            im.textboxen = boxen
            folien.append(im)
    except TextPasstNicht as fehler:
        return [], str(fehler)
    return folien, ""
