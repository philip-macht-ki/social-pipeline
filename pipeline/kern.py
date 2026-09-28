"""Gemeinsamer Kern: Pfade, Konfiguration, JSON, Zeit, ffprobe, Sperre, Protokoll.

Jeder Schritt der Pipeline gibt ein `Ergebnis` zurück, statt still zu scheitern.
Formate der Dateien stehen in ARCHITEKTUR.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("PIPELINE_ROOT", Path(__file__).resolve().parents[1]))


def _env_laden() -> None:
    """Liest .env im Repo-Ordner (NAME=wert je Zeile). Die Umgebung hat Vorrang."""
    datei = ROOT / ".env"
    if not datei.exists():
        return
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        name, _, wert = zeile.partition("=")
        os.environ.setdefault(name.strip(), wert.strip().strip('"').strip("'"))


_env_laden()


@dataclass
class Ergebnis:
    """status: ok | befund | fehler | nichts. Ein Befund stoppt nichts, er wird gezeigt."""

    status: str
    meldung: str = ""
    daten: dict = field(default_factory=dict)

    @property
    def gut(self) -> bool:
        return self.status in ("ok", "befund", "nichts")


def konfig(name: str) -> dict:
    """Liest konfig/<name> (mit oder ohne .toml)."""
    datei = ROOT / "konfig" / (name if name.endswith(".toml") else f"{name}.toml")
    with open(datei, "rb") as f:
        return tomllib.load(f)


def pfad(*teile: str | Path) -> Path:
    return ROOT.joinpath(*[str(t) for t in teile])


def lesen(p: Path, standard=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return standard


def schreiben(p: Path, daten) -> None:
    """Schreibt JSON atomar, damit ein Abbruch keine halbe Datei hinterlässt."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def zone() -> ZoneInfo:
    return ZoneInfo(konfig("pipeline").get("zeitzone", "Europe/Berlin"))


def jetzt() -> datetime:
    return datetime.now(zone())


def dauer(datei: Path) -> float:
    """Länge einer Mediendatei in Sekunden, 0.0 wenn nicht messbar."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(datei)],
        capture_output=True,
        text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def lauf(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Führt einen Befehl aus. Wirft mit lesbarer Meldung, wenn er scheitert."""
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        schwanz = (r.stderr or r.stdout or "").strip().splitlines()[-8:]
        raise RuntimeError(f"{Path(str(cmd[0])).name} scheiterte ({r.returncode}): " + " | ".join(schwanz))
    return r


def log(zeile: str) -> None:
    """Eine Zeile ins Tagesprotokoll arbeit/logs/<datum>.log und auf den Bildschirm."""
    t = jetzt()
    ziel = pfad("arbeit", "logs", f"{t:%Y-%m-%d}.log")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with open(ziel, "a", encoding="utf-8") as f:
        f.write(f"{t:%H:%M:%S} {zeile}\n")
    print(zeile, flush=True)


class Sperre:
    """Verhindert zwei gleichzeitige Läufe. Prüft die PID, nicht den Befehlstext
    (pgrep findet sonst die eigene Diagnose-Shell)."""

    def __init__(self, name: str = "lauf"):
        self.p = pfad("arbeit", f".{name}.pid")

    def __enter__(self):
        self.p.parent.mkdir(parents=True, exist_ok=True)
        if self.p.exists():
            try:
                pid = int(self.p.read_text().strip())
                os.kill(pid, 0)
                raise RuntimeError(f"Ein Lauf ist schon aktiv (PID {pid}).")
            except (ValueError, ProcessLookupError):
                pass  # verwaiste Sperre von einem abgebrochenen Lauf
            except PermissionError:
                raise RuntimeError("Ein Lauf ist schon aktiv.")
        self.p.write_text(str(os.getpid()))
        return self

    def __exit__(self, *_):
        self.p.unlink(missing_ok=True)


def takes() -> list[Path]:
    basis = pfad("arbeit")
    if not basis.exists():
        return []
    return sorted(p for p in basis.iterdir() if p.is_dir() and (p / "take.json").exists())


def stuecke(take: str | None = None) -> list[Path]:
    """Ordner arbeit/<take>/stuecke/<nn> mit rezept.json."""
    return sorted(
        p.parent
        for t in takes()
        if not take or t.name == take
        for p in (t / "stuecke").glob("*/rezept.json")
    )


def stueck_ordner(stueck_id: str) -> Path:
    """rezept-Ordner zu einer Stück-ID wie 'beispiel-01'."""
    take, _, nr = stueck_id.rpartition("-")
    return pfad("arbeit", take, "stuecke", nr)
