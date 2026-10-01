"""Tests für die Werkzeuge in umbau/, ohne Netzzugriff und ohne echtes ffmpeg
oder rclone. Die Module liegen bewusst außerhalb des pipeline-Pakets (eigene
Vorlage, keine zusätzliche Abhängigkeit), deshalb werden sie hier per Pfad
geladen statt importiert.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

UMBAU = Path(__file__).resolve().parents[1] / "umbau"


def _laden(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(f"umbau_{name}", UMBAU / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


hochladen = _laden("hochladen")
abschnitte_mod = _laden("abschnitte")
einsetzen_mod = _laden("einsetzen")
openrouter_mod = _laden("openrouter")
musik_mod = _laden("musik")


# --- hochladen.py: Drive-Link-Umbau ---------------------------------------


def test_drive_id_zu_link():
    link = hochladen.drive_id_zu_link("ABC123")
    assert link == "https://drive.usercontent.google.com/download?id=ABC123&export=download"


def test_id_aus_rclone_link_mit_id_parameter():
    text = "https://drive.google.com/uc?id=XYZ789&export=download\n"
    assert hochladen._id_aus_rclone_link(text) == "XYZ789"


def test_id_aus_rclone_link_mit_pfadform():
    text = "https://drive.google.com/file/d/QWE456/view?usp=drivesdk\n"
    assert hochladen._id_aus_rclone_link(text) == "QWE456"


def test_id_aus_rclone_link_ohne_treffer_wirft():
    with pytest.raises(RuntimeError):
        hochladen._id_aus_rclone_link("keine brauchbare Antwort hier")


def test_ziel_nimmt_umgebungsvariable(monkeypatch):
    monkeypatch.setenv("UMBAU_RCLONE_ZIEL", "gdrive:anderer-ordner")
    assert hochladen.ziel() == "gdrive:anderer-ordner"


def test_ziel_hat_standardwert(monkeypatch):
    monkeypatch.delenv("UMBAU_RCLONE_ZIEL", raising=False)
    assert hochladen.ziel() == "gdrive:umbau-tmp"


def test_kurzlebiger_link_laedt_hoch_und_loescht_immer(monkeypatch, tmp_path):
    aufgerufen = []

    def fake_hochladen(pfad, remote=None):
        aufgerufen.append(("hoch", pfad))
        return "datei.mp4", "https://beispiel.invalid/datei"

    def fake_weg(name, remote=None):
        aufgerufen.append(("weg", name))

    monkeypatch.setattr(hochladen, "hochladen", fake_hochladen)
    monkeypatch.setattr(hochladen, "weg", fake_weg)

    datei = tmp_path / "x.mp4"
    datei.write_bytes(b"x")

    with pytest.raises(ValueError):
        with hochladen.kurzlebiger_link(str(datei)) as link:
            assert link == "https://beispiel.invalid/datei"
            raise ValueError("Fehler mitten im Auftrag")

    assert aufgerufen == [("hoch", str(datei)), ("weg", "datei.mp4")]


# --- abschnitte.py: abschnitte.json-Prüfung -------------------------------


def test_abschnitte_pruefen_akzeptiert_gueltige_liste():
    abschnitte_mod.pruefen([{"name": "a", "von": 0.0, "bis": 1.5}])


def test_abschnitte_pruefen_lehnt_leere_liste_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen([])


def test_abschnitte_pruefen_lehnt_fehlendes_feld_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen([{"name": "a", "von": 0.0}])


def test_abschnitte_pruefen_lehnt_doppelten_namen_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen(
            [{"name": "a", "von": 0, "bis": 1}, {"name": "a", "von": 1, "bis": 2}]
        )


def test_abschnitte_pruefen_lehnt_bis_vor_von_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen([{"name": "a", "von": 2, "bis": 1}])


def test_abschnitte_pruefen_lehnt_text_statt_zahl_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen([{"name": "a", "von": "null", "bis": 1}])


def test_abschnitte_pruefen_lehnt_nicht_liste_ab():
    with pytest.raises(ValueError):
        abschnitte_mod.pruefen({"name": "a", "von": 0, "bis": 1})


# --- einsetzen.py: ffmpeg-Filterkette als reine Funktion ------------------


def test_farbfaktor_gleicht_dunkleres_bild_aus():
    faktoren = einsetzen_mod.farbfaktor([200, 200, 200], [180, 190, 170])
    assert faktoren[0] == pytest.approx(200 / 180)
    assert faktoren[1] == pytest.approx(200 / 190)
    assert faktoren[2] == pytest.approx(200 / 170)


def test_farbfaktor_schuetzt_vor_division_durch_null():
    faktoren = einsetzen_mod.farbfaktor([100, 100, 100], [0, 0, 0])
    assert all(f == 100.0 for f in faktoren)


def test_gain_filter_format():
    text = einsetzen_mod.gain_filter([1.1111, 1.0, 0.9])
    assert text == "colorchannelmixer=rr=1.1111:gg=1.0000:bb=0.9000"


def test_masken_kette_enthaelt_zeiten_und_schwelle():
    kette = einsetzen_mod.masken_kette(1.5, 4.0, "colorchannelmixer=rr=1:gg=1:bb=1", 28)
    assert "trim=1.5:4.0" in kette
    assert "gt(val,28)" in kette
    assert "alphamerge" in kette
    assert kette.endswith("[v]")


def test_ganz_kette_hat_keine_maske():
    kette = einsetzen_mod.ganz_kette("colorchannelmixer=rr=1:gg=1:bb=1")
    assert "alphamerge" not in kette
    assert "trim" not in kette
    assert kette.endswith("[v]")


def test_kette_bauen_waehlt_nach_modus():
    gain = "colorchannelmixer=rr=1:gg=1:bb=1"
    assert einsetzen_mod.kette_bauen("maske", 0, 1, gain, 28) == einsetzen_mod.masken_kette(0, 1, gain, 28)
    assert einsetzen_mod.kette_bauen("ganz", 0, 1, gain, 28) == einsetzen_mod.ganz_kette(gain)


def test_quelle_waehlen_bevorzugt_geschaerfte_datei(tmp_path):
    (tmp_path / "edit-a.mp4").write_bytes(b"x")
    (tmp_path / "edit-a-scharf.mp4").write_bytes(b"x")
    assert einsetzen_mod.quelle_waehlen(str(tmp_path), "a").endswith("edit-a-scharf.mp4")


def test_quelle_waehlen_faellt_zurueck_ohne_geschaerfte_datei(tmp_path):
    (tmp_path / "edit-a.mp4").write_bytes(b"x")
    assert einsetzen_mod.quelle_waehlen(str(tmp_path), "a").endswith("edit-a.mp4")
    assert "scharf" not in einsetzen_mod.quelle_waehlen(str(tmp_path), "a")


# --- Schlüssel wird nie in Ausgaben geschrieben ---------------------------


def test_openrouter_schluessel_aus_umgebungsvariable(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-geheim")
    assert openrouter_mod.schluessel() == "sk-or-v1-geheim"


def test_openrouter_schluessel_fehlermeldung_enthaelt_wert_nicht(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class LeereAntwort:
        stdout = ""

    monkeypatch.setattr(openrouter_mod.subprocess, "run", lambda *a, **k: LeereAntwort())
    with pytest.raises(RuntimeError) as err:
        openrouter_mod.schluessel()
    text = str(err.value)
    assert "sk-or" not in text
    assert "geheim" not in text


def test_musik_schluessel_fehlermeldung_enthaelt_wert_nicht(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    class LeereAntwort:
        stdout = ""

    monkeypatch.setattr(musik_mod.subprocess, "run", lambda *a, **k: LeereAntwort())
    with pytest.raises(RuntimeError) as err:
        musik_mod.schluessel()
    assert "elevenlabs-api-key" in str(err.value) or "ELEVENLABS_API_KEY" in str(err.value)


def test_openrouter_req_nie_mit_schluessel_im_body(monkeypatch):
    """req() darf den Schlüssel nur im Authorization-Header senden, nie im
    JSON-Körper landen lassen."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-geheim")
    aufgezeichnet = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(anfrage, timeout=120):
        aufgezeichnet["body"] = anfrage.data
        aufgezeichnet["header"] = anfrage.get_header("Authorization")
        return FakeResponse()

    monkeypatch.setattr(openrouter_mod.urllib.request, "urlopen", fake_urlopen)
    openrouter_mod.req("POST", "/videos", {"model": "x", "prompt": "y"})
    assert b"sk-or-v1-geheim" not in aufgezeichnet["body"]
    assert aufgezeichnet["header"] == "Bearer sk-or-v1-geheim"
