"""Festes Titelband (1016x429, Grad 96, drei Zeilen) und Cover-Bild.

Das Titelband ist die einzige Texteinblendung mit fester Größe (im Unterschied
zum Tipp-Titel, der sich an den Text anpasst): dieselbe Auflage über wechselnde
Aufnahmen hinweg, siehe ARCHITEKTUR.md. Pixelmessung statt Zeichenzahl
(`pipeline/schrift.py`), nie geraten.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import schrift, urteil
from .kern import Ergebnis, konfig, lauf, log, pfad

BREITE, HOEHE = 1016, 429
GRAD_STANDARD = 96
GRAD_STUFEN = (96, 88, 80, 72)
ZEILENABSTAND = 1.10
MAX_ZEILEN = 3
RESERVE = 0.02  # je Seite, an allen vier Kanten


def nutzbare_breite() -> int:
    return int(BREITE * (1 - 2 * RESERVE))


def nutzbare_hoehe() -> int:
    return int(HOEHE * (1 - 2 * RESERVE))


def _farben() -> dict:
    return konfig("marke").get("farben", {
        "akzent": "#E8590C", "dunkel": "#1B1A2E", "hell": "#FBF5EC", "grau": "#5B5A6E",
    })


def passung(text: str) -> dict:
    """Sucht Grad und Zeilenumbruch, die den Text ins Band bringen.

    Reihenfolge (ARCHITEKTUR.md): fester Grad 96 zuerst. Passt es nicht, bittet
    `titel.md` das Modell zweimal um Kürzung (mit Pixelbefund im Auftrag).
    Hilft das nicht, sinkt der Grad in festen Stufen bis 72. Passt es auch
    dort nicht: `status: befund`, das Stück wird nicht gesperrt (das
    entscheidet der Aufrufer), aber der Befund steht im Ergebnis.
    """
    w = nutzbare_breite()
    aktuell = text
    for _ in range(2):
        ok, befund, zeilen = schrift.passt(aktuell, "titel", GRAD_STANDARD, w, MAX_ZEILEN, ZEILENABSTAND)
        if ok:
            return {"text": aktuell, "grad": GRAD_STANDARD, "zeilen": zeilen, "status": "ok", "meldung": ""}
        neu = aktuell
        try:
            antwort = urteil.frage(
                urteil.vorlage("titel", text=aktuell, befund=befund),
                zweck="titelband_kuerzen",
                rueckfall=lambda: {"text": aktuell},
            )
            if isinstance(antwort, dict) and antwort.get("text"):
                neu = str(antwort["text"]).strip()
        except urteil.KeinUrteil:
            pass
        if neu == aktuell:
            break
        aktuell = neu

    grad, rest = schrift.groesste_passende(aktuell, "titel", list(GRAD_STUFEN), w, MAX_ZEILEN)
    if grad:
        status = "ok" if grad == GRAD_STANDARD else "befund"
        meldung = "" if status == "ok" else f'Titelband auf Grad {grad} verkleinert ("{aktuell}").'
        return {"text": aktuell, "grad": grad, "zeilen": rest, "status": status, "meldung": meldung}
    return {"text": aktuell, "grad": GRAD_STUFEN[-1], "zeilen": [], "status": "befund",
            "meldung": f"Titelband passt auch bei Grad {GRAD_STUFEN[-1]} nicht: {rest}"}


def bild(zeilen: list[str], grad: int, akzent_letztes_wort: bool = True) -> Image.Image:
    """Zeichnet das Band: helle Fläche, dunkle Schrift, letztes Wort in Akzentfarbe."""
    farben = _farben()
    img = Image.new("RGBA", (BREITE, HOEHE), farben.get("hell", "#FBF5EC") + "FF"
                     if len(farben.get("hell", "#FBF5EC")) == 7 else farben.get("hell", "#FBF5EC"))
    d = ImageDraw.Draw(img)
    font = schrift.schrift("titel", grad)
    zeilenhoehe = int(grad * ZEILENABSTAND)
    block_hoehe = zeilenhoehe * len(zeilen)
    y = (HOEHE - block_hoehe) // 2
    innenrand = (BREITE - nutzbare_breite()) // 2
    for i, zeile in enumerate(zeilen):
        letzte_zeile = i == len(zeilen) - 1
        woerter = zeile.split(" ")
        if akzent_letztes_wort and letzte_zeile and len(woerter) > 1:
            vorlauf = " ".join(woerter[:-1]) + " "
            letztes = woerter[-1]
        else:
            vorlauf, letztes = zeile, ""
        gesamt_b = schrift.breite(zeile, font)
        x = innenrand + max(0, (nutzbare_breite() - gesamt_b) // 2)
        links = font.getbbox(vorlauf if letztes else zeile)[0]
        d.text((x - links, y), vorlauf, font=font, fill=farben.get("dunkel", "#1B1A2E"))
        if letztes:
            x2 = x + schrift.breite(vorlauf, font)
            d.text((x2, y), letztes, font=font, fill=farben.get("akzent", "#E8590C"))
        y += zeilenhoehe
    return img


def erstes_standbild(video: Path, sekunde: float, ziel: Path) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    lauf(["ffmpeg", "-y", "-ss", f"{max(0.0, sekunde):.3f}", "-i", str(video),
          "-frames:v", "1", "-q:v", "2", str(ziel)])


def cover(video: Path, sekunde: float, titel_text: str, wortmarke_text: str, ziel: Path) -> Ergebnis:
    """cover.jpg (1080x1920, JPEG, sRGB, <=8 MB): Standbild + Titelband + Wortmarke.

    Das Standbild kommt aus der Mitte des ersten Satzes nach dem Hook (Aufruf
    übergibt die passende Sekunde), nicht gespiegelt anders als das Reel selbst
    (dasselbe `roh.mp4`, also automatisch konsistent).
    """
    tmp = ziel.with_suffix(".roh.jpg")
    try:
        erstes_standbild(video, sekunde, tmp)
        basis = Image.open(tmp).convert("RGB")
    except (RuntimeError, OSError) as e:
        return Ergebnis("fehler", f"Cover-Standbild fehlgeschlagen: {e}")
    finally:
        tmp.unlink(missing_ok=True)

    if basis.size != (1080, 1920):
        basis = basis.resize((1080, 1920))
    canvas = basis.convert("RGBA")

    p = passung(titel_text)
    band = bild(p["zeilen"] or [titel_text], p["grad"])
    # unten im mittleren Drittel: Drittelgrenzen bei 1280 und 1920, Bandmitte auf 1600
    band_y = 1280 + (640 - HOEHE) // 2
    band_x = (1080 - BREITE) // 2
    canvas.alpha_composite(band, (band_x, band_y))

    marke_font = schrift.schrift("text", 22)
    d = ImageDraw.Draw(canvas)
    farben = _farben()
    text = wortmarke_text.upper()
    b = schrift.breite(text, marke_font)
    d.text((1080 - 70 - b, 1920 - 70), text, font=marke_font, fill=farben.get("grau", "#5B5A6E"))

    ziel.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(ziel, "JPEG", quality=92, icc_profile=None, subsampling=0)
    mb = ziel.stat().st_size / 1e6
    if mb > 8.0:
        canvas.convert("RGB").save(ziel, "JPEG", quality=78)
        mb = ziel.stat().st_size / 1e6
    meldung = p["meldung"]
    if mb > 8.0:
        return Ergebnis("befund", f"cover.jpg ist {mb:.1f} MB, über 8 MB Grenze.")
    log(f"ok: cover.jpg gebaut ({mb:.1f} MB, Titelband Grad {p['grad']}).")
    return Ergebnis("befund" if meldung else "ok", meldung, {"grad": p["grad"], "mb": round(mb, 2)})
