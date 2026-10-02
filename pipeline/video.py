"""Rohschnitt und Fassungen je Plattform: `befehl_bauen`, `befehl_fassungen`.

Die Schnittrechnung steckt in `schnitt.py` (reine Zahlen), die Text-Ebenen in
`ebenen.py`/`titelband.py` (Pillow). Hier stehen nur die ffmpeg-Aufrufe und
die Reihenfolge. Kein Urteil über Zeiten/Maße/Dateien (Grundsatz
ARCHITEKTUR.md); Urteil nur dort, wo Inhalt entschieden wird (Stichworte,
Titelband-Kürzung), und das steckt in `titelband.py`/hier nur beim Aufruf.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image

from . import bausteine, ebenen, einwort, gesicht, schnitt, titelband, urteil, wortspur
from .kern import Ergebnis, konfig, lauf, lesen, log, pfad, schreiben, stueck_ordner, stuecke


# --------------------------------------------------------------- Hilfen ---

def _rezept_pfad(stueck_id: str) -> Path:
    return stueck_ordner(stueck_id) / "rezept.json"


def _stueck_id(p: Path) -> str:
    return f"{p.parent.parent.name}-{p.name}"


def _ziel_stuecke(args: argparse.Namespace) -> list[str]:
    alle = {_stueck_id(p): p for p in stuecke()}
    if not getattr(args, "ziel", None):
        return list(alle)
    ziel: list[str] = []
    for z in args.ziel:
        if z in alle:
            ziel.append(z)
            continue
        treffer = [sid for sid, p in alle.items() if p.parent.parent.name == z]
        ziel.extend(treffer if treffer else [z])
    gesehen: set[str] = set()
    out = []
    for z in ziel:
        if z not in gesehen:
            gesehen.add(z)
            out.append(z)
    return out


def _woerter(take: str) -> list[dict]:
    return lesen(pfad("arbeit", take, "woerter.json"), []) or []


def _saetze(take: str) -> list[dict]:
    return lesen(pfad("arbeit", take, "saetze.json"), []) or []


def _quelle(take: str) -> Path | None:
    ordner = pfad("arbeit", take)
    if not ordner.exists():
        return None
    for p in sorted(ordner.iterdir()):
        if p.name.startswith("quelle."):
            return p
    return None


def _satz_wortbereich(saetze: list[dict], nr: int) -> tuple[int, int] | None:
    for s in saetze:
        if s["nr"] == nr:
            return s["von_wort"], s["bis_wort"]
    return None


def _ausgabe_ordner(stueck_id: str) -> Path:
    return pfad("ausgabe", stueck_id)


def _neue_zeit(t: float, segmente_quellzeit: list[list[float]]) -> float | None:
    """Bildet eine Quellzeit über dieselben Segmentgrenzen wie `roh.mp4` auf die
    neue (geschnittene) Zeitachse ab. None, wenn die Stelle herausgeschnitten wurde."""
    versatz = 0.0
    for s, e in segmente_quellzeit:
        if s <= t <= e:
            return round(versatz + (t - s), 4)
        versatz += e - s
    return None


# -------------------------------------------------------------- bauen ---

def bauen_stueck(stueck_id: str, *, neu: bool = False) -> Ergebnis:
    ordner = _ausgabe_ordner(stueck_id)
    roh = ordner / "roh.mp4"
    zeitachse_pfad = ordner / "zeitachse.json"
    if roh.exists() and zeitachse_pfad.exists() and not neu:
        return Ergebnis("nichts", "roh.mp4 vorhanden, --neu erzwingt Neubau.")

    rezept_pfad = _rezept_pfad(stueck_id)
    rezept = lesen(rezept_pfad)
    if not rezept:
        return Ergebnis("fehler", "kein rezept.json gefunden.")
    take = rezept["take"]
    quelle = _quelle(take)
    if not quelle:
        return Ergebnis("fehler", f"keine Quelldatei in arbeit/{take}/.")
    woerter = _woerter(take)
    saetze = _saetze(take)
    if not woerter or not saetze:
        return Ergebnis("fehler", "woerter.json oder saetze.json fehlt oder ist leer.")

    von = _satz_wortbereich(saetze, rezept["von_satz"])
    bis = _satz_wortbereich(saetze, rezept["bis_satz"])
    if von is None or bis is None:
        return Ergebnis("fehler", "Satznummern aus rezept.json nicht in saetze.json gefunden.")
    von_wort, bis_wort = von[0], bis[1]

    w = schnitt.werte()
    segmente = schnitt.pausenschnitt(woerter, von_wort, bis_wort, w)

    hook = rezept.get("hook")
    if hook:
        hook_bereich = _satz_wortbereich(saetze, hook["von_satz"])
        if hook_bereich:
            hv, hb = hook_bereich
            ab_wort = hook.get("ab_wort")
            if ab_wort is not None and hv <= int(ab_wort) <= hb:
                hv = int(ab_wort)
            segmente = schnitt.hook_vorn(segmente, hv, hb)

    if not segmente:
        return Ergebnis("fehler", "keine Segmente nach dem Pausenschnitt (leerer Wortbereich?).")
    # Vor-/Nachlauf nur an den echten Rändern der fertigen Kette (Anfang und
    # Ende), nicht an jeder inneren Fuge: die inneren Fugen (auch die neue Fuge
    # dort, wo der Hook herausgezogen wurde) bekommen stattdessen die 0,12 s
    # Tonblende gegen Klicks, siehe unten.
    segmente = schnitt.raender(segmente, woerter, w)

    achse = schnitt.neue_zeitachse(woerter, segmente)
    gesamt_dauer = achse["dauer_s"]
    if gesamt_dauer <= 0:
        return Ergebnis("fehler", "errechnete Dauer ist 0.")

    schnitt_konf = konfig("pipeline").get("schnitt", {})
    entspiegeln = bool(schnitt_konf.get("entspiegeln", False))
    belichtung = bool(schnitt_konf.get("belichtung", True))
    zoomstufen = schnitt.zoom_takt(len(segmente), w)

    teile: list[str] = []
    vlabels: list[str] = []
    alabels: list[str] = []
    for i, (s, e, _, _) in enumerate(segmente):
        vlab, alab = f"v{i}", f"a{i}"
        kette = f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS,"
        if entspiegeln:
            kette += "hflip,"
        kette += "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        kette += schnitt.zoom_crop_filter(zoomstufen[i], augenlinie=w.augenlinie)
        kette += "fps=30,"
        if belichtung:
            kette += "curves=all='0/0 0.5/0.54 1/0.97',eq=contrast=1.06,unsharp=5:5:0.5,"
        kette += f"format=yuv420p[{vlab}]"
        teile.append(kette)

        laenge = max(0.02, e - s)
        blende = min(w.blende_segment, max(0.01, laenge / 2 - 0.01))
        aus_start = max(0.0, laenge - blende)
        teile.append(
            f"[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={blende:.3f},afade=t=out:st={aus_start:.3f}:d={blende:.3f}[{alab}]"
        )
        vlabels.append(f"[{vlab}]")
        alabels.append(f"[{alab}]")

    concat_in = "".join(f"{v}{a}" for v, a in zip(vlabels, alabels))
    teile.append(f"{concat_in}concat=n={len(segmente)}:v=1:a=1[vcat][acat]")
    teile.append("[acat]loudnorm=I=-14:TP=-1.5:LRA=11[afinal]")
    filtergraph = ";".join(teile)

    roh.parent.mkdir(parents=True, exist_ok=True)
    lauf([
        "ffmpeg", "-y", "-i", str(quelle), "-filter_complex", filtergraph,
        "-map", "[vcat]", "-map", "[afinal]",
        "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(roh),
    ])
    schreiben(zeitachse_pfad, achse)
    log(wortspur.nachziehen(ordner).meldung)
    return Ergebnis("ok", f"{len(segmente)} Segmente, {gesamt_dauer:.1f} s -> {roh.name}")


def befehl_bauen(args: argparse.Namespace) -> int:
    ziel = _ziel_stuecke(args)
    if not ziel:
        log("nichts: keine Stücke gefunden (erst 'zerlegen' laufen lassen).")
        return 0
    fehler = 0
    for sid in ziel:
        try:
            ergebnis = bauen_stueck(sid, neu=args.neu)
        except Exception as e:  # ein Stück darf die anderen nicht mitreißen
            ergebnis = Ergebnis("fehler", str(e))
        log(f"{ergebnis.status}: bauen {sid}: {ergebnis.meldung}")
        fehler += ergebnis.status == "fehler"
    return 1 if fehler and fehler == len(ziel) else 0


# ---------------------------------------------------------- fassungen ---

def _substantive_rueckfall(saetze_bereich: list[dict]) -> dict:
    """Rückfall ohne Modell: längste großgeschriebenen Wörter (Substantiv-Näherung)."""
    kandidaten: list[tuple[str, int]] = []
    for s in saetze_bereich:
        for tok in s["text"].split():
            wort = tok.strip(".,!?:;\"'()„“–—")
            if len(wort) >= 6 and wort[:1].isupper():
                kandidaten.append((wort, s["nr"]))
    gesehen: set[str] = set()
    out = []
    for wort, nr in sorted(kandidaten, key=lambda t: -len(t[0])):
        if wort.lower() in gesehen:
            continue
        gesehen.add(wort.lower())
        out.append({"text": wort, "satz": nr})
        if len(out) >= 4:
            break
    return {"kacheln": out}


def _kacheln_rezept(rezept: dict, rezept_pfad: Path, saetze: list[dict]) -> list[dict]:
    if rezept.get("kacheln") is not None:
        return rezept["kacheln"]
    bereich = [s for s in saetze if rezept["von_satz"] <= s["nr"] <= rezept["bis_satz"]]
    text = "\n".join(f"{s['nr']}: {s['text']}" for s in bereich)

    def rueckfall():
        return _substantive_rueckfall(bereich)

    def pruefe(antwort):
        if not isinstance(antwort, dict) or not isinstance(antwort.get("kacheln"), list):
            return 'Antwort muss {"kacheln": [{"text","satz"}, …]} sein.'
        if not (3 <= len(antwort["kacheln"]) <= 5):
            return "3 bis 5 Kacheln erwartet."
        return None

    try:
        antwort = urteil.frage(urteil.vorlage("stichworte", saetze=text), zweck="stichworte",
                                rueckfall=rueckfall, pruefe=pruefe)
    except urteil.KeinUrteil:
        antwort = rueckfall()
    kacheln = antwort.get("kacheln", []) if isinstance(antwort, dict) else []
    rezept["kacheln"] = kacheln
    schreiben(rezept_pfad, rezept)
    return kacheln


def _kacheln_mit_zeit(kacheln: list[dict], saetze: list[dict], woerter: list[dict],
                       segmente_quellzeit: list[list[float]]) -> list[dict]:
    out = []
    for k in kacheln:
        satz = next((s for s in saetze if s["nr"] == k.get("satz")), None)
        if not satz or not (0 <= satz["von_wort"] < len(woerter)):
            continue
        t_neu = _neue_zeit(woerter[satz["von_wort"]]["s"], segmente_quellzeit)
        if t_neu is None:
            continue
        out.append({"text": k.get("text", ""), "start": t_neu})
    return out


def _stil_waehlen(rezept: dict, rezept_pfad: Path) -> str:
    aktuell = (rezept.get("stil") or {}).get("reel")
    if aktuell:
        return aktuell
    stile_konf = konfig("stile").get("instagram", {})
    optionen = list(stile_konf.get("reel", ["klar"]))
    gesperrt = set(stile_konf.get("gesperrt", []))
    optionen = [o for o in optionen if o not in gesperrt] or ["klar"]
    zaehler = {o: 0 for o in optionen}
    for p in stuecke():
        r = lesen(p / "rezept.json", {}) or {}
        s = (r.get("stil") or {}).get("reel")
        if s in zaehler:
            zaehler[s] += 1
    gewaehlt = min(optionen, key=lambda o: zaehler[o])
    rezept.setdefault("stil", {})["reel"] = gewaehlt
    schreiben(rezept_pfad, rezept)
    return gewaehlt


def _plattform_stil(rezept: dict, plattform: str, instagram_stil: str) -> str:
    """Wählt nur einen Stil, den die Zielplattform ausdrücklich erlaubt."""
    art = "video" if plattform == "tiktok" else "short"
    erlaubt = set(konfig("stile").get(plattform, {}).get(art, []))
    stil = instagram_stil if instagram_stil in erlaubt else "klar"
    rezept.setdefault("stil", {})[plattform] = stil
    return stil


def _kartenwoerter(karte: dict) -> list[str]:
    """Wörter, die eine Karte in ihrer Zeit bereits lesbar zeigt."""
    if karte.get("art") == "korrektur":
        text = f"{karte.get('alt', '')} {karte.get('y_text', '')}"
    else:
        text = str(karte.get("wort", ""))
    return [wort for wort in text.split() if wort]


def _karten_fuer_rahmen(karten: list[dict], rahmen: dict, links: int, rechts: int,
                         roh: Path | None) -> list[dict]:
    """Hält Karten mit ihrer echten Höhe oberhalb der Plattformleiste."""
    unten = int(rahmen["unten"])
    out = []
    for karte in karten:
        hoehe = bausteine._lokal(karte, roh).height
        maximum = 1920 - unten - hoehe
        if maximum < 270:
            continue
        out.append({**karte, "y": max(270, min(int(karte.get("y", 900)), maximum))})
    return out


def _spuren_bauen(rezept: dict, rezept_pfad: Path, style: str, woerter_neu: list[dict],
                   saetze: list[dict], woerter_quelle: list[dict], segmente_quellzeit: list[list[float]],
                   dauer: float, plattform: str, rahmen: dict, marke: dict,
                   karten: list[dict] | None = None, gesichter: list[dict] | None = None
                  ) -> list[list[tuple[float, float, Image.Image | None]]]:
    rp = rahmen[plattform]
    farben = marke.get("farben", {})
    farben_ut = {"an": "#f4f0e6", "aus": "#8b8474"}
    spuren: list[list[tuple[float, float, Image.Image | None]]] = []

    if style == "klar":
        spuren.append(ebenen.titel_spur(rezept.get("titel", ""), dauer, oben=rp["oben"], bis=4.8,
                                        farbe="#f4f0e6"))
        spuren.append(ebenen.karaoke_spur(woerter_neu, dauer, unten=rp["unten"], farben=farben_ut))
    elif style == "titelband":
        p = titelband.passung(rezept.get("titel", ""))
        band = titelband.bild(p["zeilen"] or [rezept.get("titel", "")], p["grad"])
        spuren.append(ebenen.titelband_spur(band, dauer, oben=rp["oben"], bis=4.8))
        spuren.append(ebenen.karaoke_spur(woerter_neu, dauer, unten=rp["unten"], farben=farben_ut))
    elif style == "stichworte":
        kacheln = _kacheln_mit_zeit(_kacheln_rezept(rezept, rezept_pfad, saetze), saetze,
                                     woerter_quelle, segmente_quellzeit)
        spuren.append(ebenen.kacheln_spur(kacheln, dauer, titel_bis=0.0, farben=farben))
        spuren.append(ebenen.karaoke_spur(woerter_neu, dauer, unten=rp["unten"], farben=farben_ut))
    elif style in {"einwort", "schwarzbild"}:
        links = int(rp.get("links", 60))
        rechts = 1080 - int(rp.get("aktionsleiste", 180))
        wortstil = (rezept.get("wortstil") or "klar")
        spuren.append(ebenen.titel_spur(rezept.get("titel", ""), dauer, oben=rp["oben"], bis=4.8,
                                        farbe="#f4f0e6"))
        spuren.append(einwort.spur(woerter_neu, dauer, stil=wortstil, links=links, rechts=rechts,
                                   akzentfarbe=farben.get("akzent", "#E8590C"), gesichter=gesichter,
                                   auslassen=[{"wort": wort, "von": k["von"] - .2, "bis": k["bis"]}
                                              for k in (karten or [])
                                              if k["art"] in {"haken", "kreuz", "korrektur"}
                                              for wort in _kartenwoerter(k)],
                                   schwarz=style == "schwarzbild", zoom=bool(rezept.get("zoom_punch"))))
        if karten:
            karten_plattform = _karten_fuer_rahmen(karten, rp, links, rechts,
                                                    rezept.get("_roh_fuer_bausteine"))
            spuren.append(bausteine.spur(karten_plattform, dauer, links=links, rechts=rechts,
                                         roh=rezept.get("_roh_fuer_bausteine"), unten=int(rp["unten"])))
    else:
        spuren.append(ebenen.karaoke_spur(woerter_neu, dauer, unten=rp["unten"], farben=farben_ut))

    spuren.append(ebenen.wortmarke_spur(marke.get("wortmarke", "MARKE"), dauer, unten=rp["unten"],
                                        rechts=rp["rechts"], farbe=farben.get("grau", "#5B5A6E")))
    return spuren


def _overlay(roh: Path, liste: Path, ziel: Path) -> None:
    lauf([
        "ffmpeg", "-y", "-i", str(roh), "-f", "concat", "-safe", "0", "-i", str(liste),
        "-filter_complex", "[1:v]format=rgba[ov];[0:v][ov]overlay=format=auto[vout]",
        "-map", "[vout]", "-map", "0:a",
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(ziel),
    ])


def _mit_schlusskarte(basis: Path, schluss_bild: Path, ziel: Path, halte: float = 2.2) -> None:
    lauf([
        "ffmpeg", "-y", "-i", str(basis),
        "-loop", "1", "-t", f"{halte:.2f}", "-i", str(schluss_bild),
        "-f", "lavfi", "-t", f"{halte:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-filter_complex",
        "[1:v]scale=1080:1920,fps=30,format=yuv420p[sv];"
        "[0:v][0:a][sv][2:a]concat=n=2:v=1:a=1[vout][aout]",
        "-map", "[vout]", "-map", "[aout]",
        "-r", "30", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(ziel),
    ])


def _instagram_fassung(quelle: Path, ziel: Path, dauer: float) -> str:
    """> 100 MB: neu kodieren auf <= 82 MB (Falle "Container ERROR" bei großen
    Dateien, siehe befund_schnitt.md, 21.09.2026: 168 MB scheitern, 88 MB gehen durch)."""
    shutil.copyfile(quelle, ziel)
    mb = ziel.stat().st_size / 1e6
    if mb <= 100.0:
        return ""
    rate = max(0.5, min(6.0, (82.0 * 8) / max(dauer, 1.0) - 0.13))
    neu = ziel.with_suffix(".neu.mp4")
    lauf([
        "ffmpeg", "-y", "-i", str(ziel),
        "-c:v", "libx264", "-preset", "medium", "-crf", "24",
        "-maxrate", f"{rate:.2f}M", "-bufsize", f"{rate*2:.2f}M",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(neu),
    ])
    neu.replace(ziel)
    mb2 = ziel.stat().st_size / 1e6
    return f"Instagram-Fassung war {mb:.1f} MB, auf {mb2:.1f} MB nachkomprimiert."


def _schluss_text(rezept: dict, take: str) -> str:
    """Text der Schlusskarte: `schluss` aus dem Rezept, sonst bei Mehrteilern
    "Teil n+1: <Titel des nächsten Stücks>", sonst ein neutraler Abschied."""
    schluss = rezept.get("schluss")
    if schluss:
        return schluss
    von_stuecken = rezept.get("von_stuecken", 1) or 1
    nr = rezept.get("nr", 1) or 1
    if von_stuecken > 1 and nr < von_stuecken:
        naechstes = lesen(pfad("arbeit", take, "stuecke", f"{nr + 1:02d}", "rezept.json"))
        titel_naechstes = ((naechstes or {}).get("titel") or "").split("\n")[0]
        if titel_naechstes:
            return f"Teil {nr + 1}: {titel_naechstes}"
    return "Danke fürs Zuschauen."


def _cover_sekunde(rezept: dict, saetze: list[dict], segmente_quellzeit: list[list[float]],
                    dauer: float) -> float:
    """Mitte des ersten Satzes NACH dem Hook, auf der neuen Zeitachse."""
    hook_satz = (rezept.get("hook") or {}).get("von_satz")
    kandidaten = [s for s in saetze
                  if rezept["von_satz"] <= s["nr"] <= rezept["bis_satz"] and s["nr"] != hook_satz]
    rueckfall = min(dauer * 0.3, max(0.0, dauer - 0.1))
    if not kandidaten:
        return rueckfall
    satz = min(kandidaten, key=lambda s: s["nr"])
    t = _neue_zeit((satz["s"] + satz["e"]) / 2, segmente_quellzeit)
    return rueckfall if t is None else min(t, max(0.0, dauer - 0.1))


def fassungen_stueck(stueck_id: str, *, neu: bool = False) -> Ergebnis:
    ordner = _ausgabe_ordner(stueck_id)
    roh = ordner / "roh.mp4"
    achse = lesen(ordner / "zeitachse.json")
    if not roh.exists() or not achse:
        return Ergebnis("fehler", "roh.mp4/zeitachse.json fehlen, erst 'bauen' laufen lassen.")
    ziel_dateien = [ordner / n for n in ("instagram.mp4", "tiktok.mp4", "cover.jpg")]
    # Vorhandene Fassungen zählen nur, wenn sie jünger sind als roh.mp4 und
    # zeitachse.json. Sonst ginge nach einem Neubau von roh.mp4 die alte,
    # falsch untertitelte Fassung raus (so passiert bei Y39 im Betrieb).
    quelle_stand = max(roh.stat().st_mtime_ns, (ordner / "zeitachse.json").stat().st_mtime_ns)
    aktuell = all(p.exists() and p.stat().st_mtime_ns >= quelle_stand for p in ziel_dateien)
    if aktuell and not neu:
        return Ergebnis("nichts", "Fassungen vorhanden, --neu erzwingt Neubau.")

    rezept_pfad = _rezept_pfad(stueck_id)
    rezept = lesen(rezept_pfad)
    if not rezept:
        return Ergebnis("fehler", "kein rezept.json gefunden.")
    take = rezept["take"]
    saetze = _saetze(take)
    woerter_quelle = _woerter(take)
    dauer = achse["dauer_s"]
    woerter_neu = achse["woerter"]
    befunde: list[str] = []

    marke = konfig("marke")
    rahmen = konfig("sicherheitsrahmen")
    style = _stil_waehlen(rezept, rezept_pfad)
    # Das optionale Modul kann den Hintergrund ersetzen und ein Sperrfenster
    # ins Rezept schreiben. Ohne Modul bleibt der Rohschnitt unverändert.
    try:
        from . import ki_einblendung
    except ImportError:
        ki_einblendung = None
    grund = ki_einblendung.anwenden(stueck_id, rezept, rezept_pfad, roh, achse) if ki_einblendung else roh
    wortstile = ["klar", "kontur", "pille"]
    if style in {"einwort", "schwarzbild"}:
        benutzt = {str((lesen(p / "rezept.json", {}) or {}).get("wortstil", "")) for p in stuecke()}
        rezept["wortstil"] = min(wortstile, key=lambda x: (x in benutzt, wortstile.index(x)))
        rezept["zoom_punch"] = rezept.get("nr", 1) % 2 == 0
        gesichter = gesicht.laden(grund, ordner / "gesicht.json", dauer)
        karten = [k for k in bausteine.finden(woerter_neu, rezept) if k["von"] < dauer]
        for karte in karten:
            karte["bis"] = min(karte["bis"], dauer)
        karten = bausteine.platzieren(karten, gesichter,
                                      links=int(rahmen["instagram"].get("links", 60)),
                                      rechts=1080 - int(rahmen["instagram"].get("aktionsleiste", 180)))
        karten = [karte for karte in karten if any(
            bausteine._lokal(karte, roh).height <= 1920 - int(plattform["unten"]) - 270
            for plattform in (rahmen["instagram"], rahmen["tiktok"], rahmen["youtube"])
        )]
        rezept["bausteine"] = [k["art"] for k in karten] + [f"wortstil_{rezept['wortstil']}"]
        if rezept["zoom_punch"]:
            rezept["bausteine"].append("zoom_punch")
        schreiben(rezept_pfad, rezept)
        # Nur für die Renderphase: kein rechnerbezogener Pfad im Rezept speichern.
        rezept["_roh_fuer_bausteine"] = roh
    else:
        gesichter, karten = None, []

    stil_tiktok = _plattform_stil(rezept, "tiktok", style)
    stil_youtube = _plattform_stil(rezept, "youtube", style)
    spuren_standard = _spuren_bauen(rezept, rezept_pfad, style, woerter_neu, saetze, woerter_quelle,
                                    achse["segmente"], dauer, "instagram", rahmen, marke, karten, gesichter)
    spuren_tiktok = _spuren_bauen(rezept, rezept_pfad, stil_tiktok, woerter_neu, saetze, woerter_quelle,
                                  achse["segmente"], dauer, "tiktok", rahmen, marke, karten, gesichter)
    spuren_youtube = None
    if stil_youtube != style:
        spuren_youtube = _spuren_bauen(rezept, rezept_pfad, stil_youtube, woerter_neu, saetze, woerter_quelle,
                                       achse["segmente"], dauer, "youtube", rahmen, marke, karten, gesichter)
    rezept.pop("_roh_fuer_bausteine", None)
    schreiben(rezept_pfad, rezept)

    ebenen_ordner = ordner / "ebenen"
    liste_standard = ebenen.schreiben(ebenen_ordner / "standard", dauer, *spuren_standard)
    liste_tiktok = ebenen.schreiben(ebenen_ordner / "tiktok", dauer, *spuren_tiktok)
    liste_youtube = (ebenen.schreiben(ebenen_ordner / "youtube", dauer, *spuren_youtube)
                     if spuren_youtube is not None else None)

    basis_standard = ordner / "_basis_standard.mp4"
    basis_tiktok = ordner / "_basis_tiktok.mp4"
    basis_youtube = ordner / "_basis_youtube.mp4"
    _overlay(grund, liste_standard, basis_standard)
    _overlay(grund, liste_tiktok, basis_tiktok)
    if liste_youtube is not None:
        _overlay(grund, liste_youtube, basis_youtube)

    letzter_frame_pfad = ordner / "_letzter_frame.jpg"
    titelband.erstes_standbild(grund, max(0.0, dauer - 0.08), letzter_frame_pfad)
    schluss_text = _schluss_text(rezept, take)
    schluss_bild = ebenen.schlusskarte_bild(Image.open(letzter_frame_pfad), schluss_text,
                                            farbe=marke.get("farben", {}).get("hell", "#FBF5EC"))
    schluss_bild_pfad = ordner / "_schlusskarte.png"
    schluss_bild.save(schluss_bild_pfad)

    voll_pfad = ordner / "_voll.mp4"
    _mit_schlusskarte(basis_standard, schluss_bild_pfad, voll_pfad)
    _mit_schlusskarte(basis_tiktok, schluss_bild_pfad, ordner / "tiktok.mp4")

    ig_meldung = _instagram_fassung(voll_pfad, ordner / "instagram.mp4", dauer)
    if ig_meldung:
        befunde.append(ig_meldung)

    dateien = {"instagram": "instagram.mp4", "tiktok": "tiktok.mp4"}
    if dauer <= 179.0:
        if liste_youtube is None:
            shutil.copyfile(voll_pfad, ordner / "youtube.mp4")
        else:
            _mit_schlusskarte(basis_youtube, schluss_bild_pfad, ordner / "youtube.mp4")
        dateien["youtube"] = "youtube.mp4"
    else:
        befunde.append(f"zu lang für ein Short ({dauer:.0f} s > 179 s), kein youtube.mp4.")

    cover_ergebnis = titelband.cover(
        grund, _cover_sekunde(rezept, saetze, achse["segmente"], dauer),
        rezept.get("titel", ""), marke.get("wortmarke", "MARKE"), ordner / "cover.jpg",
    )
    if cover_ergebnis.meldung:
        befunde.append(cover_ergebnis.meldung)

    for tmp in (basis_standard, basis_tiktok, basis_youtube, voll_pfad, letzter_frame_pfad):
        tmp.unlink(missing_ok=True)

    stueck_json = {
        "id": stueck_id, "dauer_s": round(dauer, 2), "dateien": dateien,
        "status": "befund" if befunde else "fertig", "befunde": befunde,
    }
    schreiben(ordner / "stueck.json", stueck_json)
    rezept["status"] = stueck_json["status"]
    if befunde:
        rezept.setdefault("befunde", []).extend(befunde)
    schreiben(rezept_pfad, rezept)

    meldung = f"Stil {style}, {dauer:.1f} s" + (f"; {'; '.join(befunde)}" if befunde else "")
    return Ergebnis("befund" if befunde else "ok", meldung, {"dateien": dateien})


def befehl_fassungen(args: argparse.Namespace) -> int:
    ziel = _ziel_stuecke(args)
    if not ziel:
        log("nichts: keine Stücke gefunden.")
        return 0
    fehler = 0
    for sid in ziel:
        try:
            ergebnis = fassungen_stueck(sid, neu=args.neu)
        except Exception as e:
            ergebnis = Ergebnis("fehler", str(e))
        log(f"{ergebnis.status}: fassungen {sid}: {ergebnis.meldung}")
        fehler += ergebnis.status == "fehler"
    return 1 if fehler and fehler == len(ziel) else 0
