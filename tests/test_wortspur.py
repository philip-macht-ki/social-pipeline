from __future__ import annotations

import json
import subprocess

import pytest

from pipeline import wortspur


def _roh_mit_ton(pfad, filter_text: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", filter_text, "-c:a", "aac", str(pfad)],
        check=True,
        capture_output=True,
    )


def test_nachziehen_folgt_toneinsatz_und_laesst_ohne_luecke_unveraendert(repo):
    ordner = repo / "ausgabe" / "x-01"
    ordner.mkdir(parents=True)
    ton = (
        "aevalsrc=if(between(t\\,0.5\\,1.0)\\,0.5*sin(2*PI*440*t)\\,0):"
        "s=16000:d=3"
    )
    _roh_mit_ton(ordner / "roh.mp4", ton)
    achse = {"woerter": [
        {"w": "Erstes", "s": 0.0, "e": 1.2},
        {"w": "zweites", "s": 1.5, "e": 1.8},
    ], "dauer_s": 3.0}
    (ordner / "zeitachse.json").write_text(json.dumps(achse), encoding="utf-8")

    ergebnis = wortspur.nachziehen(ordner)
    neu = json.loads((ordner / "zeitachse.json").read_text(encoding="utf-8"))

    assert ergebnis.status == "ok"
    assert neu["woerter"][0]["s"] == pytest.approx(0.5, abs=0.03)
    assert neu["woerter"][1]["s"] == 1.5
    assert neu["wortanfang_korrigiert"] == 1


def test_nachziehen_korrigiert_nicht_vor_drei_zehnteln_oder_nach_zwei_sekunden(repo):
    ordner = repo / "ausgabe" / "x-01"
    ordner.mkdir(parents=True)
    ton = (
        "aevalsrc=if(between(t\\,0.1\\,0.2)+between(t\\,2.1\\,2.3)\\,"
        "0.5*sin(2*PI*440*t)\\,0):s=16000:d=3"
    )
    _roh_mit_ton(ordner / "roh.mp4", ton)
    achse = {"woerter": [{"w": "Erstes", "s": 0.0, "e": 2.5}], "dauer_s": 3.0}
    (ordner / "zeitachse.json").write_text(json.dumps(achse), encoding="utf-8")

    wortspur.nachziehen(ordner)
    neu = json.loads((ordner / "zeitachse.json").read_text(encoding="utf-8"))

    assert neu["woerter"][0]["s"] == 0.0
    assert neu["wortanfang_korrigiert"] == 0
