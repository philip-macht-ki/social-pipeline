"""Zusatzstücke ohne Modell und ohne echten Videoschnitt prüfen."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from pipeline import kurzstuecke, plan
from pipeline.schrift import breite, hoehe, schrift


def _take(repo, name="take"):
    take = repo / "arbeit" / name
    take.mkdir(parents=True)
    (take / "take.json").write_text(json.dumps({"id": name}))
    (take / "transkript.txt").write_text("Früher war alles schwer. Heute ist es klar.")
    ausgabe = repo / "ausgabe" / f"{name}-01"
    ausgabe.mkdir()
    (ausgabe / "stueck.json").write_text(json.dumps({"id": f"{name}-01", "status": "fertig"}))
    return take


def test_alltag_auswahl_ist_je_take_stabil(repo):
    ordner = repo / "medien" / "alltag"
    ordner.mkdir(parents=True)
    for name in ("A.MP4", "b.mov", "c.mp4"):
        (ordner / name).write_bytes(b"x")
    assert kurzstuecke._alltag("gleich") == kurzstuecke._alltag("gleich")


def test_lesereel_prueft_laenge_absatz_und_verbotene_zeichen():
    gut = {"brief": "Lieber Algorithmus\n\nFür Selbstständige ist Klarheit wichtig.\n\n"
                    "Wir gehören zusammen.",
           "caption": "Was nimmst du daraus mit?"}
    assert kurzstuecke.pruefe_lesereel(gut) is None
    assert kurzstuecke.pruefe_lesereel({**gut, "brief": gut["brief"] + " \u2014 nie"})
    assert kurzstuecke.pruefe_lesereel({**gut, "brief": "Hallo\n\na\n\nb"})


def test_uebermalt_prueft_grenzen_und_passt_nicht():
    gut = {"vorher": "Früher", "falsch": "schwer", "richtig": "klar", "nachsatz": "Das wurde gesagt.",
           "caption": "Was davon bleibt bei dir hängen?"}
    assert kurzstuecke.pruefe_uebermalt(gut) is None
    assert kurzstuecke.pruefe_uebermalt({**gut, "falsch": "x" * 21})
    assert "Verneinung" in kurzstuecke.pruefe_uebermalt({**gut, "vorher": "Das Problem ist nicht"})
    assert kurzstuecke.pruefe_uebermalt({"passt_nicht": "Kein Gegensatz."}) is None


def test_lesereel_auftrag_enthaelt_titel_und_aussagen_aus_rezepten(repo, monkeypatch):
    take = _take(repo)
    for nummer, titel, aussage in (("01", "Weniger Reibung", "Zwanzig Handgriffe bremsen."),
                                    ("02", "Klarer Ablauf", "Ein guter Ablauf spart Zeit.")):
        rezept = take / "stuecke" / nummer / "rezept.json"
        rezept.parent.mkdir(parents=True)
        rezept.write_text(json.dumps({"titel": titel, "aussage": aussage}))
    auftraege = []

    def urteil_mock(auftrag, **werte):
        auftraege.append((auftrag, werte))
        return {"brief": "Lieber Algorithmus\n\nEin klarer Ablauf hilft.\n\nWir gehören zusammen.",
                "caption": "Welcher Ablauf hilft dir heute?"}

    monkeypatch.setattr(kurzstuecke, "frage", urteil_mock)
    monkeypatch.setattr(kurzstuecke, "_lese_video", lambda *args: None)
    monkeypatch.setattr(kurzstuecke, "_manifest", lambda *args: None)
    assert kurzstuecke._bauen_lese("take").status == "ok"
    assert "Weniger Reibung" in auftraege[0][0]
    assert "Zwanzig Handgriffe bremsen." in auftraege[0][0]
    assert "Klarer Ablauf" in auftraege[0][0]
    assert auftraege[0][1]["pruefe"] is kurzstuecke.pruefe_lesereel


def test_uebermalt_auftrag_nachbessert_verneinung_und_fordert_caption(repo, monkeypatch):
    _take(repo)
    auftraege = []
    antwort = {"vorher": "Das Problem ist", "falsch": "der Inhalt", "richtig": "die Handgriffe",
               "nachsatz": "Sie machen alles schwer.", "caption": "Welche Handgriffe streichst du?"}

    def urteil_mock(auftrag, **werte):
        auftraege.append((auftrag, werte))
        return antwort

    monkeypatch.setattr(kurzstuecke, "frage", urteil_mock)
    monkeypatch.setattr(kurzstuecke, "_uebermalt_video", lambda *args: None)
    monkeypatch.setattr(kurzstuecke, "_manifest", lambda *args: None)
    assert kurzstuecke._bauen_uebermalt("take").status == "ok"
    mangel = auftraege[0][1]["pruefe"]({**antwort, "vorher": "Das Problem ist nicht"})
    assert mangel == "vorher darf keine Verneinung enthalten."
    assert "vorher, richtig und nachsatz" in auftraege[0][0]
    assert '"caption":"…?"' in auftraege[0][0]


def test_uebermalt_setzt_grosse_einzelzeilen_und_handschrift_mit_abstand(repo, tmp_path):
    daten = {
        "vorher": "Das Problem liegt bei",
        "falsch": "Zu viele Schritte.",
        "richtig": "Klarheit.",
        "nachsatz": "Dann bleibt nur, was du gut kannst.",
        "caption": "Was bleibt dann für dich übrig?",
    }
    layout = kurzstuecke._uebermalt_layout(daten)
    font = schrift("text_normal", layout["koerper"])
    assert layout["block_breite"] == 864
    assert max(breite(daten[feld], font) for feld in ("vorher", "falsch", "nachsatz")) >= 692
    assert all(breite(daten[feld], font) <= layout["block_breite"] for feld in ("vorher", "falsch", "nachsatz"))
    hand = schrift("hand", layout["hand"])
    vorher_unten = layout["zeilen"]["vorher"] + hoehe(font)
    assert layout["richtig_y"] > vorher_unten
    assert layout["richtig_y"] + hoehe(hand) < layout["zeilen"]["falsch"]
    wege = kurzstuecke._uebermalt_bilder(daten, tmp_path)
    assert all(Image.open(weg).size == (1080, 1920) for weg in wege)


def test_lesereel_rueckfall_verdunkelt_und_zeichnet_weich(repo, monkeypatch, tmp_path):
    quelle = repo / "arbeit" / "take" / "quelle.mov"
    quelle.parent.mkdir()
    quelle.write_bytes(b"x")
    ebene = tmp_path / "lese-text.png"
    monkeypatch.setattr(kurzstuecke, "_png_text", lambda *args, **kwargs: Image.new("RGBA", (1080, 1920)))
    befehle = []
    monkeypatch.setattr(kurzstuecke, "lauf", lambda cmd: befehle.append(cmd))
    kurzstuecke._lese_video("take", "Lieber Algorithmus", tmp_path / "instagram.mp4")
    graph = befehle[0][befehle[0].index("-filter_complex") + 1]
    assert "gblur=sigma=18" in graph
    assert "brightness=-0.42" in graph
    assert ebene.exists()


def test_uebermalt_video_verwendet_absolute_bildwege(repo, monkeypatch, tmp_path):
    daten = {"vorher": "Früher", "falsch": "schwer", "richtig": "klar", "nachsatz": "Das wurde gesagt.",
             "caption": "Was davon bleibt bei dir hängen?"}

    class TemporaererOrdner:
        def __enter__(self):
            ordner = tmp_path / "concat"
            ordner.mkdir()
            return str(ordner)

        def __exit__(self, *args):
            return False

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(kurzstuecke.tempfile, "TemporaryDirectory", TemporaererOrdner)
    befehle = []
    monkeypatch.setattr(kurzstuecke, "lauf", lambda cmd: befehle.append(cmd))
    kurzstuecke._uebermalt_video(daten, tmp_path / "instagram.mp4")
    liste = Path(befehle[0][befehle[0].index("-i") + 1])
    assert all(str(tmp_path) in zeile for zeile in liste.read_text().splitlines() if zeile.startswith("file"))


def test_textdateien_nimmt_caption_und_wiederholt_den_satz_nicht(repo):
    texte = kurzstuecke._textdateien(
        "take", "Die Handgriffe machen den Unterschied. Was würdest du streichen?",
        "Das Problem sind die Handgriffe.",
    )
    instagram = texte["instagram"]["caption"]
    assert "Die Handgriffe machen den Unterschied." in instagram
    assert instagram.count("Die Handgriffe machen den Unterschied.") == 1
    assert "Was würdest du streichen?" in instagram


def test_passt_nicht_baut_keine_datei_und_setzt_merker(repo, monkeypatch):
    _take(repo)
    monkeypatch.setattr(kurzstuecke, "frage", lambda *a, **k: {"passt_nicht": "Kein Gegensatz."})
    kurzstuecke.befehl(argparse.Namespace(ziel=["take"], neu=False))
    assert not (repo / "ausgabe/take-uebermalt").exists()
    daten = json.loads((repo / "arbeit/take/take.json").read_text())
    assert daten["kurzstuecke"]["uebermalt"] == "nichts"


def test_merker_verhindert_doppelbau(repo, monkeypatch):
    _take(repo)
    gebaut = []
    monkeypatch.setattr(
        kurzstuecke, "_bauen_lese", lambda take: gebaut.append(take) or kurzstuecke.Ergebnis("ok")
    )
    monkeypatch.setattr(kurzstuecke, "_bauen_uebermalt", lambda take: kurzstuecke.Ergebnis("nichts"))
    args = argparse.Namespace(ziel=["take"], neu=False)
    kurzstuecke.befehl(args)
    kurzstuecke.befehl(args)
    assert gebaut == ["take"]


def test_planen_nimmt_beide_zusatzstuecke_auf(repo):
    _take(repo)
    for suffix, stil in (("lese", "lesereel"), ("uebermalt", "uebermalt")):
        ziel = repo / "ausgabe" / f"take-{suffix}"
        ziel.mkdir()
        (ziel / "instagram.mp4").write_bytes(b"x")
        (ziel / "stueck.json").write_text(json.dumps({"id": f"take-{suffix}", "status": "fertig", "nr": 1,
            "von_stuecken": 1, "stil": stil, "dauer_s": 8, "dateien": {"instagram": "instagram.mp4"}}))
        (ziel / "texte.json").write_text(json.dumps({"instagram": {"caption": "Text"}}))
    kandidaten = plan._kandidaten()
    assert {k["quelle"] for k in kandidaten} >= {"take-lese", "take-uebermalt"}
    plan.befehl_planen(argparse.Namespace(tage=3))
    geplant = {e["quelle"] for e in json.loads((repo / "arbeit/plan.json").read_text())["eintraege"]}
    assert {"take-lese", "take-uebermalt"} <= geplant
