"""Gemeinsame Testhilfe: jeder Test bekommt ein eigenes Repo in einem tmp-Ordner.

`repo` kopiert konfig/, schriften/, vorlagen/ dorthin und biegt kern.ROOT um.
Alle Module rufen pfad()/konfig() zur Laufzeit auf und landen damit im
tmp-Ordner, nie im echten arbeit/. Das Urteil läuft ohne Modell.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pipeline import kern, schrift

ECHT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for ordner in ("konfig", "schriften", "vorlagen"):
        shutil.copytree(ECHT / ordner, tmp_path / ordner)
    for ordner in ("eingang", "arbeit", "ausgabe", "medien/hintergruende"):
        (tmp_path / ordner).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(kern, "ROOT", tmp_path)
    monkeypatch.setenv("PIPELINE_ROOT", str(tmp_path))
    monkeypatch.setenv("URTEIL_BACKEND", "ohne")
    schrift.schrift.cache_clear()
    yield tmp_path
    schrift.schrift.cache_clear()
