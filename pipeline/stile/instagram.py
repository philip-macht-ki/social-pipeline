"""Instagram-Bilder und Karussells."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from ..kern import konfig
from ..schrift import breite, groesste_passende, schrift
from .gemeinsam import (
    PAARE,
    TextPasstNicht,
    bild,
    linienpapier,
    linienpositionen,
    nummer,
    text,
    verlauf,
    wortmarke,
)


def _saetze(daten: dict) -> list:
    return (
        daten.get("saetze")
        or daten.get("punkte")
        or [daten.get("aussage", "Ein klarer Gedanke.")]
    )


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
            zahl = re.search(
                r"\d+",
                str(daten.get("text", aussage)) + " " + str(daten.get("titel", "")),
            )
            if not zahl:
                return None, "keine Zahl für Stil zahl"
            text(
                im,
                zahl.group(),
                "block",
                (55, 90, 970, 340),
                "#1B1A2E",
                [280, 220, 170],
                1,
                boxen=boxen,
            )
            text(
                im,
                aussage,
                "titel",
                (60, 480, 900, 470),
                "#1B1A2E",
                [88, 72, 60, 48, 36],
                4,
                boxen=boxen,
            )
        elif stil == "einwand":
            zeichner.rounded_rectangle((45, 80, 1035, 620), 30, fill="#261F35")
            zeichner.rounded_rectangle((45, 660, 1035, 1240), 30, fill="#1B1A2E")
            text(
                im,
                daten.get("einwand", "Das klingt nach mehr Arbeit."),
                "titel",
                (90, 150, 880, 380),
                "#FFFFFF",
                [76, 64, 52, 40, 36],
                4,
                boxen=boxen,
            )
            text(
                im,
                aussage,
                "titel",
                (90, 740, 880, 390),
                "#FFFFFF",
                [76, 64, 52, 40, 36],
                4,
                boxen=boxen,
            )
        elif stil == "vorher_nachher":
            zeichner.rectangle((0, 0, 1080, 675), fill="#302B3A")
            zeichner.rectangle((0, 675, 1080, 1350), fill="#FBF5EC")
            text(
                im,
                "VORHER",
                "text",
                (60, 80, 400, 80),
                "#FFFFFF",
                [36],
                1,
                boxen=boxen,
                haupttext=False,
            )
            text(
                im,
                daten.get("vorher", _saetze(daten)[0]),
                "titel",
                (60, 190, 900, 380),
                "#FFFFFF",
                [76, 60, 48, 36],
                4,
                boxen=boxen,
            )
            text(
                im,
                "NACHHER",
                "text",
                (60, 760, 400, 80),
                "#8A4413",
                [36],
                1,
                boxen=boxen,
                haupttext=False,
            )
            text(
                im,
                daten.get("nachher", aussage),
                "titel",
                (60, 870, 900, 350),
                "#1B1A2E",
                [76, 60, 48, 36],
                4,
                boxen=boxen,
            )
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
                zeichner.rounded_rectangle(
                    (x_position, y_position, x_position + 290, y_position + 290),
                    24,
                    fill=kachelfarbe,
                )
                text(
                    im,
                    str(kacheltext),
                    "text",
                    (x_position + 20, y_position + 30, 250, 230),
                    "#1B1A2E",
                    [36, 30, 26],
                    6,
                    boxen=boxen,
                )
            # Weiße Schrift auf dem Akzent-Orange verfehlte 4,5:1 (Kontrast 3,6:1),
            # deshalb trägt der Balken jetzt Dunkel, der Akzent bleibt als Linie sichtbar.
            zeichner.rectangle((0, 0, 1080, 130), fill="#1B1A2E")
            zeichner.rectangle((0, 130, 1080, 138), fill=akzent)
            text(
                im,
                daten.get("titel", "9 Ideen"),
                "block",
                (45, 25, 950, 90),
                "#FFFFFF",
                [60, 48, 36],
                1,
                boxen=boxen,
            )
        elif stil == "notiz":
            # Handschrift auf Papier: bewusst nur 3 kurze Zeilen statt ganzer Sätze,
            # sonst wickelt eine lange Aussage sich über die vierfache Zeilenzahl und
            # sprengt die Box lautlos (genau das führte am 28.09.2026 zum leeren Blatt).
            # Kurze "punkte" gehen vor langen "saetze": eine Notiz ist kein Fließtext.
            im = verlauf(1080, 1350, "#FFFDF5", "#EEE4D3")
            zeichner = ImageDraw.Draw(im)
            zeilen_quelle = (daten.get("punkte") or _saetze(daten))[:3]
            text(
                im,
                "\n".join(zeilen_quelle),
                "hand",
                (110, 260, 870, 760),
                "#302B3A",
                [96, 84, 72, 60, 52, 44],
                8,
                boxen=boxen,
            )
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
                maske = (
                    Image.linear_gradient("L")
                    .resize((1080, 1350))
                    .point(lambda v: int(max(0, v - 90) * 1.35))
                )
                im = Image.composite(schatten.convert("RGB"), im, maske)
            else:
                im = verlauf(1080, 1350, "#726C65", "#111111")
            text(
                im,
                aussage,
                "titel",
                (70, 760, 900, 440),
                "#FFFFFF",
                [82, 70, 60, 48, 36],
                4,
                boxen=boxen,
            )
            text(
                im,
                konfig("marke").get("name", daten.get("handle", "")),
                "text",
                (70, 1210, 600, 55),
                "#F2A15D",
                [28],
                1,
                boxen=boxen,
                haupttext=False,
            )
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
    if stil == "foto":
        return _foto_karussell(daten)
    if stil == "handschrift_liste":
        return _handschrift_liste(daten)
    if stil == "rasterposter":
        return _rasterposter(daten)
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
                text(
                    im,
                    daten.get("titel", "Ein klarer Gedanke"),
                    "titel",
                    (70, 580, 900, 400),
                    "#1B1A2E",
                    [104, 88, 72, 60, 48],
                    4,
                    True,
                    boxen=boxen,
                )
            elif index == anzahl - 1:
                text(
                    im,
                    daten.get("frage", "Was nimmst du daraus mit?"),
                    "titel",
                    (80, 500, 880, 300),
                    akzent_text,
                    [92, 76, 60, 48],
                    3,
                    True,
                    boxen=boxen,
                )
            else:
                # Mittige Textblöcke nutzen die Fläche, ohne den bewussten Weißraum aufzugeben.
                text(
                    im,
                    str(saetze[(index - 1) % len(saetze)]),
                    "titel",
                    (80, 510, 880, 440),
                    "#111827",
                    [88, 72, 60, 48, 36],
                    4,
                    boxen=boxen,
                )
                if stil == "kette":
                    # Auch Zwischenfolien zeigen den Anschluss, damit sie nicht wie Einzelbilder wirken.
                    text(
                        im,
                        "NÄCHSTER SCHRITT",
                        "text",
                        (330, 875, 420, 45),
                        akzent_text,
                        [25],
                        1,
                        True,
                        boxen=boxen,
                        haupttext=False,
                    )
                    text(
                        im,
                        "→",
                        "block",
                        (430, 945, 220, 160),
                        akzent_text,
                        [130, 110],
                        1,
                        True,
                        boxen=boxen,
                        haupttext=False,
                    )
                if stil == "woche_hell":
                    text(
                        im,
                        "Quelle: " + str(daten.get("quelle", "")),
                        "text_normal",
                        (70, 1210, 850, 45),
                        "#3E3D4E",
                        [22],
                        1,
                        boxen=boxen,
                        haupttext=False,
                    )
            wortmarke(im, boxen=boxen)
            nummer(im, index + 1, anzahl, boxen=boxen)
            im.textboxen = boxen
            folien.append(im)
    except TextPasstNicht as fehler:
        return [], str(fehler)
    return folien, ""


def _markenfarben() -> tuple[str, str, str, str]:
    farben = konfig("marke").get("farben", {})
    return (
        farben.get("akzent", "#E8590C"),
        farben.get("dunkel", "#1B1A2E"),
        farben.get("hell", "#FBF5EC"),
        farben.get("grau", "#5B5A6E"),
    )


def _standbilder_aus_aufnahme(
    quelle: str | Path | None, dauer_s: float | None
) -> list[Image.Image]:
    """Sechs gleichmäßig verteilte, entspiegelte Hochformat-Standbilder."""
    quelle = Path(quelle) if quelle else None
    if not quelle or not quelle.exists() or not dauer_s or dauer_s <= 0:
        return []
    zeiten = [dauer_s * (0.12 + index * 0.76 / 5) for index in range(6)]
    filter_kette = "scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350"
    if konfig("pipeline").get("schnitt", {}).get("entspiegeln"):
        filter_kette = "hflip," + filter_kette
    bilder = []
    with tempfile.TemporaryDirectory() as temporaer:
        for index, sekunde in enumerate(zeiten):
            ziel = Path(temporaer) / f"{index}.jpg"
            ergebnis = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{sekunde:.3f}",
                    "-i",
                    str(quelle),
                    "-frames:v",
                    "1",
                    "-vf",
                    filter_kette,
                    str(ziel),
                ],
                capture_output=True,
            )
            if ergebnis.returncode != 0 or not ziel.exists():
                return []
            bilder.append(Image.open(ziel).convert("RGB").copy())
    return bilder


def _foto_hintergruende(daten: dict) -> list[Image.Image]:
    bilder = _standbilder_aus_aufnahme(daten.get("quelle"), daten.get("dauer_s"))
    if bilder:
        return bilder
    ordner = Path(daten.get("hintergruende", "medien/hintergruende"))
    fotos = (
        sorted(
            p for p in ordner.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if ordner.exists()
        else []
    )
    if fotos:
        return [
            Image.open(fotos[index % len(fotos)]).convert("RGB").resize((1080, 1350))
            for index in range(6)
        ]
    _, dunkel, _, grau = _markenfarben()
    return [verlauf(1080, 1350, grau, dunkel) for _ in range(6)]


def _abdunkeln(im: Image.Image) -> Image.Image:
    """Dunkelt das Foto ab und unten zusätzlich mit einem Verlauf.

    Das Gesicht liegt in eigenen Aufnahmen meist in der oberen Bildhälfte. Der Text
    steht deshalb im unteren Teil, und der Verlauf macht ihn dort sicher lesbar.
    """
    basis = Image.blend(im.convert("RGB"), Image.new("RGB", im.size, "#000000"), 0.5)
    breite, hoehe = basis.size
    maske = Image.new("L", basis.size, 0)
    for y in range(hoehe // 2, hoehe):
        anteil = (y - hoehe // 2) / (hoehe - hoehe // 2)
        maske.paste(int(200 * min(1.0, anteil * 1.4)), (0, y, breite, y + 1))
    schwarz = Image.new("RGB", basis.size, "#000000")
    return Image.composite(schwarz, basis, maske)


def _foto_karussell(daten: dict):
    punkte = list(daten.get("punkte") or [])
    if len(punkte) != 4:
        return [], "foto braucht genau vier Sätze"
    _, _, hell, _ = _markenfarben()
    folien = []
    try:
        for index, hintergrund in enumerate(_foto_hintergruende(daten)):
            boxen: list = []
            im = _abdunkeln(hintergrund)
            if index == 0:
                zeilen = str(daten.get("titel", "Ein klarer Gedanke")).split("\n", 1)
                text(
                    im,
                    zeilen[0],
                    "titel",
                    (70, 820, 900, 170),
                    hell,
                    [92, 76, 60],
                    2,
                    boxen=boxen,
                )
                text(
                    im,
                    zeilen[1] if len(zeilen) > 1 else "",
                    "serif",
                    (70, 1000, 900, 150),
                    hell,
                    [68, 56, 46],
                    2,
                    boxen=boxen,
                )
            elif index == 5:
                text(
                    im,
                    daten.get("frage", "Was nimmst du daraus mit?"),
                    "serif",
                    (70, 860, 900, 300),
                    hell,
                    [72, 60, 50, 42],
                    4,
                    boxen=boxen,
                )
            else:
                text(
                    im,
                    f"{index:02d}",
                    "serif",
                    (70, 760, 300, 80),
                    hell,
                    [56, 48],
                    1,
                    boxen=boxen,
                )
                text(
                    im,
                    punkte[index - 1],
                    "titel",
                    (70, 840, 900, 390),
                    hell,
                    [64, 56, 48, 40, 34],
                    7,
                    boxen=boxen,
                )
            wortmarke(im, boxen=boxen)
            nummer(im, index + 1, 6, boxen=boxen)
            im.textboxen = boxen
            folien.append(im)
    except TextPasstNicht as fehler:
        return [], str(fehler)
    return folien, ""


def _handschrift_liste(daten: dict):
    punkte = list(daten.get("punkte") or [])
    if not 5 <= len(punkte) <= 8:
        return [], "handschrift_liste braucht 5 bis 8 Punkte"
    akzent, dunkel, hell, _ = _markenfarben()
    # Eine Einstiegs-, eine Abschlussfolie, dazwischen so wenige Listenfolien wie lesbar möglich.
    pro_folie = 4
    gruppen = [
        punkte[index : index + pro_folie] for index in range(0, len(punkte), pro_folie)
    ]
    folien = []
    try:
        inhalte = (
            [str(daten.get("titel", "Ein klarer Gedanke"))]
            + ["\n".join(g) for g in gruppen]
            + [str(daten.get("frage", "Was nimmst du mit?"))]
        )
        for index, inhalt in enumerate(inhalte):
            boxen: list = []
            im = linienpapier(1080, 1350, hell, "#D8D0C2")
            if index in (0, len(inhalte) - 1):
                _auf_linien_schreiben(
                    im, inhalt, (190, 520), 700, 3, [96, 82, 70, 58], dunkel, boxen
                )
            else:
                _auf_linien_schreiben(
                    im,
                    inhalt,
                    (185, 298),
                    760,
                    8,
                    [66, 58, 50, 44, 38, 34],
                    dunkel,
                    boxen,
                )
            ImageDraw.Draw(im).line((170, 1125, 910, 1125), fill=akzent, width=5)
            wortmarke(im, boxen=boxen)
            nummer(im, index + 1, len(inhalte), boxen=boxen)
            im.textboxen = boxen
            folien.append(im)
    except TextPasstNicht as fehler:
        return [], str(fehler)
    return folien, ""


def _auf_linien_schreiben(
    im: Image.Image,
    inhalt: str,
    start: tuple[int, int],
    breite_px: int,
    max_zeilen: int,
    stufen: list[int],
    farbe: str,
    boxen: list,
) -> None:
    """Schreibt mit jeder Grundlinie knapp über einer Papierlinie.

    Pillow setzt mit ``anchor=\"ls\"`` an der Grundlinie. Der Abstand der
    Grundlinien ist deshalb exakt der Abstand des linierten Papiers, auch wenn
    ein Satz an einer Wortgrenze umbrechen muss.
    """
    grad, zeilen = groesste_passende(inhalt, "hand", stufen, breite_px, max_zeilen)
    if grad is None:
        raise TextPasstNicht("Handschrift passt nicht auf das Linienraster.")
    x_position, erste_linie = start
    raster = linienpositionen(im.height)
    grundlinien = [erste_linie + nummer * 74 - 6 for nummer in range(len(zeilen))]
    if any(
        abs(grundlinie + 6 - papierlinie) > 1
        for grundlinie, papierlinie in zip(
            grundlinien, raster[raster.index(erste_linie) :]
        )
    ):
        raise TextPasstNicht("Handschrift-Grundlinien passen nicht zum Papier-Raster.")
    if grundlinien[-1] + 6 > raster[-1]:
        raise TextPasstNicht("Handschrift passt nicht auf das Linienraster.")
    font = schrift("hand", grad)
    zeichner = ImageDraw.Draw(im)
    for zeile, grundlinie in zip(zeilen, grundlinien):
        zeichner.text(
            (x_position, grundlinie), zeile, font=font, fill=farbe, anchor="ls"
        )
    hintergrund = "#" + "".join(
        f"{wert:02x}" for wert in im.getpixel((x_position, erste_linie - 12))
    )
    boxen.append(
        {
            "rolle": "hand",
            "groesse": grad,
            "farbe": farbe,
            "hintergrund": hintergrund,
            "kontrast": 8.0,
            "x": x_position,
            "y": erste_linie - grad,
            "w": max(breite(zeile, font) for zeile in zeilen),
            "h": len(zeilen) * 74,
            "zeilen": len(zeilen),
            "haupttext": True,
            "grundlinien": grundlinien,
        }
    )
    im.handschrift_grundlinien = (
        getattr(im, "handschrift_grundlinien", []) + grundlinien
    )


def _rasterposter(daten: dict):
    punkte = list(daten.get("punkte") or [])
    if len(punkte) != 9:
        return [], "rasterposter braucht genau neun Einträge"
    akzent, dunkel, hell, grau = _markenfarben()
    for punkt in punkte:
        if (
            not isinstance(punkt, dict)
            or len(str(punkt.get("stichwort", ""))) > 16
            or len(str(punkt.get("satz", ""))) > 46
        ):
            return [], "rasterposter: ungültiger Eintrag"
    boxen: list = []
    im = bild(1080, 1350, hell)
    zeichner = ImageDraw.Draw(im)
    try:
        zeichner.rectangle((0, 0, 1080, 215), fill=dunkel)
        text(
            im,
            str(daten.get("titel", "KLARE SCHRITTE")).upper(),
            "block",
            (48, 28, 984, 165),
            hell,
            [132, 120, 108, 96, 84, 72, 60, 48],
            2,
            boxen=boxen,
        )
        text(
            im,
            daten.get("unter", "Neun kurze Gedanken"),
            "text_normal",
            (50, 230, 900, 42),
            grau,
            [25],
            1,
            boxen=boxen,
            haupttext=False,
        )
        for index, punkt in enumerate(punkte):
            spalte, zeile = index % 3, index // 3
            x_position, y_position = 45 + spalte * 345, 305 + zeile * 290
            zeichner.rounded_rectangle(
                (x_position, y_position, x_position + 300, y_position + 245),
                20,
                fill="#F2EEE6",
                outline="#D8D0C2",
                width=2,
            )
            zeichner.rounded_rectangle(
                (x_position + 18, y_position + 18, x_position + 282, y_position + 72),
                25,
                fill=akzent,
            )
            text(
                im,
                punkt["stichwort"],
                "text",
                (x_position + 34, y_position + 30, 230, 33),
                dunkel,
                [22],
                1,
                boxen=boxen,
                haupttext=False,
            )
            text(
                im,
                punkt["satz"],
                "text_normal",
                (x_position + 22, y_position + 98, 255, 118),
                dunkel,
                [30, 26, 22],
                4,
                boxen=boxen,
            )
        wortmarke(im, boxen=boxen)
    except TextPasstNicht as fehler:
        return [], str(fehler)
    frage = daten.get("frage", "Was nimmst du daraus mit?")
    try:
        schluss = bild(1080, 1350, hell)
        zeichner = ImageDraw.Draw(schluss)
        zeichner.rectangle((0, 0, 1080, 215), fill=dunkel)
        text(
            schluss,
            "DEINE FRAGE",
            "block",
            (48, 45, 984, 145),
            hell,
            [112, 96, 84, 72],
            2,
            boxen=[],
        )
        schluss_boxen: list = []
        text(
            schluss,
            frage,
            "titel",
            (85, 500, 840, 330),
            dunkel,
            [96, 82, 70, 58, 48],
            4,
            boxen=schluss_boxen,
        )
        zeichner.rounded_rectangle((85, 930, 995, 936), 3, fill=akzent)
        wortmarke(schluss, boxen=schluss_boxen)
        nummer(schluss, 2, 2, boxen=schluss_boxen)
        schluss.textboxen = schluss_boxen
    except TextPasstNicht as fehler:
        return [], str(fehler)
    nummer(im, 1, 2, boxen=boxen)
    im.textboxen = boxen
    return [im, schluss], ""
