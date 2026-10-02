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
if str(ECHT / "umbau") not in sys.path:
    sys.path.insert(0, str(ECHT / "umbau"))
import budget  # noqa: E402


@pytest.fixture(autouse=True)
def _ki_budget_abgeschirmt(tmp_path, monkeypatch):
    """Kein Test bucht ins echte arbeit/ki_budget.json oder zeigt eine echte
    Mac-Mitteilung. Auch Tests ohne `repo` rufen budget über storyboard_video
    und umbauen auf; ohne diese Abschirmung landeten ihre Schein-Buchungen im
    echten Monatsdeckel und der Deckel-Test meldete per osascript."""
    monkeypatch.setattr(budget, "_datei", lambda: tmp_path / "arbeit" / "ki_budget.json")
    monkeypatch.setattr(budget, "subprocess", SimpleNamespace(run=lambda *a, **k: None))


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
