"""Stilwahl und Bildtexte je Take (pipeline/stile/redaktion.py, pipeline/stile/__init__.py)."""
import argparse
import json

from pipeline import kern, stile
from pipeline.stile import redaktion


def _take(repo, name="t1"):
    ordner = repo / "arbeit" / name
    (ordner / "stuecke" / "01").mkdir(parents=True)
    kern.schreiben(ordner / "take.json", {"id": name})
    saetze = [{"nr": i, "s": i * 3.0, "e": i * 3.0 + 2.5, "text": f"Satz Nummer {i} über deine Woche."} for i in range(8)]
    kern.schreiben(ordner / "saetze.json", saetze)
    kern.schreiben(ordner / "stuecke" / "01" / "rezept.json",
                   {"id": f"{name}-01", "titel": "Drei Schritte für deine Woche", "aussage": "Plane kurz, dann los."})
    return ordner


def test_auswahl_nimmt_am_wenigsten_benutzten_und_nie_heute_doppelt(repo):
    benutzt = {"instagram/zitat_standbild": {"anzahl": 5, "datum": "2000-01-01"},
               "instagram/zahl": {"anzahl": 0, "datum": "2026-09-28"}}
    wahl = redaktion.auswahl("instagram", "bild", 2, benutzt, heute="2026-09-28")
    assert "zahl" not in wahl, "heute schon benutzt"
    assert "zitat_standbild" not in wahl, "am häufigsten benutzt"
    assert len(wahl) == 2


def test_auswahl_kennt_die_neuen_instagram_karussells(repo):
    wahl = redaktion.auswahl("instagram", "karussell", 6, {}, heute="2026-09-28")
    assert {"foto", "handschrift_liste", "rasterposter"} <= set(wahl)


def test_gesperrter_stil_kommt_nie(repo):
    stile_toml = (repo / "konfig" / "stile.toml").read_text()
    (repo / "konfig" / "stile.toml").write_text(stile_toml.replace(
        '[instagram]\n', '[instagram]\n', 1).replace('gesperrt = []', 'gesperrt = ["einwand"]', 1))
    for _ in range(10):
        assert "einwand" not in redaktion.auswahl("instagram", "bild", 6, {})


def test_nur_eingeschaltete_plattformen(repo):
    kanaele = (repo / "konfig" / "kanaele.toml").read_text()
    (repo / "konfig" / "kanaele.toml").write_text(kanaele.replace("[tiktok]\nan = true", "[tiktok]\nan = false"))
    assert all(p != "tiktok" for p, _, _ in redaktion.plan_fuer_take({}))


def test_pruefung_verlangt_jeden_stil_und_verbietet_gedankenstrich():
    gewuenscht = [("instagram", "bild", "zahl"), ("threads", "text", "frage")]
    assert "fehlen" in redaktion._pruefe({"stile": []}, gewuenscht)
    antwort = {"stile": [{"plattform": "instagram", "stil": "zahl", "felder": {"zahl": "3", "aussage": "Drei – Dinge"},
                          "text": "x"}, {"plattform": "threads", "stil": "frage", "passt_nicht": "keine Frage"}]}
    assert redaktion._pruefe(antwort, gewuenscht)
    antwort["stile"][0]["felder"]["aussage"] = "Drei Dinge"
    assert redaktion._pruefe(antwort, gewuenscht) is None


def test_bilder_ohne_modell_baut_je_plattform_einen_stil_mit_text(repo):
    _take(repo)
    assert stile.befehl(argparse.Namespace(ziel=[], neu=False)) == 0
    manifeste = [json.loads(p.read_text()) for p in (repo / "ausgabe" / "bilder").glob("*/bild.json")]
    plattformen = [m["plattform"] for m in manifeste]
    assert plattformen.count("pinterest") <= 2
    assert sum(1 for m in manifeste if m["plattform"] == "instagram" and m["art"] == "bild") <= 1
    for m in manifeste:
        text = m["texte"][m["plattform"]]
        assert text.get("text"), f"{m['id']} ohne Beitragstext"
    # Ein zweiter Lauf baut für denselben Take nichts doppelt.
    vorher = len(manifeste)
    stile.befehl(argparse.Namespace(ziel=[], neu=False))
    assert len(list((repo / "ausgabe" / "bilder").glob("*/bild.json"))) == vorher


def test_passt_nicht_erzeugt_kein_bild(repo, monkeypatch):
    _take(repo)
    def antwort(take, gewuenscht):
        return {"stile": [{"plattform": p, "stil": s, "passt_nicht": "Material trägt es nicht"} for p, _, s in gewuenscht]}
    monkeypatch.setattr(redaktion, "texte_fuer_take", antwort)
    stile.befehl(argparse.Namespace(ziel=[], neu=False))
    assert not list((repo / "ausgabe" / "bilder").glob("*/bild.json"))


def test_neuer_karussellstil_faellt_auf_schritte_zurueck(repo, monkeypatch):
    _take(repo)
    monkeypatch.setattr(redaktion, "plan_fuer_take", lambda benutzt: [("instagram", "karussell", "foto")])
    monkeypatch.setattr(redaktion, "texte_fuer_take", lambda take, gewuenscht: {"stile": [{
        "plattform": "instagram", "stil": "foto", "passt_nicht": "Keine vier passenden Sätze."
    }]})
    assert stile.befehl(argparse.Namespace(ziel=[], neu=False)) == 0
    manifest = json.loads(next((repo / "ausgabe" / "bilder").glob("*/bild.json")).read_text())
    benutzt = kern.lesen(repo / "arbeit" / "stile_benutzt.json", {})
    assert manifest["stil"] == "schritte"
    assert "Rückfall auf schritte" in manifest["befunde"][0]
    assert "instagram/foto" not in benutzt
    assert benutzt["instagram/schritte"]["anzahl"] == 1


def test_neue_stilgrenzen_werden_vor_dem_rendern_geprueft():
    eintrag = {"plattform": "instagram", "stil": "rasterposter", "felder": {"punkte": [
        {"stichwort": "A", "satz": "B"} for _ in range(8)
    ]}}
    assert "neun" in redaktion._stilgrenzen(eintrag)
