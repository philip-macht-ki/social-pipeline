"""Eine kurze KI-Szene in einen Rohschnitt einsetzen.

Dieses Modul wird von video.py aufgerufen. Es beendet nie den Bau eines Stuecks:
bei fehlendem Modell, Budget oder einer fehlgeschlagenen Erzeugung bleibt roh.mp4.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from pipeline import urteil
from pipeline.kern import konfig, lesen, log, pfad, schreiben

try:
    from umbau import budget
except ModuleNotFoundError:  # Das Werkzeug liegt absichtlich neben dem Paket.
    UMBAU = Path(__file__).resolve().parents[1] / "umbau"
    sys.path.insert(0, str(UMBAU))
    import budget

DAUER = {"ltx": 2.2, "flux": 3.0, "seedance": 4.0}


def _rotation() -> int:
    datei = pfad("arbeit", "ki_rotation.json")
    daten = lesen(datei, {}) or {}
    daten["stuecke"] = int(daten.get("stuecke", 0)) + 1
    schreiben(datei, daten)
    return daten["stuecke"]


def _seedance_woche() -> int:
    from datetime import timedelta

    grenze = (budget.jetzt() - timedelta(days=7)).isoformat()
    daten = lesen(pfad("arbeit", "ki_budget.json"), {}) or {}
    return sum(
        1
        for b in daten.get("buchungen", [])
        if b.get("art") == "seedance"
        and b.get("status") == "gebucht"
        and b.get("zeit", "") >= grenze
    )


def _hat_schluessel() -> bool:
    try:
        try:
            from umbau import openrouter
        except ModuleNotFoundError:
            import openrouter
        return bool(openrouter.schluessel())
    except Exception:
        return False


def _wahl() -> list[str]:
    nummer = _rotation()
    schluessel = _hat_schluessel()
    auswahl: list[str] = []
    seedance_moeglich = (
        nummer % 7 == 0
        and _seedance_woche() < 2
        and schluessel
        and budget.darf("seedance", DAUER["seedance"])
    )
    flux_moeglich = schluessel and budget.darf("flux", DAUER["flux"])
    if seedance_moeglich:
        auswahl.append("seedance")
    if (nummer % 3 == 0 or nummer % 7 == 0 and not seedance_moeglich) and flux_moeglich:
        auswahl.append("flux")
    ltx = str(konfig("pipeline").get("ki", {}).get("ltx_ordner", ""))
    if ltx and Path(ltx).is_dir():
        auswahl.append("ltx")
    return auswahl


def _pruefe_plan(antwort: object) -> str | None:
    if not isinstance(antwort, dict):
        return "Die Antwort ist kein JSON-Objekt."
    if not isinstance(antwort.get("wort"), str) or not isinstance(
        antwort.get("prompt"), str
    ):
        return "wort und prompt fehlen."
    prompt = antwort["prompt"].lower()
    verboten = ("text", "logo", "customer", "price", "result")
    if any(w in prompt for w in verboten):
        return "Der Bildauftrag verletzt eine Sicherheitsregel."
    return None


def _plan(art: str, achse: dict) -> dict | None:
    woerter = achse.get("woerter", [])
    text = " ".join(f"{w.get('w', '')}[{w.get('s', 0):.2f}]" for w in woerter)[:4000]
    flux = art == "flux"
    regel = (
        "Die sprechende Person bleibt echt: Gesicht, Kleidung, Haltung und Stimme unveraendert. "
        "Nur der Raum verwandelt sich. "
        if flux
        else "Die Zwischenszene zeigt keine Menschen, Haende oder Gesichter. "
    )
    auftrag = urteil.vorlage(
        "ki_einblendung", art=art, dauer=DAUER[art], transkript=text, regeln=regel
    )
    try:
        antwort = urteil.frage(
            auftrag, zweck="ki_einblendung", rueckfall=lambda: None, pruefe=_pruefe_plan
        )
    except Exception as e:
        log(f"KI-Einblendung: Planung gescheitert: {e}")
        return None
    if not isinstance(antwort, dict):
        return None
    wort = re.sub(r"[^\wäöüß-]", "", antwort.get("wort", "").lower())
    for w in woerter:
        gleich = re.sub(r"[^\wäöüß-]", "", str(w.get("w", "")).lower()) == wort
        von = float(w.get("s", -1))
        if (
            gleich
            and von >= 3
            and von + DAUER[art] <= float(achse.get("dauer_s", 0)) - 0.5
        ):
            return {"von": round(von, 2), "prompt": antwort["prompt"].strip()}
    log("KI-Einblendung: Modellwort liegt nicht an einer passenden Stelle.")
    return None


def _ltx(plan: dict, ziel: Path) -> None:
    ordner = Path(str(konfig("pipeline")["ki"]["ltx_ordner"]))
    cmd = [
        "uv",
        "run",
        "ltx-2-mlx",
        "generate",
        "-p",
        plan["prompt"] + " No people, no text, no logos.",
        "--frames",
        "97",
        "--frame-rate",
        "25",
        "-H",
        "1280",
        "-W",
        "704",
        "--distilled",
        "--low-ram",
        "-o",
        str(ziel),
    ]
    subprocess.run(
        cmd, cwd=ordner, check=True, capture_output=True, text=True, timeout=1500
    )


def _bezahlt(art: str, plan: dict, roh: Path, ziel: Path, stueck_id: str) -> None:
    try:
        from umbau import storyboard_video, umbauen
    except ModuleNotFoundError:
        import storyboard_video
        import umbauen
    nummer = budget.reservieren(art, DAUER[art], stueck_id)
    ok = False
    kosten = None
    try:
        if art == "seedance":
            ergebnis = storyboard_video.erzeugen(
                None,
                str(ziel),
                plan["prompt"],
                modell="bytedance/seedance-2.0-fast",
                dauer=4,
                size="720x1280",
                budgetiert=True,
            )
        else:
            ausschnitt = ziel.with_name("flux_eingang.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(plan["von"]),
                    "-t",
                    "3",
                    "-i",
                    str(roh),
                    "-an",
                    "-vf",
                    "scale=720:1280",
                    str(ausschnitt),
                ],
                check=True,
            )
            try:
                ergebnis = umbauen.umbauen(
                    str(ausschnitt), str(ziel), plan["prompt"], dauer=3, budgetiert=True
                )
            finally:
                ausschnitt.unlink(missing_ok=True)
        nutzung = ergebnis.get("usage") or {}
        kosten = (
            nutzung.get("cost") if isinstance(nutzung, dict) else ergebnis.get("cost")
        )
        ok = True
    finally:
        budget.abschliessen(nummer, kosten, ok)


def _einsetzen(roh: Path, clip: Path, ziel: Path, von: float, laenge: float) -> None:
    filter = (
        f"[1:v]trim=0:{laenge:.3f},setpts=PTS-STARTPTS+{von:.3f}/TB,"
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30[k];"
        f"[0:v][k]overlay=0:0:enable='between(t,{von:.3f},{von + laenge:.3f})':eof_action=pass[v]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(roh),
            "-i",
            str(clip),
            "-filter_complex",
            filter,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "veryfast",
            "-c:a",
            "copy",
            str(ziel),
        ],
        check=True,
    )


def anwenden(
    stueck_id: str, rezept: dict, rezept_pfad: Path, roh: Path, achse: dict
) -> Path:
    """Erzeugt hoechstens eine Einblendung und gibt das Video fuer Schrift-Ebenen zurueck."""
    if not konfig("pipeline").get("ki", {}).get("einblendung", False):
        rezept["ki_einblendung"] = None
        schreiben(rezept_pfad, rezept)
        return roh
    ausgabe = pfad("ausgabe", stueck_id)
    fertig = ausgabe / "roh_ki.mp4"
    if (
        rezept.get("ki_einblendung")
        and fertig.exists()
        and fertig.stat().st_mtime > roh.stat().st_mtime
    ):
        return fertig
    for art in _wahl():
        plan = _plan(art, achse)
        if not plan:
            continue
        clip = ausgabe / f"ki_{art}.mp4"
        try:
            ausgabe.mkdir(parents=True, exist_ok=True)
            if art == "ltx":
                _ltx(plan, clip)
            else:
                _bezahlt(art, plan, roh, clip, stueck_id)
            _einsetzen(roh, clip, fertig, plan["von"], DAUER[art])
            rezept["ki_einblendung"] = {
                "art": art,
                "von": plan["von"],
                "bis": round(plan["von"] + DAUER[art], 2),
                "prompt": plan["prompt"],
            }
            schreiben(rezept_pfad, rezept)
            return fertig
        except Exception as e:
            log(f"KI-Einblendung {art} gescheitert, Rueckfall: {e}")
    rezept["ki_einblendung"] = None
    schreiben(rezept_pfad, rezept)
    return roh


def befehl_budget(args) -> int:
    return budget.befehl(args)
