"""Gemeinsame Testhilfe: jeder Test bekommt ein eigenes Repo in einem tmp-Ordner.

`repo` kopiert konfig/, schriften/, vorlagen/ dorthin und biegt kern.ROOT um.
Alle Module rufen pfad()/konfig() zur Laufzeit auf und landen damit im
tmp-Ordner, nie im echten arbeit/. Das Urteil läuft ohne Modell.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import kern, schrift

ECHT = Path(__file__).resolve().parents[1]
# Repo-Wurzel für `from umbau import …` (umbau/ ist kein installiertes Paket).
if str(ECHT) not in sys.path:
    sys.path.insert(0, str(ECHT))
if str(ECHT / "umbau") not in sys.path:
    sys.path.insert(0, str(ECHT / "umbau"))
import budget  # noqa: E402
import openrouter  # noqa: E402
from umbau import budget as umbau_budget  # noqa: E402
from umbau import openrouter as umbau_openrouter  # noqa: E402


@pytest.fixture(autouse=True)
def _ki_budget_abgeschirmt(tmp_path, monkeypatch):
    """Kein Test bucht ins echte arbeit/ki_budget.json, zeigt eine echte
    Mac-Mitteilung oder findet den echten OpenRouter-Schlüssel (ein echter
    Aufruf kostet Geld). Ein Test, der einen Schlüssel braucht, setzt
    OPENROUTER_API_KEY selbst auf einen Schein-Wert.

    umbau/ hat keine __init__.py: dieselben Dateien sind als `budget` (bare
    import, umbau/ in sys.path) und als `umbau.budget` (aus pipeline/) zwei
    getrennte Module. Darum wird jede Kopie einzeln abgeschirmt."""
    datei = tmp_path / "arbeit" / "ki_budget.json"
    for modul in (budget, umbau_budget):
        monkeypatch.setattr(modul, "_datei", lambda: datei)
        monkeypatch.setattr(modul, "subprocess", SimpleNamespace(run=lambda *a, **k: None))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    kein_eintrag = SimpleNamespace(stdout="")
    for modul in (openrouter, umbau_openrouter):
        monkeypatch.setattr(modul, "subprocess", SimpleNamespace(run=lambda *a, **k: kein_eintrag))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for ordner in ("konfig", "schriften", "vorlagen"):
        shutil.copytree(ECHT / ordner, tmp_path / ordner)
    for ordner in ("eingang", "arbeit", "ausgabe", "medien/hintergruende"):
        (tmp_path / ordner).mkdir(parents=True, exist_ok=True)
    # Tests laufen ohne echtes Netz: die Rechtschreibprüfung ist standardmäßig
    # aus, egal was in der echten konfig/pipeline.toml steht. Ein Test, der sie
    # gezielt prüfen will, mockt `rechtschreibung.pruefe` selbst (siehe
    # tests/test_rechtschreibung.py, tests/test_texte.py).
    pipeline_toml = tmp_path / "konfig" / "pipeline.toml"
    alt = pipeline_toml.read_text(encoding="utf-8")
    neu = alt.replace("[rechtschreibung]\nan = true", "[rechtschreibung]\nan = false")
    pipeline_toml.write_text(neu, encoding="utf-8")
    monkeypatch.setattr(kern, "ROOT", tmp_path)
    monkeypatch.setenv("PIPELINE_ROOT", str(tmp_path))
    monkeypatch.setenv("URTEIL_BACKEND", "ohne")
    schrift.schrift.cache_clear()
    yield tmp_path
    schrift.schrift.cache_clear()
