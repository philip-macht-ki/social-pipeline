"""Fertige Videos werden als normale Stücke in die Planung aufgenommen."""
from __future__ import annotations

import argparse

from pipeline import aufnehmen, plan
from pipeline.kern import lesen


def test_name_ist_frei_und_wird_nicht_ueberschrieben(repo):
    (repo / "ausgabe" / "U01").mkdir()
    assert aufnehmen._freier_name("umbau") == "U02"
    quelle = repo / "clip.mp4"
    quelle.write_bytes(b"x")
    ergebnis = aufnehmen.aufnehmen(quelle, "U01", "umbau", "Titel", "Beschreibung")
    assert ergebnis.status == "fehler"
    assert "--neu" in ergebnis.meldung


def test_aufnahme_randet_erganzt_stille_spur_und_plant(repo, monkeypatch):
    quelle = repo / "quer.mp4"
    quelle.write_bytes(b"x")
    befehle = []

    def normalisieren(eingang, ziel, hat_ton):
        befehle.append((eingang, ziel, hat_ton))
        ziel.write_bytes(b"video")

    monkeypatch.setattr(aufnehmen, "_normalisieren", normalisieren)
    monkeypatch.setattr(aufnehmen, "_hat_ton", lambda _: False)
    monkeypatch.setattr(aufnehmen, "dauer", lambda _: 30.0)
    monkeypatch.setattr(aufnehmen.titelband, "cover", lambda *a: aufnehmen.Ergebnis("ok", ""))
    monkeypatch.setattr(aufnehmen.texte, "_machen", lambda _: aufnehmen.Ergebnis("ok", ""))
    ergebnis = aufnehmen.aufnehmen(quelle, None, "umbau", "Querformat", "Eine Beschreibung")
    assert ergebnis.status == "ok"
    assert befehle[0][2] is False
    assert (repo / "ausgabe" / "U01" / "tiktok.mp4").read_bytes() == b"video"
    assert (repo / "ausgabe" / "U01" / "youtube.mp4").exists()
    assert lesen(repo / "ausgabe" / "U01" / "stueck.json")["stil"] == "umbau"
    plan.befehl_planen(argparse.Namespace(tage=2))
    assert any(e["quelle"] == "U01" for e in lesen(repo / "arbeit" / "plan.json")["eintraege"])


def test_aufnahme_ohne_sprache_und_beschreibung_plant_nicht(repo, monkeypatch):
    quelle = repo / "still.mp4"
    quelle.write_bytes(b"x")
    monkeypatch.setattr(aufnehmen, "_hat_ton", lambda _: False)
    monkeypatch.setattr(aufnehmen, "_normalisieren", lambda _, ziel, __: ziel.write_bytes(b"video"))
    monkeypatch.setattr(aufnehmen, "dauer", lambda _: 30.0)
    ergebnis = aufnehmen.aufnehmen(quelle, "U01", "umbau", None, None)
    assert ergebnis.status == "befund"
    assert "Beschreibung fehlt" in ergebnis.meldung
    assert not (repo / "arbeit" / "U01" / "stuecke" / "01" / "rezept.json").exists()


def test_aufnahme_transkribiert_und_laesst_youtube_bei_180_sekunden_weg(repo, monkeypatch):
    quelle = repo / "sprache.mp4"
    quelle.write_bytes(b"x")
    monkeypatch.setattr(aufnehmen, "_hat_ton", lambda _: True)
    monkeypatch.setattr(aufnehmen, "_normalisieren", lambda _, ziel, __: ziel.write_bytes(b"video"))
    monkeypatch.setattr(aufnehmen, "dauer", lambda _: 180.0)
    monkeypatch.setattr(aufnehmen.titelband, "cover", lambda *a: aufnehmen.Ergebnis("ok", ""))
    monkeypatch.setattr(aufnehmen.texte, "_machen", lambda _: aufnehmen.Ergebnis("ok", ""))

    def whisper(arbeit, neu):
        (arbeit / "woerter.json").write_text('[{"w":"Hallo.","s":0,"e":1}]')
        (arbeit / "saetze.json").write_text('[{"nr":0,"text":"Hallo."}]')
        (arbeit / "transkript.txt").write_text("Hallo.\n")
        return aufnehmen.Ergebnis("ok", "transkribiert")

    monkeypatch.setattr(aufnehmen.transkript, "verarbeite", whisper)
    monkeypatch.setattr(aufnehmen, "_inhalt", lambda *a: ("Titel", "Aussage"))
    assert aufnehmen.aufnehmen(quelle, "U01", "umbau", None, None).status == "befund"
    assert not (repo / "ausgabe" / "U01" / "youtube.mp4").exists()
    assert lesen(repo / "arbeit" / "U01" / "woerter.json")[0]["w"] == "Hallo."


def test_querformat_sitzt_mittig_mit_rand(tmp_path):
    import subprocess
    from PIL import Image

    quelle = tmp_path / "quer.mp4"
    ziel = tmp_path / "hoch.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=red:size=1920x1080:rate=30", "-t", "1", str(quelle)], check=True)
    aufnehmen._normalisieren(quelle, ziel, hat_ton=False)
    bild = tmp_path / "bild.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ziel), "-frames:v", "1", str(bild)],
                   check=True)
    im = Image.open(bild).convert("RGB")
    assert im.size == (1080, 1920)
    oben, mitte, unten = im.getpixel((540, 100)), im.getpixel((540, 960)), im.getpixel((540, 1820))
    assert max(oben) < 30 and max(unten) < 30
    assert mitte[0] > 180 and mitte[1] < 80
