"""uv run pipeline vorrat / status / zeitplan einrichten|entfernen [--trocken]

Betriebsübersicht (Vorrat gegen Soll, Kurzstatus) und die sichere Verwaltung
des launchd-Jobs, der den Tageslauf im Takt startet.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .kern import jetzt, konfig, lesen, pfad


def befehl_vorrat(args) -> int:
    """Zählt je Plattform und Tag geplante Beiträge gegen das Soll aus den Slots.

    "Irgendwas ist geplant" ist kein Vorrat: Es zählt nur die Zahl gegen das
    Soll, sonst meldet der Betrieb "nichts zu tun", obwohl Lücken offen sind
    (Falle aus dem Vorbild, 24.09.2026).
    """
    plan = lesen(pfad("arbeit", "plan.json"), {"eintraege": []}).get("eintraege", [])
    kanaele = konfig("kanaele")
    luecken: list[tuple] = []
    for tag_offset in range(7):
        datum = (jetzt() + timedelta(days=tag_offset)).date()
        for kanal, cfg in kanaele.items():
            soll = len(cfg.get("slots", []))
            ist = sum(1 for e in plan if e.get("kanal") == kanal
                      and datetime.fromisoformat(e["zeit"]).date() == datum
                      and e.get("status") in ("geplant", "laeuft", "veroeffentlicht"))
            if ist < soll:
                luecken.append((datum, kanal, soll - ist))
            zusatz = f" Lücke {soll - ist}" if ist < soll else ""
            print(f"{datum} {kanal}: {ist}/{soll}{zusatz}")
    roh = pfad("eingang").exists() and any(pfad("eingang").iterdir())
    fertig = any(pfad("ausgabe").glob("*/stueck.json")) or any(pfad("ausgabe", "bilder").glob("*/bild.json"))
    if not fertig and not roh:
        print("befund: Rohmaterial fehlt.")
    bald = jetzt().date() + timedelta(days=2)
    return 3 if any(datum <= bald for datum, _, _ in luecken) else 0


def befehl_status(args) -> int:
    takes = list(pfad("arbeit").glob("*/take.json"))
    stuecke = list(pfad("arbeit").glob("*/stuecke/*/rezept.json"))
    print(f"ok: Takes {len(takes)}, Stücke {len(stuecke)}.")
    plan = lesen(pfad("arbeit", "plan.json"), {"eintraege": []}).get("eintraege", [])
    bald = jetzt().date() + timedelta(days=2)
    for e in sorted(plan, key=lambda x: x.get("zeit", "")):
        # "pruefen" (hängender Lauf, siehe posten/__init__.py) immer zeigen, auch wenn
        # der ursprüngliche Sendeplatz schon länger als zwei Tage zurückliegt.
        if e.get("status") == "pruefen" or datetime.fromisoformat(e["zeit"]).date() <= bald:
            print(f"{e['zeit']} {e['kanal']} {e['status']}")
    for x in lesen(pfad("arbeit", "postlog.json"), [])[-10:]:
        print(f"postlog: {x.get('kanal')} {x.get('plan_id')} {x.get('status')}")
    return 0


def befehl_zeitplan(args) -> int:
    ziel = Path.home() / "Library/LaunchAgents/de.pipeline.takt.plist"
    vorlage = pfad("zeitplan", "de.pipeline.takt.plist.vorlage")
    uv = shutil.which("uv") or "uv"
    text = vorlage.read_text().replace("__REPO__", str(pfad())).replace(" uv run", f" {uv} run")
    aktion = (getattr(args, "ziel", []) or [""])[0]
    if aktion not in ("einrichten", "entfernen"):
        print("fehler: Nutze zeitplan einrichten oder entfernen.")
        return 2
    if args.trocken:
        print(f"ok: trocken {aktion}\n{text}")
        return 0
    if input(f"Zeitplan wirklich {aktion}? [ja] ").strip().lower() != "ja":
        print("nichts: abgebrochen.")
        return 0
    try:
        if aktion == "einrichten":
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(text)
            subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(ziel)], check=True)
        else:
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(ziel)], check=False)
            ziel.unlink(missing_ok=True)
        print(f"ok: Zeitplan {aktion}.")
        return 0
    except Exception as e:
        print(f"fehler: Zeitplan {aktion} fehlgeschlagen: {e}")
        return 1
