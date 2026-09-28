"""Gemeinsame Pillow-Bausteine für Bildstile.

Zwei Fallen aus dem Vorbild-Befund vom 28.09.2026 sind hier für immer behoben:

1. `text()` warf früher nur ein (bool, befund)-Paar zurück, das viele Aufrufer
   nie prüften. Ein Text, der nicht passte, wurde dann einfach nicht
   gezeichnet, ohne dass irgendwer das merkte (instagram-notiz kam als leeres
   Blatt raus, eine Raster-Kachel blieb leer). Jetzt wirft `text()` bei einem
   Passungs- oder Kontrastproblem `TextPasstNicht`. Jeder Stil fängt das in
   seiner obersten Funktion ab und meldet es als Befund, statt ein halbes
   Bild auszuliefern.
2. Niemand maß den Kontrast von Textfarbe gegen Hintergrund. `tiktok-foto_zitat`
   ging mit weißer Schrift auf hellem Beige raus, unlesbar. `text()` misst
   jetzt die mittlere Hintergrundfarbe unter der Textbox und verlangt ein
   WCAG-Kontrastverhältnis von mindestens 4,5:1.

Jeder erfolgreich gezeichnete Textblock landet zusätzlich in `im.textboxen`
(Farbe, Größe, Kontrast, Lage). Die Tests lesen das aus, statt Pixel zu raten.
"""
from __future__ import annotations

import re

from PIL import Image, ImageDraw

from ..kern import konfig
from ..schrift import breite, zeichne_zeilen, groesste_passende, schrift

PAARE = [
    ("#E8590C", "#FFF0E7"),
    ("#2563EB", "#E8F0FF"),
    ("#0F9B8E", "#E1F7F3"),
    ("#7C3AED", "#F0E9FF"),
    ("#159947", "#E5F6EA"),
    ("#D6417A", "#FDE8F0"),
]

# Dieselben sechs Farbtöne, aber dunkler: für weißen Text auf einer satten Kachel
# oder einem Badge. PAARE[i][0] selbst reicht dafür oft nicht (Befund 28.09.2026:
# weiß auf #E8590C bringt nur 3,6:1). PAARE_BADGE liegt überall über 4,5:1.
PAARE_BADGE = ["#9C3A0C", "#1E4FC4", "#096B62", "#6A2FD1", "#0C6B31", "#A02D5C"]

MINDESTKONTRAST = 4.5


class TextPasstNicht(Exception):
    """Ein Text passt nicht in seine Box oder sein Kontrast reicht nicht.
    Die aufrufende Stilfunktion fängt das ab und meldet es als Befund,
    statt ein Bild mit einer leeren oder unlesbaren Stelle auszuliefern."""


def bild(breite_px: int, hoehe_px: int, farbe: str = "#FBF5EC"):
    return Image.new("RGB", (breite_px, hoehe_px), farbe)


def verlauf(breite_px: int, hoehe_px: int, oben: str, unten: str):
    im = bild(breite_px, hoehe_px, oben)
    zeichner = ImageDraw.Draw(im)
    obere_farbe = tuple(int(oben.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4))
    untere_farbe = tuple(int(unten.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4))
    for y_position in range(hoehe_px):
        fortschritt = y_position / max(1, hoehe_px - 1)
        farbe = tuple(round(obere_farbe[index] * (1 - fortschritt) + untere_farbe[index] * fortschritt) for index in range(3))
        zeichner.line((0, y_position, breite_px, y_position), fill=farbe)
    return im


def _hex_zu_rgb(hex_farbe: str) -> tuple[float, float, float]:
    hex_farbe = hex_farbe.lstrip("#")
    return tuple(int(hex_farbe[i:i + 2], 16) for i in (0, 2, 4))


def _luminanz(hex_farbe: str) -> float:
    """Relative Luminanz nach WCAG, Grundlage jedes Kontrastverhältnisses."""
    def kanal(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in _hex_zu_rgb(hex_farbe))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(vordergrund: str, hintergrund: str) -> float:
    """WCAG-Kontrastverhältnis zweier Hex-Farben (1.0 bis 21.0)."""
    hell = max(_luminanz(vordergrund), _luminanz(hintergrund)) + 0.05
    dunkel = min(_luminanz(vordergrund), _luminanz(hintergrund)) + 0.05
    return hell / dunkel


def mittlere_farbe(im, box: tuple[int, int, int, int]) -> str:
    """Mittlere Farbe unter einer Box, als Hex. Bei Fotos und Verläufen ist das
    die richtige Kontrastgrundlage, nicht eine einzelne Ecke."""
    x, y, breite_box, hoehe_box = box
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1 = min(im.width, x0 + max(1, int(breite_box)))
    y1 = min(im.height, y0 + max(1, int(hoehe_box)))
    if x1 <= x0 or y1 <= y0:
        return "#000000"
    ausschnitt = im.convert("RGB").crop((x0, y0, x1, y1)).resize((1, 1))
    r, g, b = ausschnitt.getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def _kontrastfarbe(hintergrund: str) -> str:
    """Wählt zwischen fast weiß und fast dunkel, je nachdem, was mehr Kontrast
    zu einem gegebenen Hintergrund bringt. Für Wortmarke und Foliennummer, die
    auf sehr unterschiedlichen Hintergründen stehen müssen."""
    hell, dunkel = "#FDFBF5", "#1B1A2E"
    return hell if kontrast(hell, hintergrund) >= kontrast(dunkel, hintergrund) else dunkel


def text(im, inhalt, rolle: str, box, farbe: str = "#1B1A2E", stufen=None, max_zeilen: int = 3,
          mitte: bool = False, boxen: list | None = None, haupttext: bool = True) -> int:
    """Zeichnet Text in eine Box. Gibt die Unterkante zurück.

    Wirft `TextPasstNicht`, wenn der Text bei keiner der `stufen` in die Box
    passt oder der Kontrast zur gemessenen Hintergrundfarbe unter 4,5:1 liegt.
    Übergib `boxen` (eine Liste), um jede erfolgreich gezeichnete Box mit
    Farbe, Größe, Kontrast und Lage dort zu protokollieren, für den
    Lesbarkeits- und Kontrasttest. `haupttext=False` markiert bewusste
    Feinschrift (Quellenangabe, Spaltenkopf, Achsenbeschriftung): die
    Mindestschriftgröße für Lesetext gilt nur für haupttext=True."""
    x_position, y_position, breite_px, hoehe_px = box
    stufen = stufen or [120, 104, 88, 72, 60, 48, 36]
    schriftgrad, zeilen = groesste_passende(str(inhalt), rolle, stufen, breite_px, max_zeilen)
    if schriftgrad is None:
        raise TextPasstNicht(f"Text passt nicht in {rolle}-Box bei ({x_position},{y_position}): {zeilen}")
    hintergrund = mittlere_farbe(im, box)
    verhaeltnis = kontrast(farbe, hintergrund)
    if verhaeltnis < MINDESTKONTRAST:
        raise TextPasstNicht(
            f"Kontrast {verhaeltnis:.1f}:1 in {rolle}-Box bei ({x_position},{y_position}) ist unter "
            f"{MINDESTKONTRAST}:1 (Text {farbe} gegen Hintergrund {hintergrund})."
        )
    unterkante = zeichne_zeilen(im, zeilen, rolle, schriftgrad, (x_position, y_position), farbe, 1.08,
                                 "mitte" if mitte else "links", breite_px)
    if unterkante > y_position + hoehe_px:
        raise TextPasstNicht(f"Text ist {unterkante - y_position - hoehe_px} px zu hoch für die Box bei ({x_position},{y_position}).")
    if boxen is not None:
        boxen.append({
            "rolle": rolle, "groesse": schriftgrad, "farbe": farbe, "hintergrund": hintergrund,
            "kontrast": round(verhaeltnis, 2), "x": x_position, "y": y_position,
            "w": breite_px, "h": unterkante - y_position, "zeilen": len(zeilen), "haupttext": haupttext,
        })
    return unterkante


def wortmarke(im, x: int = 48, y: int | None = None, farbe: str | None = None, boxen: list | None = None):
    """Kleine Wortmarke unten links. Die Farbe wird automatisch gegen den
    tatsächlichen Hintergrund gewählt (Befund 28.09.2026: ein festes Grau
    verschwand auf dunklen Pinterest- und TikTok-Hintergründen)."""
    wortmarke_text = konfig("marke").get("wortmarke", "").upper()
    if not wortmarke_text:
        return
    x_position = x
    y_position = y if y is not None else im.height - 55
    font = schrift("text", 22)
    geschaetzte_breite = sum(breite(b, font) + 4 for b in wortmarke_text)
    hintergrund = mittlere_farbe(im, (x_position, y_position, geschaetzte_breite, 26))
    farbe = farbe or _kontrastfarbe(hintergrund)
    zeichner = ImageDraw.Draw(im)
    buchstabenabstand = 4
    for buchstabe in wortmarke_text:
        zeichner.text((x_position, y_position), buchstabe, font=font, fill=farbe)
        x_position += breite(buchstabe, font) + buchstabenabstand
    if boxen is not None:
        boxen.append({"rolle": "wortmarke", "groesse": 22, "farbe": farbe, "hintergrund": hintergrund,
                       "kontrast": round(kontrast(farbe, hintergrund), 2), "x": x, "y": y_position,
                       "w": x_position - x, "h": 26, "zeilen": 1, "haupttext": False})


def nummer(im, nummer: int, gesamt: int, boxen: list | None = None):
    """Foliennummer unten rechts (Karussells), mit derselben automatischen
    Kontrastwahl wie die Wortmarke."""
    font = schrift("text", 22)
    textzeile = f"{nummer:02d} / {gesamt:02d}"
    x_position = im.width - 48 - breite(textzeile, font)
    y_position = im.height - 55
    box = (x_position, y_position, breite(textzeile, font), 26)
    hintergrund = mittlere_farbe(im, box)
    farbe = _kontrastfarbe(hintergrund)
    ImageDraw.Draw(im).text((x_position, y_position), textzeile, font=font, fill=farbe)
    if boxen is not None:
        boxen.append({"rolle": "nummer", "groesse": 22, "farbe": farbe, "hintergrund": hintergrund,
                       "kontrast": round(kontrast(farbe, hintergrund), 2), "x": x_position, "y": y_position,
                       "w": box[2], "h": box[3], "zeilen": 1, "haupttext": False})


def gesperrt(plattform: str, stil: str) -> bool:
    return stil in konfig("stile").get(plattform, {}).get("gesperrt", [])


def titel_zahl(titel: str):
    treffer = re.search(r"\b(\d+)\b", titel or "")
    return int(treffer.group(1)) if treffer else None
