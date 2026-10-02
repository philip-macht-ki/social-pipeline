"""Kurze, stille Zusatzreels je Aufnahme: Lese-Reel und übermalter Satz.

Alle sichtbaren Texte entstehen mit Pillow. Das Modul bleibt absichtlich von
den normalen Videostilen getrennt: Es erzeugt fertige Manifeste, die der
Planer wie jedes andere Einzelstück liest.
"""
from __future__ import annotations

import hashlib
import random
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .kern import Ergebnis, dauer, konfig, lauf, lesen, log, pfad, schreiben, takes
from .schrift import breite, groesste_passende, hoehe, schrift
from .texte import VERBOTEN, _fallbacks, pruefe_instagram, pruefe_tiktok, pruefe_youtube
from .urteil import frage, vorlage

BREITE, HOEHE, FPS = 1080, 1920, 30


def _normale_stuecke(take: str) -> list[dict]:
    """Fertige normale Stücke eines Takes, nie die hier erzeugten Zusatzstücke."""
    raus = []
    for datei in pfad("ausgabe").glob(f"{take}-*/stueck.json"):
        daten = lesen(datei, {})
        if daten.get("stil") not in ("lesereel", "uebermalt") and daten.get("status") in ("fertig", "befund"):
            raus.append(daten)
    return raus


def _verboten(text: str) -> str | None:
    if any(zeichen in text for zeichen in ("\u2013", "\u2014", "(", ")")):
        return "Gedankenstriche oder Klammern sind nicht erlaubt."
    if any(wort in text.lower() for wort in VERBOTEN):
        return "Verbotene Formulierung im Text."
    return None


def pruefe_lesereel(daten: object) -> str | None:
    if (not isinstance(daten, dict) or not isinstance(daten.get("brief"), str)
            or not isinstance(daten.get("caption"), str)):
        return "Lese-Reel braucht brief und caption als Text."
    brief = daten["brief"].strip()
    if not brief.startswith("Lieber Algorithmus"):
        return "Der Brief beginnt nicht mit Lieber Algorithmus."
    if not 3 <= len([z for z in brief.splitlines() if z.strip()]) <= 4:
        return "Der Brief braucht drei bis vier Absätze."
    if len(brief.split()) > 70:
        return "Der Brief hat mehr als 70 Wörter."
    return pruefe_caption(daten["caption"]) or _verboten(brief + "\n" + daten["caption"])


def pruefe_caption(caption: object) -> str | None:
    """Hält die Caption kurz und als abschließende Frage fest."""
    if not isinstance(caption, str) or not caption.strip():
        return "Caption fehlt."
    text = caption.strip()
    if len(text) > 280:
        return "Caption ist länger als 280 Zeichen."
    if not text.endswith("?"):
        return "Caption endet nicht mit einer Frage."
    if text.count("?") != 1:
        return "Caption enthält nicht genau eine Frage."
    return _verboten(text)


def pruefe_uebermalt(daten: object) -> str | None:
    if not isinstance(daten, dict):
        return "Übermalter Satz braucht ein Objekt."
    if "passt_nicht" in daten:
        if isinstance(daten["passt_nicht"], str) and daten["passt_nicht"].strip():
            return None
        return "Grund fehlt."
    # Die Satzteile bleiben kurz, damit jede Zeile groß und ohne Umbruch auf
    # dem Handy steht. Die Grenze ist eine Vorgabe für das Modell, die Passung
    # selbst wird unten in Pixeln gemessen.
    felder = {"vorher": 30, "falsch": 16, "richtig": 16, "nachsatz": 32, "caption": 280}
    if set(daten) != set(felder):
        return "Es fehlen Felder oder es sind zusätzliche Felder vorhanden."
    for feld, grenze in felder.items():
        wert = daten.get(feld)
        if not isinstance(wert, str) or not wert.strip():
            return f"{feld} fehlt."
        if len(wert) > grenze:
            return f"{feld} ist länger als {grenze} Zeichen."
    if re.search(r"\b(nicht|kein|keine|nie)\b", daten["vorher"], flags=re.IGNORECASE):
        return "vorher darf keine Verneinung enthalten."
    caption_befund = pruefe_caption(daten["caption"])
    if caption_befund:
        return caption_befund
    return _verboten(" ".join(daten.values()))


def _thema(take: str) -> str:
    rezepte = sorted(pfad("arbeit", take, "stuecke").glob("*/rezept.json"))
    teile = []
    for rezept_pfad in rezepte:
        rezept = lesen(rezept_pfad, {})
        titel = str(rezept.get("titel", "")).strip().replace("\n", " ")
        aussage = str(rezept.get("aussage", "")).strip()
        if titel or aussage:
            teile.append(f"Titel: {titel}\nAussage: {aussage}".strip())
    return "\n\n".join(teile)


def _caption_rueckfall(aussage: str) -> str:
    """Fragt weiter, ohne den Aussagesatz der Caption zu wiederholen."""
    return "Was davon ist für dich der entscheidende Punkt?"


def _textdateien(take: str, caption: str, aussage: str) -> dict:
    rezept = {"titel": "Ein Gedanke", "aussage": aussage, "von_stuecken": 1, "nr": 1}
    marke = konfig("marke")
    gueltige_caption = caption.strip() if not pruefe_caption(caption) else _caption_rueckfall(aussage)
    fallback = _fallbacks(rezept, gueltige_caption, marke)
    hashtags = " ".join(marke.get("hashtags", ["#ideen", "#alltag"])[:4]) or "#ideen #alltag"
    instagram_text = gueltige_caption
    if marke.get("cta_zeile"):
        instagram_text += "\n" + marke["cta_zeile"]
    instagram = {"caption": instagram_text + "\n" + hashtags}
    if pruefe_instagram(instagram, gueltige_caption, marke, rezept):
        instagram = fallback["instagram"]
    daten = {"instagram": instagram, "tiktok": fallback["tiktok"], "youtube": fallback["youtube"],
             "pinterest": fallback["pinterest"], "threads": fallback["threads"], "befunde": []}
    pruefungen = (
        ("tiktok", pruefe_tiktok),
        ("youtube", lambda x: pruefe_youtube(x, marke.get("link", ""), caption)),
    )
    for kanal, pruefung in pruefungen:
        if pruefung(daten[kanal]):
            daten["befunde"].append(f"{kanal}: Rückfalltext nicht prüfbar.")
    return daten


def _png_text(text: str, rolle: str, farbe: str, schatten: bool = False) -> Image.Image:
    grad, zeilen = groesste_passende(text, rolle, list(range(64, 27, -2)), 860, 12)
    if grad is None:
        raise ValueError("Text passt selbst in kleinster Schrift nicht in den Sicherheitsrahmen.")
    bild = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    zeichner = ImageDraw.Draw(bild)
    font = schrift(rolle, grad)
    schritt = int(hoehe(font) * 1.28)
    y = (HOEHE - len(zeilen) * schritt) // 2
    for zeile in zeilen:
        x = (BREITE - breite(zeile, font)) // 2
        if schatten:
            zeichner.text((x + 3, y + 4), zeile, font=font, fill=(0, 0, 0, 150))
        zeichner.text((x, y), zeile, font=font, fill=farbe)
        y += schritt
    return bild


def _alltag(take: str) -> Path | None:
    ordner = pfad("medien", "alltag")
    clips = []
    if ordner.exists():
        clips = sorted(p for p in ordner.glob("*") if p.is_file() and p.suffix.lower() in (".mp4", ".mov"))
    if not clips:
        return None
    return random.Random(hashlib.sha256(take.encode()).hexdigest()).choice(clips)


def _musik() -> Path | None:
    ordner = pfad("medien", "musik")
    if not ordner.exists():
        return None
    return next(
        (p for p in sorted(ordner.iterdir()) if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac")),
        None,
    )


def _lese_video(take: str, text: str, ziel: Path) -> None:
    ebene = ziel.parent / "lese-text.png"
    _png_text(text, "serif", "#FFFFFF", schatten=True).save(ebene)
    hintergrund = _alltag(take)
    quelle = next(iter(pfad("arbeit", take).glob("quelle.*")), None)
    if not hintergrund and not quelle:
        raise FileNotFoundError("Weder Alltag-Clip noch Rohaufnahme gefunden.")
    eingabe = hintergrund or quelle
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.18"
    if not hintergrund:
        if konfig("pipeline").get("schnitt", {}).get("entspiegeln"):
            vf = "hflip," + vf
        # Die Rohaufnahme ist nur der Rückfall. Ein Gesicht darf nicht mit dem
        # Brief konkurrieren, deshalb wird es deutlich zurückgenommen.
        vf += ",gblur=sigma=18,eq=brightness=-0.42:contrast=0.88"
        vf += ",zoompan=z='min(zoom+0.000286,1.06)':d=210:s=1080x1920:fps=30"
    musik = _musik()
    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(eingabe), "-loop", "1", "-i", str(ebene)]
    if musik:
        cmd += ["-stream_loop", "-1", "-i", str(musik)]
    graph = f"[0:v]{vf}[bg];[bg][1:v]overlay=0:0[v]"
    cmd += ["-filter_complex", graph, "-map", "[v]"]
    if musik:
        cmd += ["-map", "2:a", "-shortest"]
    cmd += ["-t", "7", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-movflags", "+faststart", str(ziel)]
    lauf(cmd)


def _uebermalt_layout(daten: dict) -> dict:
    """Misst Körpertexte mit bis zu zwei Zeilen und die Handschrift."""
    max_breite = int(BREITE * 0.80)

    def umbrechen(text: str, font) -> list[str] | None:
        if breite(text, font) <= max_breite:
            return [text]
        woerter = text.split()
        kandidaten = []
        for i in range(1, len(woerter)):
            zeilen = [" ".join(woerter[:i]), " ".join(woerter[i:])]
            if max(breite(z, font) for z in zeilen) <= max_breite:
                kandidaten.append(zeilen)
        return min(kandidaten, key=lambda z: abs(breite(z[0], font) - breite(z[1], font))) if kandidaten else None

    # Der Block steht mittig zwischen oben 300 und unten 300 (Sicherheitsrahmen).
    platz = HOEHE - 600

    def handgrad(koerper: int, text: str) -> int:
        """Handschrift mindestens so groß wie der Text, höchstens 1,6-fach."""
        for grad in range(int(koerper * 1.6), koerper - 1, -2):
            if breite(text, schrift("hand", grad)) <= max_breite:
                return grad
        return koerper

    gefunden = None
    for grad in range(150, 31, -2):
        font = schrift("text_normal", grad)
        zeilen = {"vorher": umbrechen(daten["vorher"], font),
                  "falsch": [daten["falsch"]] if breite(daten["falsch"], font) <= max_breite else None,
                  "nachsatz": umbrechen(daten["nachsatz"], font)}
        if not all(zeilen.values()):
            continue
        zeilenhoehe = int(hoehe(font) * 1.15)
        hand = handgrad(grad, daten["richtig"])
        hand_hoehe = hoehe(schrift("hand", hand))
        abstand_oben, abstand_hand, abstand_unten = 40, 10, int(zeilenhoehe * 0.6)
        gesamt = (len(zeilen["vorher"]) * zeilenhoehe + abstand_oben + hand_hoehe + abstand_hand
                  + zeilenhoehe + abstand_unten + len(zeilen["nachsatz"]) * zeilenhoehe)
        if gesamt <= platz:
            gefunden = grad
            break
    if gefunden is None:
        raise ValueError("Satzteile passen nicht in den Sicherheitsrahmen.")
    koerper, zeilentexte = gefunden, zeilen
    vorher_y = max(300, (HOEHE - gesamt) // 2)
    richtig_y = vorher_y + len(zeilentexte["vorher"]) * zeilenhoehe + abstand_oben
    falsch_y = richtig_y + hand_hoehe + abstand_hand
    nachsatz_y = falsch_y + zeilenhoehe + abstand_unten
    if nachsatz_y + len(zeilentexte["nachsatz"]) * zeilenhoehe > HOEHE - 300:
        raise ValueError("Satzblock passt nicht in den Sicherheitsrahmen.")
    return {
        "block_breite": max_breite,
        "koerper": koerper,
        "hand": hand,
        "zeilentexte": zeilentexte,
        "zeilenhoehe": zeilenhoehe,
        "zeilen": {"vorher": vorher_y, "falsch": falsch_y, "nachsatz": nachsatz_y},
        "richtig_y": richtig_y,
    }


def _uebermalt_bilder(daten: dict, ordner: Path) -> tuple[Path, Path, Path]:
    farben = konfig("marke").get("farben", {})
    grund, akzent = farben.get("hell", "#FBF5EC"), farben.get("akzent", "#E8590C")
    layout = _uebermalt_layout(daten)
    basis = Image.new("RGBA", (BREITE, HOEHE), grund)
    zeichner = ImageDraw.Draw(basis)
    font = schrift("text_normal", layout["koerper"])
    for feld in ("vorher", "falsch", "nachsatz"):
        for nr, text in enumerate(layout["zeilentexte"][feld]):
            x = (BREITE - breite(text, font)) // 2
            y = layout["zeilen"][feld] + nr * layout["zeilenhoehe"]
            zeichner.text((x, y), text, font=font, fill=farben.get("dunkel", "#1B1A2E"))
    mitte = basis.copy()
    ende = basis.copy()
    y = layout["zeilen"]["falsch"] + hoehe(font) // 2
    x = (BREITE - breite(daten["falsch"], font)) // 2
    pinsel = ImageDraw.Draw(mitte)
    randomer = random.Random(17)
    pinselbreite = breite(daten["falsch"], font)
    punkte = [(x - 42, y)] + [
        (x + i, y + randomer.randint(-12, 12)) for i in range(0, pinselbreite + 85, 12)
    ]
    pinsel.line(punkte, fill=akzent, width=max(112, int(hoehe(font) * 0.92)), joint="curve")
    ende.paste(mitte)
    hand = schrift("hand", layout["hand"])
    richtig_x = (BREITE - breite(daten["richtig"], hand)) // 2
    ImageDraw.Draw(ende).text((richtig_x, layout["richtig_y"]), daten["richtig"], font=hand, fill=akzent)
    wege = (ordner / "uebermalt-anfang.png", ordner / "uebermalt-mitte.png", ordner / "uebermalt-ende.png")
    for bild, weg in zip((basis, mitte, ende), wege):
        bild.convert("RGB").save(weg)
    return wege


def _uebermalt_video(daten: dict, ziel: Path) -> None:
    a, m, e = _uebermalt_bilder(daten, ziel.parent)
    with tempfile.TemporaryDirectory() as tmp:
        liste = Path(tmp) / "liste.txt"
        liste.write_text(
            f"file '{a.resolve()}'\nduration 2\nfile '{m.resolve()}'\nduration 1.2\n"
            f"file '{e.resolve()}'\nduration 4.8\nfile '{e.resolve()}'\n"
        )
        lauf(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(liste), "-f", "lavfi", "-i",
              "anoisesrc=d=8:c=pink:r=48000", "-filter:a", "volume='if(between(t,2,3.2),0.12,0)'",
              "-shortest", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
              "-movflags", "+faststart", str(ziel)])


def _manifest(take: str, art: str, ziel: Path, caption: str, aussage: str | None = None) -> None:
    for name in ("tiktok.mp4", "youtube.mp4"):
        (ziel / name).unlink(missing_ok=True)
        (ziel / name).hardlink_to(ziel / "instagram.mp4")
    # Das Cover ist bewusst ein echtes Frame, damit alle Upload-Wege es lesen können.
    lauf(["ffmpeg", "-y", "-ss", "1", "-i", str(ziel / "instagram.mp4"), "-frames:v", "1",
          str(ziel / "cover.jpg")])
    schreiben(ziel / "texte.json", _textdateien(take, caption, aussage or caption))
    schreiben(ziel / "stueck.json", {"id": f"{take}-{'lese' if art == 'lesereel' else 'uebermalt'}",
              "take": take,
              "nr": 1, "von_stuecken": 1, "stil": art, "dauer_s": dauer(ziel / "instagram.mp4"),
              "dateien": {"instagram": "instagram.mp4", "tiktok": "tiktok.mp4", "youtube": "youtube.mp4"},
              "status": "fertig", "befunde": []})


def _bauen_lese(take: str) -> Ergebnis:
    antwort = frage(vorlage("lesereel", zielgruppe=konfig("marke").get("zielgruppe", ""), thema=_thema(take)),
                    zweck="lesereel", rueckfall=lambda: None, pruefe=pruefe_lesereel)
    if not isinstance(antwort, dict):
        return Ergebnis("befund", "Kein Lese-Reel: Modellurteil fehlt.")
    ziel = pfad("ausgabe", f"{take}-lese")
    ziel.mkdir(parents=True, exist_ok=True)
    _lese_video(take, antwort["brief"], ziel / "instagram.mp4")
    _manifest(take, "lesereel", ziel, antwort["caption"], antwort["brief"])
    return Ergebnis("ok", "Lese-Reel gebaut.")


def _bauen_uebermalt(take: str) -> Ergebnis:
    transkript_pfad = pfad("arbeit", take, "transkript.txt")
    try:
        transkript = transkript_pfad.read_text(encoding="utf-8")
    except OSError:
        transkript = ""
    antwort = frage(vorlage("uebermalt", transkript=transkript), zweck="uebermalt",
                    rueckfall=lambda: {"passt_nicht": "Kein Modellurteil."}, pruefe=pruefe_uebermalt)
    if not isinstance(antwort, dict) or "passt_nicht" in antwort:
        grund = antwort.get("passt_nicht", "Urteil fehlt.") if isinstance(antwort, dict) else "Urteil fehlt."
        return Ergebnis("nichts", f"Kein übermalter Satz: {grund}")
    ziel = pfad("ausgabe", f"{take}-uebermalt")
    ziel.mkdir(parents=True, exist_ok=True)
    _uebermalt_video(antwort, ziel / "instagram.mp4")
    aussage = " ".join(antwort[feld] for feld in ("vorher", "richtig", "nachsatz"))
    _manifest(take, "uebermalt", ziel, antwort["caption"], aussage)
    return Ergebnis("ok", "Übermalten Satz gebaut.")


def befehl(args) -> int:
    cfg = konfig("pipeline").get("kurzstuecke", {})
    ziele = list(getattr(args, "ziel", []) or [t.name for t in takes() if _normale_stuecke(t.name)])
    for take in ziele:
        if not _normale_stuecke(take):
            log(f"nichts: {take}: kein fertiges normales Stück.")
            continue
        merker_pfad = pfad("arbeit", take, "take.json")
        merker = lesen(merker_pfad, {})
        gebaut = merker.get("kurzstuecke", {})
        for art, aktiv, funktion in (("lesereel", cfg.get("lesereel", True), _bauen_lese),
                                     ("uebermalt", cfg.get("uebermalt", True), _bauen_uebermalt)):
            if not aktiv:
                continue
            if gebaut.get(art) and not getattr(args, "neu", False):
                log(f"nichts: {take}: {art} schon geprüft.")
                continue
            try:
                ergebnis = funktion(take)
            except Exception as fehler:
                ergebnis = Ergebnis("fehler", str(fehler))
            gebaut[art] = ergebnis.status
            merker["kurzstuecke"] = gebaut
            schreiben(merker_pfad, merker)
            log(f"{ergebnis.status}: {take}: {ergebnis.meldung}")
    return 0
