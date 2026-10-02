"""Regelbasierte, mit Pillow gezeichnete Karten für Einwort-Fassungen."""

from __future__ import annotations

import re
import subprocess
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image, ImageDraw, ImageFilter

from . import schrift
from .kern import konfig, pfad

BREITE, HOEHE = 1080, 1920
VERNEINUNG = {"nicht", "kein", "keine", "nie"}


def _wort(w: str) -> str:
    return re.sub(r"[^\wäöüÄÖÜß]", "", w).lower()


def _fenster(rezept: dict) -> tuple[float, float] | None:
    wert = rezept.get("ki_einblendung") or {}
    return (
        (float(wert["von"]), float(wert["bis"]))
        if isinstance(wert, dict) and {"von", "bis"} <= set(wert)
        else None
    )


def _frei(
    karten: list[dict], start: float, ende: float, fenster: tuple[float, float] | None
) -> bool:
    return not (
        (fenster and start < fenster[1] and ende > fenster[0])
        or any(start < k["bis"] and ende > k["von"] for k in karten)
    )


def logo_holen(domain: str, ziel: Path, *, get=requests.get) -> bool:
    """Holt ein Favicon einmalig. Eine leere Cache-Datei bedeutet Fehlversuch."""
    if ziel.exists():
        return ziel.stat().st_size > 0
    ziel.parent.mkdir(parents=True, exist_ok=True)
    kandidaten = []
    try:
        antwort = get(f"https://{domain}", timeout=8)
        kandidaten.extend(
            urljoin(antwort.url, h)
            for h in re.findall(
                r'<link[^>]+rel=["\'][^"\']*(?:icon|apple-touch-icon)[^"\']*["\'][^>]+href=["\']([^"\']+)',
                antwort.text,
                re.I,
            )
        )
    except requests.RequestException:
        pass
    kandidaten += [
        f"https://{domain}/apple-touch-icon.png",
        f"https://www.google.com/s2/favicons?domain={domain}&sz=256",
    ]
    for url in kandidaten:
        if url.lower().split("?")[0].endswith(".svg"):
            continue
        try:
            bild = Image.open(BytesIO(get(url, timeout=8).content)).convert("RGBA")
            seite = min(bild.size)
            if seite < 96:
                continue
            x, y = (bild.width - seite) // 2, (bild.height - seite) // 2
            bild.crop((x, y, x + seite, y + seite)).resize(
                (256, 256), Image.Resampling.LANCZOS
            ).save(ziel)
            return True
        except (requests.RequestException, OSError):
            continue
    ziel.touch()
    return False


def finden(
    woerter: list[dict], rezept: dict, *, logos: Path | None = None
) -> list[dict]:
    """Setzt Karten regelbasiert und lässt KI-Einblendungsfenster frei."""
    cfg, fenster, karten = konfig("bausteine"), _fenster(rezept), []
    logo_ordner, sauber = (
        logos or pfad("medien", "logos"),
        [_wort(w["w"]) for w in woerter],
    )
    sticker_cfg = cfg.get("sticker", {})
    for i, wort in enumerate(sauber):
        art = (
            "haken"
            if wort in sticker_cfg.get("haken", [])
            else "kreuz"
            if wort in sticker_cfg.get("kreuz", [])
            else ""
        )
        start, ende = woerter[i]["s"], woerter[i]["s"] + 1.8
        if (
            art
            and not any(x in VERNEINUNG for x in sauber[max(0, i - 3) : i])
            and len([k for k in karten if k["art"] in {"haken", "kreuz"}]) < 2
            and not any(
                start - k["von"] < 8 for k in karten if k["art"] in {"haken", "kreuz"}
            )
            and _frei(karten, start, ende, fenster)
        ):
            karten.append(
                {"art": art, "text": wort, "wort": wort, "von": start, "bis": ende}
            )
    marken = cfg.get("marken", {})
    markenworte = [(i, marken[w]) for i, w in enumerate(sauber) if w in marken]
    verbunden = set()
    for (i, a), (j, b) in zip(markenworte, markenworte[1:]):
        start, ende = woerter[i]["s"], woerter[j]["s"] + 1.8
        if (
            a != b
            and 0.8 <= woerter[j]["s"] - woerter[i]["s"] <= 6
            and _frei(karten, start, ende, fenster)
        ):
            for domain in (a, b):
                logo_holen(domain, logo_ordner / f"{domain}.png")
            karten.append(
                {
                    "art": "verbindung",
                    "domains": [a, b],
                    "wort": sauber[i],
                    "von": start,
                    "bis": ende,
                }
            )
            verbunden.update({i, j})
    for i, domain in markenworte:
        start, ende = woerter[i]["s"], woerter[i]["s"] + 1.8
        if (
            i not in verbunden
            and len([k for k in karten if k["art"] == "logo"]) < 4
            and _frei(karten, start, ende, fenster)
        ):
            logo_holen(domain, logo_ordner / f"{domain}.png")
            karten.append(
                {
                    "art": "logo",
                    "text": sauber[i],
                    "wort": sauber[i],
                    "domain": domain,
                    "von": start,
                    "bis": ende,
                }
            )
    for i, wort in enumerate(sauber):
        j = (
            next(
                (
                    n
                    for n in range(i + 1, min(len(sauber), i + 10))
                    if sauber[n] == "sondern"
                ),
                None,
            )
            if wort == "nicht"
            else None
        )
        if (
            j is not None
            and j + 1 < len(sauber)
            and len([k for k in karten if k["art"] == "korrektur"]) < 2
        ):
            x, y, start, ende = (
                " ".join(sauber[i + 1 : j]),
                sauber[j + 1],
                woerter[i]["s"],
                woerter[j + 1]["s"] + 2,
            )
            if x and _frei(karten, start, ende, fenster):
                karten.append(
                    {
                        "art": "korrektur",
                        "alt": x,
                        "y_text": y,
                        "wort": x,
                        "von": start,
                        "bis": ende,
                    }
                )
    zaehl = [
        i
        for i, w in enumerate(sauber)
        if w in {"erstens", "zweitens", "drittens", "schritt", "punkt", "tipp"}
    ]
    if len(zaehl) >= 2:
        for nr, i in enumerate(zaehl, 1):
            start, ende = woerter[i]["s"], woerter[i]["s"] + 1.7
            if _frei(karten, start, ende, fenster):
                karten.append(
                    {
                        "art": "zaehler",
                        "nr": nr,
                        "gesamt": len(zaehl),
                        "von": start,
                        "bis": ende,
                    }
                )
    for i, w in enumerate(woerter):
        if re.search(r"\?$", w["w"]):
            start, text = (
                woerter[max(0, i - 8)]["s"],
                " ".join(x["w"] for x in woerter[max(0, i - 8) : i + 1]),
            )
            if 3 <= len(text.split()) <= 9 and _frei(
                karten, start, w["e"] + 1.5, fenster
            ):
                karten.append(
                    {
                        "art": "kommentarblase",
                        "text": text,
                        "von": start,
                        "bis": w["e"] + 1.5,
                    }
                )
                break
    for i, wort in enumerate(sauber):
        start, ende = woerter[i]["s"], woerter[i]["s"] + 2
        if (
            wort in {"handy", "app", "smartphone"}
            and not any(k["art"] == "handyrahmen" for k in karten)
            and _frei(karten, start, ende, fenster)
        ):
            karten.append({"art": "handyrahmen", "von": start, "bis": ende})
    return sorted(karten, key=lambda k: k["von"])


def _shadow(bild: Image.Image, radius: int = 16) -> Image.Image:
    out = Image.new("RGBA", (bild.width + 50, bild.height + 50))
    alpha = bild.getchannel("A").filter(ImageFilter.GaussianBlur(radius))
    out.paste((0, 0, 0, 105), (25, 29), alpha)
    out.alpha_composite(bild)
    return out


def _text(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    rolle: str,
    groesse: int,
    fill: str,
) -> None:
    font = schrift.schrift(rolle, groesse)
    d.text((xy[0] - font.getbbox(text)[0], xy[1]), text, font=font, fill=fill)


def _logo(domain: str, name: str = "") -> Image.Image:
    bild = Image.new("RGBA", (220, 220))
    d = ImageDraw.Draw(bild)
    d.rounded_rectangle((8, 8, 212, 212), radius=34, fill="white")
    try:
        logo = Image.open(pfad("medien", "logos", f"{domain}.png")).convert("RGBA")
        logo.thumbnail((150, 150), Image.Resampling.LANCZOS)
        bild.alpha_composite(logo, ((220 - logo.width) // 2, (220 - logo.height) // 2))
    except OSError:
        label, font = (
            (name or domain.split(".")[0]).upper(),
            schrift.schrift("text", 28),
        )
        _text(
            d,
            ((220 - schrift.breite(label, font)) // 2, 88),
            label,
            "text",
            28,
            "#1B1A2E",
        )
    return _shadow(bild, 12)


def _handy(roh: Path | None, zeit: float) -> Image.Image:
    bild = Image.new("RGBA", (390, 790))
    d = ImageDraw.Draw(bild)
    d.rounded_rectangle((0, 0, 389, 789), radius=58, fill="#101012")
    d.rounded_rectangle((13, 13, 376, 776), radius=46, fill="#222226")
    frame, ziel = (
        None,
        (roh.parent / f"._handy_{int(zeit * 1000)}.jpg") if roh else None,
    )
    if roh and roh.exists():
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{zeit:.3f}",
                    "-i",
                    str(roh),
                    "-frames:v",
                    "1",
                    str(ziel),
                ],
                check=True,
                capture_output=True,
            )
            frame = Image.open(ziel).convert("RGB")
        except (OSError, subprocess.CalledProcessError):
            pass
        finally:
            ziel.unlink(missing_ok=True)
    if frame:
        bild.alpha_composite(
            frame.resize((360, 740), Image.Resampling.LANCZOS).convert("RGBA"), (15, 26)
        )
    else:
        d.rounded_rectangle((15, 26, 375, 766), radius=38, fill="#E8E2D8")
    d.rounded_rectangle((145, 12, 245, 32), radius=10, fill="#050505")
    return _shadow(bild, 18)


def _lokal(k: dict, roh: Path | None) -> Image.Image:
    art = k["art"]
    if art in {"haken", "kreuz"}:
        b = Image.new("RGBA", (320, 390))
        d = ImageDraw.Draw(b)
        farbe = "#2F9E5B" if art == "haken" else "#D84545"
        d.ellipse((12, 12, 308, 308), fill=farbe, outline="white", width=10)
        if art == "haken":
            d.line((86, 158, 136, 210, 235, 105), fill="white", width=24, joint="curve")
        else:
            d.line((94, 96, 226, 228), fill="white", width=24)
            d.line((226, 96, 94, 228), fill="white", width=24)
        label, font = (k.get("text") or "").upper(), schrift.schrift("block", 44)
        _text(
            d,
            ((320 - schrift.breite(label, font)) // 2, 326),
            label,
            "block",
            44,
            "white",
        )
        return _shadow(b, 14).rotate(-6, expand=True, resample=Image.Resampling.BICUBIC)
    if art == "zaehler":
        b = Image.new("RGBA", (410, 255))
        d = ImageDraw.Draw(b)
        _text(d, (0, 0), str(k.get("nr", 1)), "block", 220, "#E8590C")
        _text(d, (250, 145), f"von {k.get('gesamt', 2)}", "text", 36, "white")
        return _shadow(b, 10)
    if art == "korrektur":
        b = Image.new("RGBA", (520, 310))
        d = ImageDraw.Draw(b)
        d.rounded_rectangle((8, 8, 510, 300), radius=22, fill="#FFF8E9")
        _text(d, (38, 55), k.get("alt", "X"), "text", 52, "#29262A")
        d.line((32, 110, 260, 65), fill="#D84545", width=9)
        d.arc((250, 45, 385, 190), 210, 350, fill="#E8590C", width=8)
        d.polygon((372, 52, 398, 76, 366, 82), fill="#E8590C")
        _text(d, (75, 150), k.get("y_text", "Y"), "hand", 90, "#E8590C")
        return _shadow(b, 13).rotate(-3, expand=True, resample=Image.Resampling.BICUBIC)
    if art == "kommentarblase":
        b = Image.new("RGBA", (620, 255))
        d = ImageDraw.Draw(b)
        d.rounded_rectangle((8, 8, 612, 220), radius=34, fill="white")
        d.polygon((80, 215, 120, 215, 92, 246), fill="white")
        d.ellipse((34, 42, 100, 108), fill="#C9A961")
        d.ellipse((50, 54, 84, 88), fill="#6B1F2A")
        _text(d, (122, 40), "Kommentar", "text", 25, "#6B6570")
        font = schrift.schrift("text_normal", 34)
        for i, z in enumerate(schrift.umbrechen(k.get("text", ""), font, 455)[:3]):
            _text(d, (122, 78 + i * 42), z, "text_normal", 34, "#242128")
        return _shadow(b, 13)
    if art == "logo":
        return _logo(k.get("domain", ""), k.get("text", ""))
    if art == "verbindung":
        b = Image.new("RGBA", (650, 250))
        d = ImageDraw.Draw(b)
        a, c = k.get("domains", ["", ""])
        b.alpha_composite(_logo(a), (0, 10))
        b.alpha_composite(_logo(c), (430, 10))
        for x in range(235, 420, 28):
            d.ellipse((x, 120, x + 11, 131), fill="#F1E8D6")
        return b
    if art == "handyrahmen":
        return _handy(roh, float(k.get("von", 0)))
    return Image.new("RGBA", (1, 1))


def platzieren(
    karten: list[dict], gesichter: list[dict], *, links: int, rechts: int
) -> list[dict]:
    """Setzt jede Karte in den Rahmen und meidet mehr als 20 Prozent Gesicht."""
    from .gesicht import bei

    out = []
    for nr, karte in enumerate(karten):
        g = bei(gesichter, karte["von"])
        gx, gy, gb, gh = (
            g["x"] * BREITE,
            g["y"] * HOEHE,
            g["b"] * BREITE,
            g["h"] * HOEHE,
        )
        probe = _lokal(karte, None)
        b, h = probe.size
        plaetze = [
            (links, 330),
            (rechts - b, 430),
            (links, 900),
            (rechts - b, 1050),
            (links, 1320),
            (rechts - b, 1280),
        ]
        plaetze = plaetze[nr % len(plaetze) :] + plaetze[: nr % len(plaetze)]
        for x, y in plaetze:
            x = max(links, min(rechts - b, x))
            y = max(270, min(1620 - h, y))
            ueber = max(0, min(x + b, gx + gb) - max(x, gx)) * max(
                0, min(y + h, gy + gh) - max(y, gy)
            )
            if ueber <= gb * gh * 0.2:
                out.append({**karte, "pos_x": int(x), "y": int(y)})
                break
    return out


def _karte(
    k: dict, *, links: int, rechts: int, roh: Path | None = None, unten: int = 300
) -> Image.Image:
    bild = Image.new("RGBA", (BREITE, HOEHE))
    lokal = _lokal(k, roh)
    x = max(links, min(rechts - lokal.width, int(k.get("pos_x", links))))
    y = max(270, min(1920 - unten - lokal.height, int(k.get("y", 900))))
    bild.alpha_composite(lokal, (x, y))
    return bild


def spur(
    karten: list[dict],
    dauer: float,
    *,
    links: int,
    rechts: int,
    roh: Path | None = None,
    unten: int = 300,
) -> list[tuple[float, float, Image.Image | None]]:
    out, letzte = [], 0.0
    for k in karten:
        start, ende = max(letzte, k["von"]), min(dauer, k["bis"])
        if ende <= start:
            continue
        if start > letzte:
            out.append((letzte, start, None))
        for von, bis, skala in (
            (start, min(ende, start + 0.08), 0.86),
            (min(ende, start + 0.08), min(ende, start + 0.16), 1.06),
            (min(ende, start + 0.16), ende, 1.0),
        ):
            if bis > von:
                ebene = _karte(k, links=links, rechts=rechts, roh=roh, unten=unten)
                if skala != 1 and (box := ebene.getbbox()):
                    teil = ebene.crop(box).resize(
                        (
                            int((box[2] - box[0]) * skala),
                            int((box[3] - box[1]) * skala),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                    ebene = Image.new("RGBA", (BREITE, HOEHE))
                    ebene.alpha_composite(teil, (box[0], box[1]))
                out.append((von, bis, ebene))
        letzte = ende
    if letzte < dauer:
        out.append((letzte, dauer, None))
    return out or [(0.0, dauer, None)]
