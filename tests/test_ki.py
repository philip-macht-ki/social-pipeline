"""Tests fuer Monatsdeckel und sichere Rueckfaelle der KI-Einblendung."""
from __future__ import annotations

from datetime import datetime
import json
import os
import sys
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

import pytest

from pipeline import ki_einblendung

UMBAU = Path(__file__).resolve().parents[1] / "umbau"
if str(UMBAU) not in sys.path:
    sys.path.insert(0, str(UMBAU))
import budget


def _zeit(monat: int):
    return lambda: datetime(2026, monat, 2, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))


def test_budget_reservieren_abschliessen_und_stornieren(repo, monkeypatch):
    monkeypatch.setattr(budget, "jetzt", _zeit(1))
    nummer = budget.reservieren("flux", 3, "test")
    budget.abschliessen(nummer, 0.12, True)
    zweite = budget.reservieren("flux", 3, "test")
    budget.abschliessen(zweite, None, False)
    assert "0.12" in budget.stand()


def test_budget_deckel_und_monatswechsel(repo, monkeypatch):
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text(encoding="utf-8").replace("deckel_eur = 20", "deckel_eur = 0.1"),
                      encoding="utf-8")
    monkeypatch.setattr(budget, "jetzt", _zeit(1))
    nummer = budget.reservieren("flux", 2, "test")
    budget.abschliessen(nummer, None, True)
    assert not budget.darf("flux", 1)
    assert budget.darf("ltx", 2.2)
    monkeypatch.setattr(budget, "jetzt", _zeit(2))
    assert budget.darf("flux", 1)


def test_budget_zwei_reservierungen_reissen_den_deckel_nicht(repo, monkeypatch):
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text(encoding="utf-8").replace("deckel_eur = 20", "deckel_eur = 0.2"),
                      encoding="utf-8")
    monkeypatch.setattr(budget, "jetzt", _zeit(1))
    budget.reservieren("flux", 4, "erste")
    with pytest.raises(RuntimeError, match="Monatsdeckel"):
        budget.reservieren("flux", 4, "zweite")
    daten = json.loads((repo / "arbeit" / "ki_budget.json").read_text(encoding="utf-8"))
    assert len(daten["buchungen"]) == 1


def test_budget_sperrt_zwei_gleichzeitige_reservierungen(repo):
    konfig = repo / "konfig" / "pipeline.toml"
    konfig.write_text(konfig.read_text(encoding="utf-8").replace("deckel_eur = 20", "deckel_eur = 0.2"),
                      encoding="utf-8")
    umgebung = {**os.environ, "PIPELINE_ROOT": str(repo)}
    code = "import sys; sys.path.insert(0, 'umbau'); import budget; print(budget.reservieren('flux', 4, 'test'))"
    erste = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=umgebung)
    zweite = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=umgebung)
    ergebnisse = [prozess.communicate() for prozess in (erste, zweite)]
    assert sum(prozess.returncode == 0 for prozess in (erste, zweite)) == 1, ergebnisse
    daten = json.loads((repo / "arbeit" / "ki_budget.json").read_text(encoding="utf-8"))
    assert len(daten["buchungen"]) == 1


def test_einblendung_aus_schreibt_null(repo, tmp_path):
    rezept = {"id": "take-01", "ki_einblendung": {"art": "flux"}}
    rezept_pfad = tmp_path / "rezept.json"
    roh = tmp_path / "roh.mp4"
    roh.write_bytes(b"roh")
    assert ki_einblendung.anwenden("take-01", rezept, rezept_pfad, roh, {}) == roh
    assert rezept["ki_einblendung"] is None


def test_bildauftrag_prueft_verbotene_woerter():
    assert ki_einblendung._pruefe_plan({"wort": "Haus", "prompt": "quiet room"}) is None
    assert ki_einblendung._pruefe_plan({"wort": "Haus", "prompt": "logo on wall"})


def test_plan_nutzt_prompt_ueber_den_echten_urteil_weg(repo, monkeypatch):
    antwort = {"wort": "Fenster", "prompt": "quiet empty room, no people"}
    monkeypatch.setattr(ki_einblendung.urteil, "vorlage", lambda *a, **k: "auftrag")

    def frage(auftrag, **kwargs):
        assert kwargs["pruefe"](antwort) is None
        return antwort

    monkeypatch.setattr(ki_einblendung.urteil, "frage", frage)
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"einblendung": True}})
    monkeypatch.setattr(ki_einblendung, "_wahl", lambda: ["ltx"])
    monkeypatch.setattr(ki_einblendung, "_ltx", lambda plan, ziel: ziel.write_bytes(b"clip"))
    monkeypatch.setattr(ki_einblendung, "_einsetzen", lambda roh, clip, ziel, *a: ziel.write_bytes(b"fertig"))
    achse = {"dauer_s": 12, "woerter": [{"w": "Fenster", "s": 4.0}]}
    roh = repo / "ausgabe" / "take-01" / "roh.mp4"
    roh.parent.mkdir(parents=True)
    roh.write_bytes(b"roh")
    rezept = {"id": "take-01"}
    rezept_pfad = repo / "arbeit" / "take" / "stuecke" / "01" / "rezept.json"
    assert ki_einblendung.anwenden("take-01", rezept, rezept_pfad, roh, achse).name == "roh_ki.mp4"
    assert rezept["ki_einblendung"]["prompt"] == antwort["prompt"]


def test_seedance_sendet_keinen_ausschnitt_aus_der_aufnahme(monkeypatch, tmp_path):
    # Dasselbe Modulobjekt wie in ki_einblendung, nicht der bare import aus umbau/.
    from umbau import storyboard_video

    aufruf = {}
    monkeypatch.setattr(ki_einblendung.budget, "reservieren", lambda *a: "buchung")
    monkeypatch.setattr(ki_einblendung.budget, "abschliessen", lambda *a: aufruf.setdefault("abschluss", a))

    def erzeugen(bild, ziel, prompt, **kwargs):
        aufruf.update({"bild": bild, "ziel": ziel, "prompt": prompt, **kwargs})
        return {"usage": {"cost": 0.2}}

    monkeypatch.setattr(storyboard_video, "erzeugen", erzeugen)
    roh = tmp_path / "roh.mp4"
    roh.write_bytes(b"aufnahme")
    ki_einblendung._bezahlt("seedance", {"von": 4.0, "prompt": "empty room"}, roh,
                            tmp_path / "ki.mp4", "take-01")
    assert aufruf["bild"] is None
    assert aufruf["prompt"] == "empty room"
    assert aufruf["budgetiert"] is True


def test_rotation_priorisiert_flux_und_seedance_nur_mit_schluessel_und_budget(repo, monkeypatch):
    ltx = repo / "ltx"
    ltx.mkdir()
    monkeypatch.setattr(ki_einblendung, "_hat_schluessel", lambda: True)
    monkeypatch.setattr(ki_einblendung.budget, "darf", lambda *a: True)
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"ltx_ordner": str(ltx)}})
    assert ki_einblendung._wahl() == ["ltx"]
    assert ki_einblendung._wahl() == ["ltx"]
    assert ki_einblendung._wahl() == ["flux", "ltx"]
    for _ in range(3):
        ki_einblendung._wahl()
    assert ki_einblendung._wahl() == ["seedance", "ltx"]
    monkeypatch.setattr(ki_einblendung, "_hat_schluessel", lambda: False)
    assert ki_einblendung._wahl() == ["ltx"]
    monkeypatch.setattr(ki_einblendung, "_hat_schluessel", lambda: True)
    monkeypatch.setattr(ki_einblendung.budget, "darf", lambda *a: False)
    assert ki_einblendung._wahl() == ["ltx"]


def test_ohne_ltx_ordner_gibt_es_bei_normalem_stueck_keine_einblendung(repo, monkeypatch):
    monkeypatch.setattr(ki_einblendung, "_hat_schluessel", lambda: True)
    monkeypatch.setattr(ki_einblendung.budget, "darf", lambda *a: True)
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"ltx_ordner": ""}})
    assert ki_einblendung._wahl() == []


def test_seedance_woche_faellt_auf_flux_und_ltx_zurueck(repo, monkeypatch):
    ltx = repo / "ltx"
    ltx.mkdir()
    monkeypatch.setattr(ki_einblendung, "_hat_schluessel", lambda: True)
    monkeypatch.setattr(ki_einblendung.budget, "darf", lambda *a: True)
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"ltx_ordner": str(ltx)}})
    monkeypatch.setattr(ki_einblendung, "_seedance_woche", lambda: 2)
    for _ in range(6):
        ki_einblendung._wahl()
    assert ki_einblendung._wahl() == ["flux", "ltx"]


def test_fehlgeschlagene_bezahlte_einblendung_storniert_und_faellt_zurueck(repo, monkeypatch):
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"einblendung": True}})
    monkeypatch.setattr(ki_einblendung, "_wahl", lambda: ["flux", "ltx"])
    monkeypatch.setattr(ki_einblendung, "_plan", lambda *a: {"von": 4.0, "prompt": "quiet room"})
    monkeypatch.setattr(
        ki_einblendung,
        "_ltx",
        lambda *a: (_ for _ in ()).throw(RuntimeError("ltx kaputt")),
    )
    monkeypatch.setattr(ki_einblendung.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("flux kaputt")))
    roh = repo / "ausgabe" / "take-01" / "roh.mp4"
    roh.parent.mkdir(parents=True)
    roh.write_bytes(b"roh")
    rezept = {"id": "take-01"}
    rezept_pfad = repo / "arbeit" / "take" / "stuecke" / "01" / "rezept.json"
    assert ki_einblendung.anwenden("take-01", rezept, rezept_pfad, roh, {}) == roh
    assert rezept["ki_einblendung"] is None
    buchung = json.loads((repo / "arbeit" / "ki_budget.json").read_text(encoding="utf-8"))["buchungen"][0]
    assert buchung["status"] == "storniert"


def test_vorhandenes_juengeres_ki_video_wird_nicht_neu_erzeugt(repo, monkeypatch):
    monkeypatch.setattr(ki_einblendung, "konfig", lambda *a: {"ki": {"einblendung": True}})
    monkeypatch.setattr(ki_einblendung, "_wahl", lambda: (_ for _ in ()).throw(AssertionError("neuer Aufruf")))
    roh = repo / "ausgabe" / "take-01" / "roh.mp4"
    fertig = roh.with_name("roh_ki.mp4")
    roh.parent.mkdir(parents=True)
    roh.write_bytes(b"roh")
    fertig.write_bytes(b"ki")
    rezept = {"ki_einblendung": {"art": "flux"}}
    assert ki_einblendung.anwenden("take-01", rezept, repo / "rezept.json", roh, {}) == fertig


def test_deckel_meldet_je_monat_nur_einmal(repo, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(budget.sys, "platform", "darwin")
    monkeypatch.setattr(budget.subprocess, "run", lambda *a, **k: aufrufe.append(a))
    monkeypatch.setattr(budget, "jetzt", _zeit(1))
    budget.schreiben(budget._datei(), {"monat": "2026-01", "gemeldet": False, "buchungen": [
        {"status": "gebucht", "kosten": 20.0},
    ]})
    assert not budget.darf("flux", 1)
    assert not budget.darf("flux", 1)
    monkeypatch.setattr(budget, "jetzt", _zeit(2))
    budget.schreiben(budget._datei(), {"monat": "2026-02", "gemeldet": False, "buchungen": [
        {"status": "gebucht", "kosten": 20.0},
    ]})
    assert not budget.darf("flux", 1)
    assert len(aufrufe) == 2


def test_zu_grosser_einzelauftrag_meldet_keinen_deckel(repo, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(budget.sys, "platform", "darwin")
    monkeypatch.setattr(budget.subprocess, "run", lambda *a, **k: aufrufe.append(a))
    monkeypatch.setattr(budget, "jetzt", _zeit(1))
    assert not budget.darf("seedance", 300)
    assert budget.darf("seedance", 4)
    assert aufrufe == []


def test_einsetzen_mit_kuenstlichem_clip(tmp_path):
    roh = tmp_path / "roh.mp4"
    clip = tmp_path / "clip.mp4"
    ziel = tmp_path / "roh_ki.mp4"
    for datei, farbe in ((roh, "blue"), (clip, "red")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"color={farbe}:size=1080x1920:rate=30", "-t", "2", str(datei)], check=True)
    ki_einblendung._einsetzen(roh, clip, ziel, 0.5, 1.0)
    assert ziel.exists() and ziel.stat().st_size > 0
