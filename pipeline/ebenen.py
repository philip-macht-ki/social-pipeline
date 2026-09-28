"""Text-Ebenen als Pillow-PNG-Zustände: Karaoke-Untertitel, Tipp-Titel,
Titelband-Spur, Stichwort-Kacheln, Wortmarke, Schlusskarte.

Das Homebrew-ffmpeg hier kann keinen Text einbrennen (kein drawtext, kein
libass/ass, kein subtitles-Filter). Jede Einblendung ist deshalb ein
transparentes PNG (1080x1920), das ffmpeg per `overlay` über das Video legt.

Statt jede Ebene als eigenen ffmpeg-Overlay zu verketten, werden alle aktiven
Ebenen vorher in Pillow zu EINEM Zustand je Zeitabschnitt zusammengelegt
(`zusammenfuehren`/`schreiben`): eine concat-Demuxer-Liste, ein `overlay`. Das
hält den Filtergraph klein und den Bau schnell (Zielwert: unter 2 Minuten für
60 s Video, siehe Auftrag).

Jede Spur-Funktion gibt eine Liste `[(start, ende, Bild_oder_None), …]` zurück,
die lückenlos das ganze Stück von 0 bis `dauer` abdeckt (`None` = nichts zu
zeigen). `schreiben()` fasst mehrere Spuren zusammen und schreibt die
PNG-Folge plus die ffmpeg-concat-Liste.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import schrift

BREITE, HOEHE = 1080, 1920
MIN_ZUSTAND = 0.02  # s, kürzere Zustände werden mit dem vorigen verschmolzen (Drift vermeiden)


# ---------------------------------------------------------------- Karaoke ---

def _zeilen_woerter(woerter: list[dict], max_zeichen: int, max_worte: int) -> list[list[dict]]:
    """Bricht Wörter in Zeilen, Zeichen- und Wortgrenze (nicht Pixel: die
    Karaoke-Zeile hat eine feste Zeichenbudget-Vorgabe im Auftrag, 4/20)."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    n = 0
    for w in woerter:
        laenge = len(w["w"])
        if cur and (n + 1 + laenge > max_zeichen or len(cur) >= max_worte):
            out.append(cur)
            cur, n = [], 0
        cur.append(w)
        n += (1 if n else 0) + laenge
    if cur:
        out.append(cur)
    return out


def _zeile_zustand(zeile: list[dict], aktiv: int, groesse: int, unten: int, farben: dict) -> Image.Image:
    font = schrift.schrift("text", groesse)
    rand = 70
    max_breite = BREITE - 2 * rand
    voller_text = " ".join(w["w"] for w in zeile)
    gesamt_b = schrift.breite(voller_text, font)
    x0 = rand + max(0, (max_breite - gesamt_b) // 2)
    y = HOEHE - unten - schrift.hoehe(font)

    schatten = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(schatten)
    x = x0
    for w in zeile:
        sd.text((x, y), w["w"], font=font, fill=(16, 15, 13, 220))
        x += schrift.breite(w["w"] + " ", font)
    schatten = schatten.filter(ImageFilter.GaussianBlur(7))

    vordergrund = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    d = ImageDraw.Draw(vordergrund)
    x = x0
    for i, w in enumerate(zeile):
        farbe = farben["an"] if i == aktiv else farben["aus"]
        d.text((x, y), w["w"], font=font, fill=farbe, stroke_width=9, stroke_fill="#100f0d")
        x += schrift.breite(w["w"] + " ", font)
    return Image.alpha_composite(schatten, vordergrund)


def karaoke_spur(woerter: list[dict], dauer: float, *, groesse: int = 70, unten: int = 300,
                  max_worte: int = 4, max_zeichen: int = 20, farben: dict | None = None
                 ) -> list[tuple[float, float, Image.Image | None]]:
    """Karaoke-Untertitel: ganze Zeile sichtbar, gesprochenes Wort hell.

    Ein Zustand je Wort, jeder endet exakt, wo der nächste beginnt (streng
    fortlaufend gebaut, sonst Drift über viele Wörter hinweg, siehe
    befund_schnitt.md 18.09.2026: eine frühere Fassung lief so 21 s aus dem Ton).
    """
    farben = farben or {"an": "#f4f0e6", "aus": "#8b8474"}
    zeilen = _zeilen_woerter(woerter, max_zeichen, max_worte)
    spur: list[tuple[float, float, Image.Image | None]] = []
    letzte_ende = 0.0
    for zeile in zeilen:
        start = max(letzte_ende, zeile[0]["s"])
        if start > letzte_ende:
            spur.append((letzte_ende, start, None))
        for i, w in enumerate(zeile):
            s = w["s"] if i > 0 else start
            e = zeile[i + 1]["s"] if i + 1 < len(zeile) else zeile[-1]["e"]
            if e <= s:
                continue
            spur.append((s, e, _zeile_zustand(zeile, i, groesse, unten, farben)))
        letzte_ende = max(letzte_ende, zeile[-1]["e"])
    if letzte_ende < dauer:
        spur.append((letzte_ende, dauer, None))
    return spur


# ------------------------------------------------------------- Tipp-Titel ---

def _titel_bild(text: str, groesse: int, oben: int, farbe: str, breite_rand: int = 70) -> Image.Image:
    font = schrift.schrift("titel", groesse)
    max_px = BREITE - 2 * breite_rand
    zeilen = schrift.umbrechen(text, font, max_px)
    canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    schrift.zeichne_zeilen(canvas, zeilen, "titel", groesse, (breite_rand, oben), farbe,
                           zeilenabstand=1.08, kontur=8, konturfarbe="#100f0d")
    return canvas


def titel_spur(text: str, dauer: float, *, oben: int = 270, groesse: int = 80,
                takt: float = 0.055, bis: float = 4.8, farbe: str = "#f4f0e6"
               ) -> list[tuple[float, float, Image.Image | None]]:
    """Schreibmaschinen-Tipptitel: Zeichen für Zeichen, danach stehen bis `bis`,
    nie über `oben` (Sicherheitsrahmen). Helle Schrift mit dunkler Kontur statt
    einer Hell/Dunkel-Entscheidung je Hintergrund: bleibt so auf jedem
    Rohmaterial lesbar, ohne den Videoinhalt dafür auswerten zu müssen
    (bewusste Vereinfachung gegenüber dem Vorbild, siehe Schlussbericht)."""
    text = text.strip()
    if not text:
        return [(0.0, dauer, None)]
    n = len(text)
    fertig_bei = min(bis, dauer, n * takt)
    spur: list[tuple[float, float, Image.Image | None]] = []
    voriger_t = 0.0
    zeitpunkte = sorted({round(min(fertig_bei, i * takt), 4) for i in range(1, n + 1)
                          if i * takt <= fertig_bei + 1e-9} | {fertig_bei})
    for t in zeitpunkte:
        if t <= voriger_t:
            continue
        anzahl = max(1, min(n, round(t / takt)))
        spur.append((voriger_t, t, _titel_bild(text[:anzahl], groesse, oben, farbe)))
        voriger_t = t
    halte_bis = min(bis, dauer)
    if halte_bis > voriger_t:
        spur.append((voriger_t, halte_bis, _titel_bild(text, groesse, oben, farbe)))
        voriger_t = halte_bis
    if voriger_t < dauer:
        spur.append((voriger_t, dauer, None))
    return spur


def titelband_spur(band: Image.Image, dauer: float, *, oben: int = 270, bis: float = 4.8
                   ) -> list[tuple[float, float, Image.Image | None]]:
    """Setzt das fertige Titelband (aus `titelband.py`) für die ersten `bis` Sekunden."""
    halte_bis = min(bis, dauer)
    canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    x = (BREITE - band.width) // 2
    canvas.alpha_composite(band.convert("RGBA"), (x, oben))
    spur: list[tuple[float, float, Image.Image | None]] = [(0.0, halte_bis, canvas)]
    if halte_bis < dauer:
        spur.append((halte_bis, dauer, None))
    return spur


# ----------------------------------------------------------------- Kachel ---

def _kachel_bild(text: str, skala: float, farben: dict) -> Image.Image:
    font = schrift.schrift("text", 44)
    pad_x, pad_y = 36, 22
    b = schrift.breite(text, font)
    h = schrift.hoehe(font)
    breite_kachel = max(10, int((b + 2 * pad_x) * skala))
    hoehe_kachel = max(10, int((h + 2 * pad_y) * skala))
    canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    x0 = (BREITE - breite_kachel) // 2
    y0 = int(HOEHE * 0.56)
    d = ImageDraw.Draw(canvas)
    dunkel = farben.get("dunkel", "#1B1A2E")
    d.rounded_rectangle([x0, y0, x0 + breite_kachel, y0 + hoehe_kachel],
                        radius=max(4, int(20 * skala)), fill=dunkel + "E6")
    if skala >= 0.95:
        tx = x0 + (breite_kachel - b) // 2
        ty = y0 + (hoehe_kachel - h) // 2
        d.text((tx, ty), text, font=font, fill=farben.get("hell", "#FBF5EC"))
    return canvas


def kacheln_spur(kacheln: list[dict], dauer: float, *, titel_bis: float = 0.0,
                  halte: float = 2.5, farben: dict | None = None
                 ) -> list[tuple[float, float, Image.Image | None]]:
    """Stichwort-Kacheln mit kurzem Pop, nacheinander, nie zwei gleichzeitig.

    `kacheln`: [{"text","start"}] mit Startzeit auf der NEUEN (geschnittenen)
    Zeitachse. Eine Kachel, die noch vor `titel_bis + 0,25 s` läge, wird
    verworfen statt sich mit dem Titel zu überlagern (Falle aus
    befund_schnitt.md, 22.09.2026: Titel und Kachel auf derselben Sicherheitszeile).
    """
    farben = farben or {}
    fruehester = (titel_bis + 0.25) if titel_bis else 0.0
    spur: list[tuple[float, float, Image.Image | None]] = []
    letzte_ende = 0.0
    for k in kacheln:
        start = max(float(k.get("start", 0.0)), fruehester, letzte_ende)
        if start >= dauer:
            continue
        text = str(k.get("text", "")).strip()
        if not text:
            continue
        pop_dauer = 0.12
        t = start
        for skala in (0.7, 1.0):
            ende = min(dauer, t + pop_dauer / 2)
            if ende <= t:
                continue
            spur.append((t, ende, _kachel_bild(text, skala, farben)))
            t = ende
        ende_halte = min(dauer, start + halte)
        if ende_halte > t:
            spur.append((t, ende_halte, _kachel_bild(text, 1.0, farben)))
        letzte_ende = max(letzte_ende, ende_halte)
    if not spur:
        return [(0.0, dauer, None)]
    if spur[0][0] > 0:
        spur.insert(0, (0.0, spur[0][0], None))
    if letzte_ende < dauer:
        spur.append((letzte_ende, dauer, None))
    return spur


# --------------------------------------------------------------- Wortmarke --

def wortmarke_spur(text: str, dauer: float, *, unten: int, rechts: int,
                    farbe: str = "#5B5A6E", groesse: int = 22, ut_groesse: int = 70
                   ) -> list[tuple[float, float, Image.Image | None]]:
    """Kleine Wortmarke unten rechts, außerhalb der Plattform-Leisten
    (oberhalb der sicherheitsrahmen-Grenze `unten`).

    Steht eine ganze Zeile über der Karaoke-Untertitelzeile, nicht daneben:
    eine breite Untertitelzeile reichte sonst bis an den rechten Rand und lief
    mit der Wortmarke zusammen (beim ersten echten Kontrolllauf beobachtet,
    28.09.2026: "gemeinsam notiert" klebte an "DEINE MARKE")."""
    font = schrift.schrift("text", groesse)
    txt = text.upper()
    b = schrift.breite(txt, font)
    canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    x = BREITE - rechts - b
    ut_hoehe = schrift.hoehe(schrift.schrift("text", ut_groesse))
    y = HOEHE - unten - ut_hoehe - schrift.hoehe(font) - 24
    d.text((x, y), txt, font=font, fill=farbe, stroke_width=3, stroke_fill="#100f0d")
    return [(0.0, dauer, canvas)]


# -------------------------------------------------------------- Schlusskarte

def schlusskarte_bild(frame: Image.Image, text: str, *, farbe: str = "#FBF5EC") -> Image.Image:
    """Letztes Bild abgedunkelt, Text der Schlusskarte darauf. Wird von
    `video.py` zu einem eingefrorenen Klip encodiert (Ton still)."""
    basis = frame.convert("RGBA")
    if basis.size != (BREITE, HOEHE):
        basis = basis.resize((BREITE, HOEHE))
    verdunkelt = Image.blend(basis, Image.new("RGBA", basis.size, (10, 9, 8, 255)), 0.6)
    font = schrift.schrift("titel", 64)
    max_px = BREITE - 200
    zeilen = schrift.umbrechen(text, font, max_px)
    d = ImageDraw.Draw(verdunkelt)
    zeilenhoehe = int(64 * 1.15)
    block = zeilenhoehe * len(zeilen)
    y = (HOEHE - block) // 2
    for zeile in zeilen:
        b = schrift.breite(zeile, font)
        x = (BREITE - b) // 2
        d.text((x, y), zeile, font=font, fill=farbe)
        y += zeilenhoehe
    return verdunkelt.convert("RGB")


# ----------------------------------------------------------- Zusammenlegen --

def zusammenfuehren(dauer: float, *spuren: list[tuple[float, float, Image.Image | None]]
                    ) -> list[tuple[float, float, list[Image.Image | None]]]:
    """Vereint mehrere lückenlose Spuren zu einer gemeinsamen Zeitachse
    (Vereinigung aller Schnittpunkte). Zustände unter MIN_ZUSTAND werden mit
    dem vorigen verschmolzen, damit kein Mikrozustand die Bildfolge aufbläht."""
    punkte = {0.0, round(dauer, 4)}
    for spur in spuren:
        for s, e, _ in spur:
            punkte.add(round(max(0.0, min(dauer, s)), 4))
            punkte.add(round(max(0.0, min(dauer, e)), 4))
    geordnet = sorted(punkte)
    intervalle: list[list[float]] = []
    for i in range(len(geordnet) - 1):
        s, e = geordnet[i], geordnet[i + 1]
        if e - s <= 0:
            continue
        if intervalle and e - s < MIN_ZUSTAND:
            intervalle[-1][1] = e
        else:
            intervalle.append([s, e])

    ergebnis = []
    for s, e in intervalle:
        mitte = (s + e) / 2
        bilder = []
        for spur in spuren:
            bild = None
            for ss, ee, img in spur:
                if ss - 1e-6 <= mitte < ee + 1e-6:
                    bild = img
                    break
            bilder.append(bild)
        ergebnis.append((s, e, bilder))
    return ergebnis


def schreiben(ordner: Path, dauer: float, *spuren: list[tuple[float, float, Image.Image | None]]) -> Path:
    """Komponiert die vereinten Zustände zu PNGs und schreibt die
    ffmpeg-concat-Liste (`liste.txt`). Gibt den Pfad der Liste zurück."""
    ordner.mkdir(parents=True, exist_ok=True)
    vereint = zusammenfuehren(dauer, *spuren)
    folge: list[tuple[Path, float]] = []
    for i, (s, e, bilder) in enumerate(vereint):
        canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
        for bild in bilder:
            if bild is not None:
                canvas.alpha_composite(bild)
        p = ordner / f"{i:04d}.png"
        canvas.save(p)
        folge.append((p, round(e - s, 4)))
    if not folge:
        canvas = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
        p = ordner / "0000.png"
        canvas.save(p)
        folge.append((p, round(dauer, 4)))
    liste = ordner / "liste.txt"
    with open(liste, "w", encoding="utf-8") as f:
        for p, d in folge:
            f.write(f"file '{p.resolve()}'\nduration {d:.4f}\n")
        f.write(f"file '{folge[-1][0].resolve()}'\n")
    gesamt = sum(d for _, d in folge)
    if abs(gesamt - dauer) > 0.1:
        raise RuntimeError(f"Ebenen-Spur {gesamt:.3f} s statt {dauer:.3f} s (Stück).")
    return liste
