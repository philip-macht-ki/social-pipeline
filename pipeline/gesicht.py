"""Gesichtszonen für Einblendungen, mit einem sicheren Rückfall ohne Vision."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .kern import log


FALLBACK = {"x": 0.33, "y": 0.26, "b": 0.34, "h": 0.21}


def _rueckfall() -> list[dict]:
    return [{"s": 0.0, **FALLBACK}]


def laden(roh: Path, ziel: Path, dauer: float) -> list[dict]:
    """Liest die Cache-Datei oder sucht alle 0,5 Sekunden mit macOS Vision.

    Vision ist absichtlich optional. Es kommt mit `uv sync --extra mac`; ohne
    das Extra bleibt die Kopfzone stabil
    und der Videobau funktioniert auf jeder unterstützten Installation.
    """
    if ziel.exists():
        try:
            return json.loads(ziel.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    try:
        from Vision import VNDetectFaceRectanglesRequest, VNImageRequestHandler
        from Quartz import CIImage
        from Foundation import NSURL
    except ImportError:
        log(
            "befund: Gesichtserkennung fehlt, mit `uv sync --extra mac` installieren; "
            "feste Kopfzone verwendet."
        )
        daten = _rueckfall()
        ziel.write_text(json.dumps(daten), encoding="utf-8")
        return daten

    treffer: list[dict] = []
    for nr in range(int(dauer / 0.5) + 1):
        zeit = nr * 0.5
        frame = ziel.parent / f"._gesicht_{nr}.jpg"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{zeit:.2f}",
                    "-i",
                    str(roh),
                    "-frames:v",
                    "1",
                    str(frame),
                ],
                check=True,
                capture_output=True,
            )
            anfrage = VNDetectFaceRectanglesRequest.alloc().init()
            handler = VNImageRequestHandler.alloc().initWithCIImage_options_(
                CIImage.imageWithContentsOfURL_(NSURL.fileURLWithPath_(str(frame))), {}
            )
            handler.performRequests_error_([anfrage], None)
            beobachtungen = anfrage.results() or []
            if beobachtungen:
                box = beobachtungen[0].boundingBox()
                # Vision zählt von unten. Der Rest der Pipeline von oben.
                h = min(1.0 - box.origin.y, box.size.height * 1.15)
                treffer.append(
                    {
                        "s": zeit,
                        "x": box.origin.x,
                        "y": 1 - box.origin.y - h,
                        "b": box.size.width,
                        "h": h,
                    }
                )
        except Exception:
            continue
        finally:
            frame.unlink(missing_ok=True)
    if not treffer:
        log("befund: Gesichtserkennung ohne Treffer, feste Kopfzone verwendet.")
        treffer = _rueckfall()
    ziel.write_text(json.dumps(treffer), encoding="utf-8")
    return treffer


def bei(gesichter: list[dict], zeit: float) -> dict:
    """Nimmt die zuletzt bekannte Gesichtszonenmessung."""
    return max(
        (g for g in gesichter if g.get("s", 0) <= zeit),
        key=lambda g: g.get("s", 0),
        default=gesichter[0],
    )
