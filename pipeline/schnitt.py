"""Reine Rechnung für den Rohschnitt: Pausenschnitt, Hook vorn, neue Zeitachse.

Kein ffmpeg hier, keine Dateizugriffe außer konfig(). `video.py` führt daraus
die echten ffmpeg-Befehle. Getrennt gehalten, damit die Schnittlogik ohne
Video getestet werden kann (`tests/test_video.py`).

Wortformat: [{"w","s","e"}] (Quellzeit in Sekunden). Ein Segment ist intern
ein Tupel (s, e, von_wort, bis_wort) mit Wortindizes in die volle Wortliste;
nach außen geben wir [s, e]-Listen wie in ARCHITEKTUR.md verlangt.

**Annahme zur Zahl "auf 0,28 s gekürzt" (befund_schnitt.md).** Vorlauf
(0,14 s) und Nachlauf (0,40 s) sind die Ränder, die eine herausgeschnittene
Stelle (Hook-Ende, Stückanfang/-ende) gegen das Nachbarwort bekommt. Eine
interne Pause zwischen zwei Wörtern im selben Stück wird dagegen symmetrisch
auf genau `pause_ziel` (0,28 s) um die Pausenmitte gekürzt: Pausen ab
`pausen_ab` (0,9 s) sind immer länger als 0,28 s, also bleibt immer Luft zu
beiden Wörtern (kein Anschnitt möglich). Diese zwei Regeln zusammen ergeben
für den Normalfall (Pausenschnitt mitten im Stück) fast immer die 0,28 s, und
an den Rändern (wo wirklich etwas fehlt, weil davor/danach geschnitten wurde)
die asymmetrischen 0,14/0,40 s.
"""
from __future__ import annotations

from dataclasses import dataclass

from .kern import konfig


@dataclass(frozen=True)
class Werte:
    pausen_ab: float = 0.9
    pause_ziel: float = 0.28
    max_segment: float = 9.0
    vorlauf: float = 0.14
    nachlauf: float = 0.40
    ausklang_max: float = 0.6
    zoom_stufen: tuple[float, ...] = (1.0, 1.15)
    augenlinie: float = 0.36
    blende_segment: float = 0.12


def werte() -> Werte:
    """[schnitt]-Werte aus konfig/pipeline.toml, mit den Vorbild-Werten als Rückfall."""
    k = konfig("pipeline").get("schnitt", {})
    v = Werte()
    return Werte(
        pausen_ab=k.get("pausen_ab", v.pausen_ab),
        pause_ziel=k.get("pause_ziel", v.pause_ziel),
        max_segment=k.get("max_segment", v.max_segment),
        vorlauf=k.get("vorlauf", v.vorlauf),
        nachlauf=k.get("nachlauf", v.nachlauf),
        ausklang_max=k.get("ausklang_max", v.ausklang_max),
        zoom_stufen=tuple(k.get("zoom_stufen", list(v.zoom_stufen))),
        augenlinie=k.get("augenlinie", v.augenlinie),
        blende_segment=k.get("blende_segment", v.blende_segment),
    )


Segment = tuple[float, float, int, int]  # s, e, von_wort, bis_wort (Indizes in `woerter`)


def _woerter_luecken(woerter: list[dict], von: int, bis: int) -> list[tuple[int, float]]:
    """[(wortindex_vor_der_luecke, luecke_in_s), …] für i in [von, bis)."""
    out = []
    for i in range(von, bis):
        luecke = woerter[i + 1]["s"] - woerter[i]["e"]
        out.append((i, luecke))
    return out


def _groesste_luecke(woerter: list[dict], von: int, bis: int) -> int | None:
    """Wortindex mit der größten Lücke danach, in [von, bis). None wenn nur ein Wort."""
    luecken = _woerter_luecken(woerter, von, bis)
    if not luecken:
        return None
    return max(luecken, key=lambda t: t[1])[0]


def _grob_segmente(woerter: list[dict], von: int, bis: int, pausen_ab: float) -> list[tuple[int, int]]:
    """Wortindex-Bereiche [von, bis] (inklusiv), getrennt an Pausen >= pausen_ab."""
    out = []
    start = von
    for i in range(von, bis):
        if woerter[i + 1]["s"] - woerter[i]["e"] >= pausen_ab:
            out.append((start, i))
            start = i + 1
    out.append((start, bis))
    return out


def _teile_lange_segmente(woerter: list[dict], bereiche: list[tuple[int, int]], max_segment: float
                          ) -> list[tuple[int, int]]:
    """Segmente > max_segment (Wortdauer bis+e - von+s) an der größten inneren Lücke teilen."""
    fertig: list[tuple[int, int]] = []
    offen = list(bereiche)
    while offen:
        von, bis = offen.pop(0)
        dauer = woerter[bis]["e"] - woerter[von]["s"]
        if dauer <= max_segment or von == bis:
            fertig.append((von, bis))
            continue
        schnitt = _groesste_luecke(woerter, von, bis)
        if schnitt is None:
            fertig.append((von, bis))
            continue
        offen.insert(0, (schnitt + 1, bis))
        offen.insert(0, (von, schnitt))
    fertig.sort()
    return fertig


def _kanten_pausenschnitt(woerter: list[dict], bereiche: list[tuple[int, int]], pause_ziel: float
                          ) -> list[Segment]:
    """Zeiten aus Wortindex-Bereichen: Anfang/Ende jedes Segments liegt in der Mitte
    der Nachbarpause minus/plus die halbe Zielpause, außer am äußersten Rand (dort
    bleibt das Wort selbst die Grenze, `hook_vorn`/`raender` legen dort Vor-/Nachlauf an)."""
    segmente: list[Segment] = []
    for idx, (von, bis) in enumerate(bereiche):
        s = woerter[von]["s"]
        e = woerter[bis]["e"]
        if idx > 0:
            voriges_bis = bereiche[idx - 1][1]
            mitte = (woerter[voriges_bis]["e"] + woerter[von]["s"]) / 2
            s = min(woerter[von]["s"], mitte + pause_ziel / 2)
        if idx < len(bereiche) - 1:
            naechstes_von = bereiche[idx + 1][0]
            mitte = (woerter[bis]["e"] + woerter[naechstes_von]["s"]) / 2
            e = max(woerter[bis]["e"], mitte - pause_ziel / 2)
        segmente.append((round(s, 4), round(e, 4), von, bis))
    return segmente


def pausenschnitt(woerter: list[dict], von_wort: int, bis_wort: int, w: Werte | None = None) -> list[Segment]:
    """Segmente (s, e, von_wort, bis_wort) für den Wortbereich [von_wort, bis_wort] (inklusiv).

    Pausen >= pausen_ab trennen, Segmente > max_segment an der größten inneren
    Lücke geteilt, innere Pausen auf pause_ziel gekürzt (siehe Moduldoc).
    """
    w = w or werte()
    if bis_wort < von_wort:
        return []
    grob = _grob_segmente(woerter, von_wort, bis_wort, w.pausen_ab)
    geteilt = _teile_lange_segmente(woerter, grob, w.max_segment)
    return _kanten_pausenschnitt(woerter, geteilt, w.pause_ziel)


def raender(segmente: list[Segment], woerter: list[dict], w: Werte | None = None) -> list[Segment]:
    """Legt Vorlauf vor das erste und Nachlauf hinter das letzte Segment einer Kette,
    ohne ins Wort davor/danach zu schneiden (Wortmitte der Nachbarlücke entscheidet).
    Für Segmentketten, die für sich einen Clip bilden (Hook, Stückanfang/-ende)."""
    if not segmente:
        return segmente
    w = w or werte()
    segmente = list(segmente)
    s0, e0, v0, b0 = segmente[0]
    vor_wort = woerter[v0 - 1] if v0 > 0 else None
    grenze = (vor_wort["e"] + woerter[v0]["s"]) / 2 if vor_wort else 0.0
    segmente[0] = (round(max(grenze, s0 - w.vorlauf), 4), e0, v0, b0)

    sN, eN, vN, bN = segmente[-1]
    nach_wort = woerter[bN + 1] if bN + 1 < len(woerter) else None
    grenze = (woerter[bN]["e"] + nach_wort["s"]) / 2 if nach_wort else eN + w.nachlauf
    segmente[-1] = (sN, round(min(grenze, eN + w.nachlauf), 4), vN, bN)
    return segmente


def hook_vorn(segmente: list[Segment], hook_von_wort: int, hook_bis_wort: int) -> list[Segment]:
    """Stellt die Segmente um, die den Hook-Wortbereich tragen, an den Anfang.

    Segmente, die vollständig im Hook-Bereich liegen, werden zu einer Hook-Kette
    zusammengefasst. Ein Segment, das den Hook nur teilweise trägt, wird an der
    Hook-Grenze aufgeschnitten: der Teil im Hook wandert vor, der Rest bleibt an
    seiner Stelle (ohne den Hook-Satz noch einmal zu zeigen, wie im Auftrag
    verlangt: "Rest ohne den Hook-Satz").
    """
    hook: list[Segment] = []
    rest: list[Segment] = []
    for s, e, von, bis in segmente:
        ueberlappt = von <= hook_bis_wort and bis >= hook_von_wort
        if not ueberlappt:
            rest.append((s, e, von, bis))
            continue
        im_hook = max(von, hook_von_wort), min(bis, hook_bis_wort)
        anteil = (im_hook[1] - im_hook[0] + 1) / (bis - von + 1)
        if von >= hook_von_wort and bis <= hook_bis_wort:
            hook.append((s, e, von, bis))
        elif anteil >= 0.5:
            hook.append((s, e, von, bis))
        else:
            rest.append((s, e, von, bis))
    if not hook:
        return segmente
    return hook + rest


def neue_zeitachse(woerter: list[dict], segmente: list[Segment]) -> dict:
    """{"segmente": [[s,e],…] (Quellzeit), "woerter": [{"w","s","e"}] (neue Zeit), "dauer_s"}."""
    out_segmente = [[s, e] for s, e, _, _ in segmente]
    out_woerter: list[dict] = []
    versatz = 0.0
    for s, e, von, bis in segmente:
        for i in range(von, bis + 1):
            w = woerter[i]
            if w["s"] < s or w["e"] > e:
                continue  # Wort lag außerhalb des Segmentschnitts (z. B. nach Hook-Trennung)
            out_woerter.append({
                "w": w["w"],
                "s": round(versatz + (w["s"] - s), 4),
                "e": round(versatz + (w["e"] - s), 4),
            })
        versatz += e - s
    return {"segmente": out_segmente, "woerter": out_woerter, "dauer_s": round(versatz, 4)}


def zoom_takt(anzahl: int, w: Werte | None = None) -> list[float]:
    """Zoomstufe je Segment, abwechselnd aus w.zoom_stufen."""
    w = w or werte()
    stufen = w.zoom_stufen or (1.0,)
    return [stufen[i % len(stufen)] for i in range(anzahl)]


def zoom_crop_filter(zoom: float, breite: int = 1080, hoehe: int = 1920, augenlinie: float = 0.36) -> str:
    """ffmpeg-Filterfragment: zoomt, hält dabei die Augenlinie (Anteil der Höhe) fest.

    Kein `zoompan` (im Auftrag verboten, hier ohnehin unnötig: der Zoom ist je
    Segment fest, keine Bewegung innerhalb des Segments). Reine scale+crop-Kette.
    """
    if abs(zoom - 1.0) < 1e-6:
        return ""
    x = round(breite * (zoom - 1) / 2, 3)
    y = round(hoehe * augenlinie * (zoom - 1), 3)
    return f"scale={breite*zoom:.2f}:{hoehe*zoom:.2f},crop={breite}:{hoehe}:{x}:{y},"


def ausklang(pegel: list[tuple[float, float]], wortende: float, max_dauer: float) -> float:
    """Sucht ab `wortende` die erste dauerhaft leise Stelle in einer Pegelkurve
    `[(zeit, dbfs), …]` (z. B. aus `ffmpeg … astats` oder `volumedetect` je
    Fenster). Gibt die Zugabe in Sekunden zurück, höchstens `max_dauer`.

    Warum gemessen statt fest (befund_schnitt.md, 18.09.2026): eine feste
    Zugabe von 0,55 s hat beim Vorbild den nächsten Satz mit hereingeholt, weil
    Whisper das Wortende oft auf den Nachhallbeginn legt statt aufs Verstummen.
    """
    schwelle = -40.0  # dBFS, dauerhaft leise
    kandidat = max_dauer
    for zeit, db in pegel:
        if zeit < wortende:
            continue
        if db <= schwelle:
            kandidat = min(max_dauer, round(zeit - wortende, 4))
            break
    return max(0.0, kandidat)
