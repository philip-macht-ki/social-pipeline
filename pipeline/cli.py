"""Einstieg: uv run pipeline <befehl> [ziel] [optionen]

Jeder Befehl lebt in seinem Modul als Funktion `befehl(args) -> int`
(Exit-Code). Hier wird nur verteilt. Die Module werden erst beim Aufruf
geladen, damit ein fehlendes Zusatzpaket (etwa für YouTube) nicht jeden
anderen Befehl mitreißt.
"""
from __future__ import annotations

import argparse
import importlib
import sys

# befehl: (modul, funktion, hilfe)
BEFEHLE: dict[str, tuple[str, str, str]] = {
    "pruefen": ("pruefen", "befehl", "Selbsttest: ist alles da, was die Pipeline braucht?"),
    "beispiel": ("beispiel", "befehl", "Erzeugt ein Beispielvideo in eingang/, ohne eigene Aufnahme"),
    "eingang": ("rohmaterial", "befehl_eingang", "Nimmt neue Videos aus eingang/ auf"),
    "transkript": ("transkript", "befehl", "Wortzeiten mit Whisper, lokal"),
    "zerlegen": ("zerlegen", "befehl", "Themenschnitt: aus einer Aufnahme werden Stücke"),
    "hook": ("hook", "befehl", "Stärksten ersten Satz wählen"),
    "bauen": ("video", "befehl_bauen", "Rohschnitt: Pausen raus, Bild und Ton sauber"),
    "fassungen": ("video", "befehl_fassungen", "Fassungen je Plattform mit Untertiteln und Titel"),
    "texte": ("texte", "befehl", "Texte je Plattform"),
    "bilder": ("stile", "befehl", "Bilder, Karussells, Pins, Fotobeiträge, Threads-Texte"),
    "kurzstuecke": ("kurzstuecke", "befehl", "Stille Lese-Reels und übermalte Sätze bauen"),
    "planen": ("plan", "befehl_planen", "Fertiges auf Sendeplätze verteilen"),
    "zeigen": ("plan", "befehl_zeigen", "Offene Planeinträge zum Ansehen auflisten"),
    "freigeben": ("plan", "befehl_freigeben", "Planeinträge freigeben"),
    "posten": ("posten", "befehl", "Fällige, freigegebene Einträge veröffentlichen (trocken ohne --echt)"),
    "vorrat": ("betrieb", "befehl_vorrat", "Geplant gegen Soll, Lücken melden"),
    "status": ("betrieb", "befehl_status", "Kurzübersicht über alles"),
    "verbrauch": ("urteil", "befehl_verbrauch", "Modellurteile und Tokens je Tag (Standard: 7 Tage)"),
    "ki-budget": ("ki_einblendung", "befehl_budget", "KI-Monatsbudget und Buchungen zeigen"),
    "tag": ("tageslauf", "befehl", "Der ganze Lauf in fester Reihenfolge"),
    "zeitplan": ("betrieb", "befehl_zeitplan", "launchd-Job einrichten oder entfernen"),
    "instagram-token": ("posten.instagram", "befehl_token", "Instagram-Token verlängern"),
    "youtube-anmelden": ("posten.youtube", "befehl_anmelden", "YouTube-Zugang einmalig erteilen"),
}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pipeline", description="Deine Social-Media-Pipeline")
    ap.add_argument("befehl", choices=sorted(BEFEHLE), metavar="befehl",
                    help="; ".join(f"{k}: {v[2]}" for k, v in BEFEHLE.items()))
    ap.add_argument("ziel", nargs="*", help="Take, Stück-ID, Plan-ID oder Unterbefehl")
    ap.add_argument("--neu", action="store_true", help="Vorhandenes Ergebnis neu rechnen")
    ap.add_argument("--echt", action="store_true", help="Wirklich senden statt Trockenlauf")
    ap.add_argument("--alle", action="store_true", help="Bei freigeben: alle offenen")
    ap.add_argument("--kanal", help="Nur diese Plattform")
    ap.add_argument("--tage", type=int, help="Planungshorizont in Tagen")
    ap.add_argument("--trocken", action="store_true", help="Nur zeigen, nichts ändern")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    modul, funktion, _ = BEFEHLE[args.befehl]
    try:
        mod = importlib.import_module(f"pipeline.{modul}")
    except ModuleNotFoundError as e:
        print(f"Dieser Befehl braucht ein Zusatzpaket, das fehlt: {e.name}. "
              f"Siehe README, Abschnitt Einrichtung.", file=sys.stderr)
        return 2
    code = getattr(mod, funktion)(args)
    return int(code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
