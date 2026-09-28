"""Tests für Team B: Rohschnitt und Fassungen je Plattform.

Rein rechnerische Tests (schnitt.py, ebenen.py-Zeilenbildung) laufen ohne
ffmpeg und ohne Modell. `test_ende_zu_ende` (markiert `langsam`) braucht ein
echtes Video und ffmpeg, läuft nur mit `-m langsam`.
"""
from __future__ import annotations

import json

import pytest
from PIL import Image

from pipeline import ebenen, schnitt, titelband, video


def _woerter(*paare: tuple[str, float, float]) -> list[dict]:
    return [{"w": w, "s": s, "e": e} for w, s, e in paare]


# ------------------------------------------------------------- schnitt.py ---

def test_pausenschnitt_trennt_an_grosser_pause():
    woerter = _woerter(
        ("Eins", 0.0, 0.4), ("zwei", 0.5, 0.9), ("drei", 1.0, 1.4),
        ("Vier", 3.0, 3.4), ("fünf", 3.5, 3.9),  # Pause 1.6s >= 0.9s vor "Vier"
    )
    w = schnitt.Werte()
    segmente = schnitt.pausenschnitt(woerter, 0, 4, w)
    assert len(segmente) == 2
    # kein Wort angeschnitten: jedes Wort liegt innerhalb eines Segments
    for wort in woerter:
        mitte = (wort["s"] + wort["e"]) / 2
        assert any(s <= mitte <= e for s, e, _, _ in segmente), wort


def test_pausenschnitt_kuerzt_pause_auf_pause_ziel():
    woerter = _woerter(("A", 0.0, 0.5), ("B", 3.0, 3.5))
    w = schnitt.Werte(pause_ziel=0.28, pausen_ab=0.9)
    segmente = schnitt.pausenschnitt(woerter, 0, 1, w)
    assert len(segmente) == 2
    luecke = segmente[1][0] - segmente[0][1]
    assert luecke == pytest.approx(0.28, abs=0.01)


def test_pausenschnitt_ohne_pause_bleibt_ein_segment():
    woerter = _woerter(("A", 0.0, 0.3), ("B", 0.35, 0.6), ("C", 0.62, 1.0))
    segmente = schnitt.pausenschnitt(woerter, 0, 2)
    assert len(segmente) == 1
    assert segmente[0][0] == 0.0 and segmente[0][1] == 1.0


def test_segment_ueber_max_laenge_wird_geteilt():
    # 12 Wörter über 12s, Pausen alle < 0.9s außer einer großen Lücke bei Wort 6
    zeiten = []
    t = 0.0
    for i in range(12):
        zeiten.append((f"w{i}", t, t + 0.3))
        t += 0.4 if i != 5 else 1.5
    woerter = _woerter(*zeiten)
    w = schnitt.Werte(max_segment=9.0, pausen_ab=0.9)
    segmente = schnitt.pausenschnitt(woerter, 0, 11, w)
    assert len(segmente) >= 2
    for s, e, _, _ in segmente:
        assert e - s <= 9.0 + 0.01


def test_raender_legt_vorlauf_und_nachlauf_ohne_nachbarwort_anzuschneiden():
    woerter = _woerter(("vor", 0.0, 0.3), ("A", 1.0, 1.4), ("B", 1.5, 1.8), ("nach", 2.5, 2.8))
    segmente = [(1.0, 1.8, 1, 2)]
    w = schnitt.Werte(vorlauf=0.14, nachlauf=0.40)
    aus = schnitt.raender(segmente, woerter, w)
    s, e, _, _ = aus[0]
    assert s < 1.0 and s > woerter[0]["e"]  # Vorlauf da, aber nicht ins Wort "vor"
    assert e > 1.8 and e < woerter[3]["s"]  # Nachlauf da, aber nicht ins Wort "nach"


def test_hook_vorn_stellt_hook_segment_nach_vorn():
    segmente = [(0.0, 1.0, 0, 2), (1.2, 2.0, 3, 5), (2.2, 3.0, 6, 8)]
    aus = schnitt.hook_vorn(segmente, 3, 5)
    assert aus[0][2:] == (3, 5)
    assert len(aus) == 3
    # der Rest bleibt ohne den Hook, kein Segment kommt doppelt vor
    reste = [(v, b) for _, _, v, b in aus[1:]]
    assert (3, 5) not in reste


def test_hook_vorn_ohne_treffer_laesst_reihenfolge_unveraendert():
    segmente = [(0.0, 1.0, 0, 2), (1.2, 2.0, 3, 5)]
    assert schnitt.hook_vorn(segmente, 50, 60) == segmente


def test_neue_zeitachse_wortzeiten_und_dauer():
    woerter = _woerter(("A", 0.0, 0.3), ("B", 1.5, 1.8))
    segmente = [(0.0, 0.5, 0, 0), (1.4, 2.0, 1, 1)]
    achse = schnitt.neue_zeitachse(woerter, segmente)
    assert achse["dauer_s"] == pytest.approx(0.5 + 0.6, abs=1e-6)
    assert achse["woerter"][0]["w"] == "A"
    assert achse["woerter"][0]["s"] == pytest.approx(0.0)
    # zweites Wort beginnt nach dem Versatz des ersten Segments (0.5)
    assert achse["woerter"][1]["s"] == pytest.approx(0.5 + (1.5 - 1.4))


def test_zoom_takt_wechselt_abwechselnd():
    w = schnitt.Werte(zoom_stufen=(1.0, 1.15))
    assert schnitt.zoom_takt(5, w) == [1.0, 1.15, 1.0, 1.15, 1.0]


def test_zoom_crop_filter_identitaet_bei_faktor_1():
    assert schnitt.zoom_crop_filter(1.0) == ""
    assert "crop=1080:1920" in schnitt.zoom_crop_filter(1.15)


def test_ausklang_findet_leise_stelle_und_deckelt():
    pegel = [(0.0, -5.0), (0.1, -10.0), (0.3, -42.0), (0.5, -45.0)]
    assert schnitt.ausklang(pegel, wortende=0.0, max_dauer=0.6) == pytest.approx(0.3)
    pegel_laut = [(t / 10, -5.0) for t in range(20)]
    assert schnitt.ausklang(pegel_laut, wortende=0.0, max_dauer=0.6) == 0.6


# -------------------------------------------------------------- ebenen.py ---

def test_karaoke_zeilenbildung_haelt_wort_und_zeichengrenze():
    woerter = _woerter(*[(f"wort{i}", i * 0.5, i * 0.5 + 0.3) for i in range(10)])
    zeilen = ebenen._zeilen_woerter(woerter, max_zeichen=20, max_worte=4)
    for zeile in zeilen:
        assert len(zeile) <= 4
        text = " ".join(w["w"] for w in zeile)
        assert len(text) <= 20 or len(zeile) == 1


def test_karaoke_spur_deckt_die_ganze_dauer_luekenlos_ab(repo):
    woerter = _woerter(("Heute", 0.2, 0.6), ("reden", 0.7, 1.1), ("wir", 1.2, 1.4))
    spur = ebenen.karaoke_spur(woerter, dauer=2.0, unten=300)
    assert spur[0][0] == 0.0
    assert spur[-1][1] == 2.0
    for i in range(1, len(spur)):
        assert spur[i][0] == pytest.approx(spur[i - 1][1], abs=1e-6)


def test_ebenen_schreiben_liste_ist_lueckenlos_und_stimmt_in_der_summe(repo):
    woerter = _woerter(("Eins", 0.1, 0.4), ("zwei", 0.5, 0.8))
    dauer = 3.0
    spur1 = ebenen.karaoke_spur(woerter, dauer, unten=300)
    spur2 = ebenen.titel_spur("Kurzer Titel", dauer, oben=270)
    ordner = repo / "arbeit" / "_test_ebenen"
    liste = ebenen.schreiben(ordner, dauer, spur1, spur2)
    zeilen = liste.read_text().splitlines()
    dauern = [float(z.split()[1]) for z in zeilen if z.startswith("duration")]
    assert sum(dauern) == pytest.approx(dauer, abs=0.06)
    assert all(d >= 0 for d in dauern)


def test_wortmarke_spur_deckt_gesamte_dauer_ab():
    spur = ebenen.wortmarke_spur("Meine Marke", dauer=5.0, unten=300, rechts=70)
    assert spur == [(0.0, 5.0, spur[0][2])]
    assert spur[0][2] is not None


def test_kacheln_spur_verwirft_kachel_vor_titelende():
    kacheln = [{"text": "Zu früh", "start": 0.5}, {"text": "Passt", "start": 6.0}]
    spur = ebenen.kacheln_spur(kacheln, dauer=10.0, titel_bis=4.8)
    texte_zeiten = [s for s, e, img in spur if img is not None]
    assert all(s >= 4.8 + 0.25 - 1e-6 for s in texte_zeiten)


def test_schlusskarte_bild_hat_zielgroesse():
    frame = Image.new("RGB", (1080, 1920), "white")
    bild = ebenen.schlusskarte_bild(frame, "Teil 2: Der nächste Schritt")
    assert bild.size == (1080, 1920)
    assert bild.mode == "RGB"


# ------------------------------------------------------------ titelband.py --

def test_titelband_passung_ok_bei_kurzem_text(repo):
    p = titelband.passung("Kurzer Titel")
    assert p["status"] == "ok"
    assert p["grad"] == titelband.GRAD_STANDARD


def test_titelband_passung_meldet_pixelbefund_bei_zu_langem_text(repo):
    lang = " ".join(["Wortwortwortwortwort"] * 20)
    p = titelband.passung(lang)
    assert p["status"] == "befund"
    assert "px" in p["meldung"] or "Grad" in p["meldung"]


def test_titelband_bild_hat_feste_masse(repo):
    p = titelband.passung("Zwei Zeilen\ngehen auch")
    bild = titelband.bild(p["zeilen"], p["grad"])
    assert bild.size == (titelband.BREITE, titelband.HOEHE)


# -------------------------------------------------------------- video.py ---

def test_schluss_text_mehrteiler_zeigt_naechsten_titel(repo):
    take = repo / "arbeit" / "beispiel"
    (take / "stuecke" / "02").mkdir(parents=True)
    (take / "stuecke" / "02" / "rezept.json").write_text(
        json.dumps({"titel": "Der nächste Teil\nmit Zeile 2"}), encoding="utf-8")
    rezept = {"nr": 1, "von_stuecken": 3, "schluss": None}
    text = video._schluss_text(rezept, "beispiel")
    assert text == "Teil 2: Der nächste Teil"


def test_schluss_text_nimmt_rezeptfeld_wenn_gesetzt():
    rezept = {"nr": 1, "von_stuecken": 1, "schluss": "Bis zum nächsten Mal."}
    assert video._schluss_text(rezept, "irrelevant") == "Bis zum nächsten Mal."


def test_neue_zeit_bildet_quellzeit_auf_geschnittene_zeit_ab():
    segmente = [[0.0, 1.0], [2.0, 3.0]]
    assert video._neue_zeit(0.5, segmente) == pytest.approx(0.5)
    assert video._neue_zeit(2.5, segmente) == pytest.approx(1.5)
    assert video._neue_zeit(1.5, segmente) is None  # herausgeschnitten


def test_ziel_stuecke_loest_take_namen_auf(repo):
    take = repo / "arbeit" / "beispiel"
    take.mkdir(parents=True, exist_ok=True)
    (take / "take.json").write_text("{}", encoding="utf-8")
    for nr in ("01", "02"):
        d = take / "stuecke" / nr
        d.mkdir(parents=True)
        (d / "rezept.json").write_text("{}", encoding="utf-8")
    import argparse
    args = argparse.Namespace(ziel=["beispiel"])
    assert set(video._ziel_stuecke(args)) == {"beispiel-01", "beispiel-02"}


# ------------------------------------------------------------ Ende-zu-Ende --

@pytest.mark.langsam
def test_ende_zu_ende(repo, monkeypatch):
    """Baut ein Stück aus einem winzigen erzeugten Testvideo durch bauen+fassungen."""
    import subprocess

    take = repo / "arbeit" / "beispiel"
    take.mkdir(parents=True, exist_ok=True)
    quelle = take / "quelle.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:d=6:r=30",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
        "-c:v", "libx264", "-c:a", "aac", str(quelle),
    ], check=True, capture_output=True)

    woerter = _woerter(*[(f"wort{i}", i * 0.5, i * 0.5 + 0.35) for i in range(10)])
    (take / "woerter.json").write_text(json.dumps(woerter), encoding="utf-8")
    saetze = [{"nr": 0, "von_wort": 0, "bis_wort": 4, "s": 0.0, "e": woerter[4]["e"],
               "text": "Satz eins."},
              {"nr": 1, "von_wort": 5, "bis_wort": 9, "s": woerter[5]["s"], "e": woerter[9]["e"],
               "text": "Satz zwei."}]
    (take / "saetze.json").write_text(json.dumps(saetze), encoding="utf-8")

    stueck_ordner = take / "stuecke" / "01"
    stueck_ordner.mkdir(parents=True)
    rezept = {"id": "beispiel-01", "take": "beispiel", "nr": 1, "von_stuecken": 1,
              "von_satz": 0, "bis_satz": 1, "s": 0.0, "e": woerter[-1]["e"],
              "titel": "Ein Testtitel", "aussage": "Testaussage", "hook": None,
              "stil": {"reel": "klar"}, "schluss": "Testschluss", "status": "zerlegt", "befunde": []}
    (stueck_ordner / "rezept.json").write_text(json.dumps(rezept), encoding="utf-8")

    ergebnis = video.bauen_stueck("beispiel-01")
    assert ergebnis.gut, ergebnis.meldung
    ergebnis2 = video.fassungen_stueck("beispiel-01")
    assert ergebnis2.gut, ergebnis2.meldung
    ausgabe = repo / "ausgabe" / "beispiel-01"
    assert (ausgabe / "instagram.mp4").exists()
    assert (ausgabe / "tiktok.mp4").exists()
    assert (ausgabe / "cover.jpg").exists()
