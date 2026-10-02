import os
import time
from pathlib import Path

from pipeline import hook, rohmaterial, transkript, zerlegen


def test_eingang_akzeptiert_grosse_endung(repo):
    (repo / "eingang" / "Mein Video.MOV").write_bytes(b"x")
    assert rohmaterial.eingang()[0].status == "ok"
    assert (repo / "arbeit" / "mein-video" / "quelle.mov").exists()


def test_weiterer_eingang_uebernimmt_erst_nach_zweiter_stabiler_beobachtung(repo, tmp_path, monkeypatch):
    quelle = tmp_path / "drive"
    quelle.mkdir()
    video = quelle / "Mein Video.MOV"
    video.write_bytes(b"video")
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text().replace("weitere_ordner = []", f'weitere_ordner = ["{quelle}"]'))

    zeit = [1_000.0]
    monkeypatch.setattr(rohmaterial.time, "time", lambda: zeit[0])
    assert video.exists()
    rohmaterial.eingang()
    zeit[0] += 180
    ergebnisse = rohmaterial.eingang()

    assert any(e.status == "ok" for e in ergebnisse)
    assert (quelle / "übernommen" / "Mein Video.MOV").read_bytes() == b"video"
    assert not video.exists()
    assert (repo / "arbeit" / "mein-video" / "quelle.mov").exists()


def test_weiterer_eingang_laesst_zu_junges_video_liegen(repo, tmp_path):
    quelle = tmp_path / "drive"
    quelle.mkdir()
    video = quelle / "neu.mp4"
    video.write_bytes(b"video")
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text().replace("weitere_ordner = []", f'weitere_ordner = ["{quelle}"]'))

    rohmaterial.eingang()

    assert video.exists()
    assert not (quelle / "übernommen").exists()


def test_weiterer_eingang_beginnt_bei_geaenderter_groesse_von_vorn(repo, tmp_path, monkeypatch):
    quelle = tmp_path / "drive"
    quelle.mkdir()
    video = quelle / "neu.mp4"
    video.write_bytes(b"video")
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text().replace("weitere_ordner = []", f'weitere_ordner = ["{quelle}"]'))
    zeit = [1_000.0]
    monkeypatch.setattr(rohmaterial.time, "time", lambda: zeit[0])
    rohmaterial.eingang()
    zeit[0] += 181
    video.write_bytes(b"video ist weiter gewachsen")
    rohmaterial.eingang()
    assert video.exists()
    zeit[0] += 181
    rohmaterial.eingang()
    assert (quelle / "übernommen" / "neu.mp4").exists()


def test_weiterer_eingang_verwirft_falsche_kopiegroesse(repo, tmp_path, monkeypatch):
    quelle = tmp_path / "drive"
    quelle.mkdir()
    video = quelle / "alt.mp4"
    video.write_bytes(b"video")
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text().replace("weitere_ordner = []", f'weitere_ordner = ["{quelle}"]'))

    def zu_klein(_: str, ziel: str):
        Path(ziel).write_bytes(b"x")

    zeit = [1_000.0]
    monkeypatch.setattr(rohmaterial.time, "time", lambda: zeit[0])
    rohmaterial.eingang()
    zeit[0] += 180
    monkeypatch.setattr(rohmaterial.shutil, "copyfile", zu_klein)
    ergebnisse = rohmaterial.eingang()

    assert any(e.status == "befund" for e in ergebnisse)
    assert video.exists()
    assert not (quelle / "übernommen").exists()
    assert not list((repo / "eingang").glob("*.teil"))


def test_saetze_an_pause_und_zeichen():
    w = [{"w":"Hallo","s":0,"e":.2},{"w":"Welt","s":.3,"e":.5},{"w":"Nächster","s":1.0,"e":1.2},{"w":"Satz.","s":1.3,"e":1.5}]
    assert [x["text"] for x in transkript.saetze(w)] == ["Hallo Welt", "Nächster Satz."]


def test_ueberlappung_wird_auf_satzkante_bereinigt():
    s=[{"nr":i,"s":i*10,"e":i*10+8,"text":"Satz."} for i in range(5)]
    r=zerlegen.bereinige([{"von_satz":0,"bis_satz":2},{"von_satz":2,"bis_satz":4}],s,1,200)
    assert r == [{"von_satz":0,"bis_satz":2},{"von_satz":3,"bis_satz":4}]


def test_kurzes_stueck_wird_zusammengelegt():
    s=[{"nr":0,"s":0,"e":4,"text":"Kurz."},{"nr":1,"s":5,"e":45,"text":"Lang."}]
    assert zerlegen.bereinige([{"von_satz":0,"bis_satz":0},{"von_satz":1,"bis_satz":1}],s,30,200) == [{"von_satz":0,"bis_satz":1}]


def test_hook_schwellen():
    assert hook.vorziehen(7,5)
    assert hook.vorziehen(6,2)
    assert not hook.vorziehen(6,4)


def test_satzzeichen_trotz_zusammengezogenem_wort():
    block = [{"w": x, "s": 0, "e": 0} for x in "ich habe die e mail strecke überarbeitet also egal was du machst".split()]
    neue = "Ich habe die E-Mail-Strecke überarbeitet. Also egal, was du machst.".split()
    assert transkript.zeichen_uebernehmen(block, neue) == 3
    assert [w["w"] for w in block][3:9] == ["e", "mail", "strecke", "überarbeitet.", "also", "egal,"]


def test_satzzeichen_verworfen_wenn_modell_umschreibt():
    block = [{"w": x, "s": 0, "e": 0} for x in "das ist ein ganz anderer satz".split()]
    assert transkript.zeichen_uebernehmen(block, "Völlig neuer Text hier.".split()) == 0
    assert all("." not in w["w"] for w in block)


def test_fenster_schneiden_in_der_laengsten_pause():
    w = [{"w": "a", "s": i, "e": i + .8} for i in range(40)]
    w[15]["e"] = 15.2   # längste Pause zwischen 15,2 und 16,0
    assert round(transkript.schnitte(w, 40.0)[0], 2) == 15.6
