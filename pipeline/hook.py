"""uv run pipeline hook [stück-id oder take …] [--neu]

Wählt den stärksten vollständigen Einstiegssatz eines Stücks (den Hook) per
Modell und trägt ihn ins rezept.json ein.
"""
from __future__ import annotations

from . import urteil
from .kern import Ergebnis, lesen, schreiben, stuecke

# Anlaufwörter, die vor einem Hook-Kandidaten wegfallen dürfen ("Also, heute...").
ANLAUF = {"und", "also", "ja", "so", "äh", "ähm", "naja", "genau"}


def kandidaten(saetze):
    """Sätze zwischen 1,4 und 9 Sekunden mit 4 bis 24 Wörtern, je auch ohne Anlauf."""
    aus = []
    for s in saetze:
        woerter = s["text"].split()
        dauer = float(s["e"]) - float(s["s"])
        if not (1.4 <= dauer <= 9 and 4 <= len(woerter) <= 24):
            continue
        aus.append({"von_satz": s["nr"], "text": s["text"], "ab_wort": None})
        n = 0
        while n < min(4, len(woerter)) and woerter[n].lower().strip(",.!?") in ANLAUF:
            n += 1
        if n and len(woerter[n:]) >= 4:
            aus.append({"von_satz": s["nr"], "text": " ".join(woerter[n:]), "ab_wort": n})
    return aus


def vorziehen(punkte, einstieg):
    """Ein Hook lohnt sich nur bei deutlichem Vorsprung vor dem echten Einstieg."""
    return punkte >= 7 and punkte - einstieg >= 2 or einstieg <= 2 and punkte - einstieg >= 4


def verarbeite(ordner, neu=False):
    rezept = lesen(ordner / "rezept.json", {})
    if rezept.get("hook") is not None and not neu:
        return Ergebnis("nichts", f"nichts: {rezept.get('id')} hat schon einen Hook")
    saetze = lesen(ordner.parents[1] / "saetze.json", [])[rezept["von_satz"]:rezept["bis_satz"] + 1]
    ks = kandidaten(saetze)
    if not ks:
        return Ergebnis("befund", f"befund: {rezept['id']} hat keinen Hook-Kandidaten")
    einstieg = {"von_satz": saetze[0]["nr"], "text": saetze[0]["text"]}
    try:
        antwort = urteil.frage(
            urteil.vorlage("hook", kandidaten="\n".join(f'{i}: {k["text"]}' for i, k in enumerate(ks)),
                            einstieg=einstieg["text"]),
            zweck="hook",
            rueckfall=lambda: {"einstieg_punkte": 0, "kandidaten": [
                {"nr": i, "punkte": 0, "grund": "Ohne Modell bleibt der Einstieg."} for i in range(len(ks))]},
            pruefe=lambda x: None if isinstance(x, dict) else "JSON-Objekt fehlt")
        ep = int(antwort.get("einstieg_punkte", 0))
        bewertungen = {int(x.get("nr", -1)): x for x in antwort.get("kandidaten", [])}
        beste = max(range(len(ks)), key=lambda i: int(bewertungen.get(i, {}).get("punkte", 0)))
        b = bewertungen.get(beste, {})
        p = int(b.get("punkte", 0))
        if vorziehen(p, ep):
            hook = {"von_satz": ks[beste]["von_satz"], "punkte": p, "einstieg_punkte": ep,
                    "grund": b.get("grund", "")}
            if ks[beste]["ab_wort"]:
                hook["ab_wort"] = ks[beste]["ab_wort"]
            rezept["hook"] = hook
        else:
            rezept["hook"] = None
        schreiben(ordner / "rezept.json", rezept)
        return Ergebnis("ok", f"ok: Hook für {rezept['id']} geprüft")
    except Exception as e:
        return Ergebnis("fehler", f"fehler: Hook {rezept.get('id')}: {e}")


def befehl(args):
    ziel = [o for o in stuecke() if not args.ziel
            or lesen(o / "rezept.json", {}).get("id") in args.ziel or o.parents[1].name in args.ziel]
    es = [verarbeite(o, args.neu) for o in ziel] or [Ergebnis("nichts", "nichts: kein Stück für Hook")]
    for e in es:
        print(e.meldung)
    return int(any(e.status == "fehler" for e in es))
