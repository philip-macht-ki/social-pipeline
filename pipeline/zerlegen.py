"""uv run pipeline zerlegen [take …] [--neu]

Themenabschnitte per Modell prüfen und als Rezepte arbeit/<take>/stuecke/<nn>/
rezept.json schreiben.
"""
from __future__ import annotations

from . import urteil
from .kern import Ergebnis, konfig, lesen, schreiben, takes


def geschnittene_dauer(saetze: list[dict], von: int, bis: int) -> float:
    """Länge eines Stücks nach dem Kürzen langer Pausen."""
    teil = saetze[von:bis + 1]
    if not teil:
        return 0
    pausen = sum(max(0, float(b["s"]) - float(a["e"]) - .28)
                 for a, b in zip(teil, teil[1:]) if float(b["s"]) - float(a["e"]) >= .9)
    return float(teil[-1]["e"]) - float(teil[0]["s"]) - pausen


def bereinige(kandidaten: list[dict], saetze: list[dict], min_laenge: float, max_laenge: float) -> list[dict]:
    """Modellgrenzen bleiben Satznummern. Das verhindert Satzbruch vom 23.09.2026:
    Das Modell schnitt Zehntelsekunden neben einer Satzgrenze, wodurch Stücke
    mitten im Satz begannen oder endeten."""
    aus = []
    for k in sorted(kandidaten, key=lambda x: (int(x.get("von_satz", 0)), int(x.get("bis_satz", 0)))):
        k = dict(k)
        k["von_satz"] = max(0, int(k["von_satz"]))
        k["bis_satz"] = min(len(saetze) - 1, int(k["bis_satz"]))
        if k["bis_satz"] < k["von_satz"]:
            continue
        if aus and k["von_satz"] <= aus[-1]["bis_satz"]:
            # Überlappung über die Hälfte des kleineren Stücks: zusammenlegen statt trennen.
            ueberlappung = aus[-1]["bis_satz"] - k["von_satz"] + 1
            kleinstes = min(k["bis_satz"] - k["von_satz"] + 1, aus[-1]["bis_satz"] - aus[-1]["von_satz"] + 1)
            if ueberlappung / kleinstes > .5:
                aus[-1]["bis_satz"] = max(aus[-1]["bis_satz"], k["bis_satz"])
                continue
            k["von_satz"] = aus[-1]["bis_satz"] + 1
        aus.append(k)
    i = 0
    while i < len(aus):
        if geschnittene_dauer(saetze, aus[i]["von_satz"], aus[i]["bis_satz"]) < min_laenge and len(aus) > 1:
            nachbar = i - 1 if i == len(aus) - 1 else i + 1
            a, b = sorted((i, nachbar))
            aus[a]["bis_satz"] = aus[b]["bis_satz"]
            aus.pop(b)
            i = 0
            continue
        i += 1
    return [k for k in aus if geschnittene_dauer(saetze, k["von_satz"], k["bis_satz"]) <= max_laenge]


def _rueckfall(saetze):
    """Ohne Modell: an Pausen ab 2 Sekunden trennen, statt nichts zu liefern."""
    pausen_ab_index = [i + 1 for i, (a, b) in enumerate(zip(saetze, saetze[1:]))
                       if float(b["s"]) - float(a["e"]) >= 2]
    grenzen = [0] + pausen_ab_index + [len(saetze)]
    return {"stuecke": [{"von_satz": a, "bis_satz": b - 1, "titel": saetze[a]["text"][:60],
                          "aussage": saetze[a]["text"], "schluss": ""}
                         for a, b in zip(grenzen, grenzen[1:]) if a < b], "reste": []}


def verarbeite(take, neu=False):
    if any((take / "stuecke").glob("*/rezept.json")) and not neu:
        return Ergebnis("nichts", f"nichts: {take.name} ist schon zerlegt")
    saetze = lesen(take / "saetze.json", [])
    if not saetze:
        return Ergebnis("fehler", f"fehler: {take.name} hat keine Sätze")
    nummeriert = "\n".join(f'{s["nr"]}: {s["s"]:.2f}-{s["e"]:.2f} {s["text"]}' for s in saetze)
    try:
        def _pruefe(x):
            return None if isinstance(x, dict) and isinstance(x.get("stuecke"), list) else "stuecke fehlt"

        antwort = urteil.frage(urteil.vorlage("zerlegen", saetze=nummeriert), zweck="zerlegen",
            rueckfall=lambda: _rueckfall(saetze), pruefe=_pruefe)
        cfg = konfig("pipeline")["schnitt"]
        stuecke = bereinige(antwort.get("stuecke", []), saetze, cfg["min_laenge"], cfg["max_laenge"])
        reste = []
        benutzt = {n for k in stuecke for n in range(k["von_satz"], k["bis_satz"] + 1)}
        for n, s in enumerate(saetze):
            if n not in benutzt:
                reste.append({"text": s["text"], "s": s["s"], "e": s["e"], "grund": "nicht im Stück"})
        schreiben(take / "reste.json", reste)
        befunde = []
        deckung = len(benutzt) / len(saetze)
        if deckung < .75:
            befunde.append(f"Nur {deckung:.0%} der Sätze abgedeckt.")
        for nr, k in enumerate(stuecke, 1):
            teil = saetze[k["von_satz"]:k["bis_satz"] + 1]
            # Modelltext kann typografische Gedankenstriche liefern, die Vorlage erlaubt sie nicht.
            sauber = lambda x: str(x).replace("–", ",").replace("—", ",")
            rezept = {
                "id": f"{take.name}-{nr:02d}", "take": take.name, "nr": nr,
                "von_stuecken": len(stuecke), "von_satz": k["von_satz"], "bis_satz": k["bis_satz"],
                "s": teil[0]["s"], "e": teil[-1]["e"],
                "titel": sauber(k.get("titel", "")), "aussage": sauber(k.get("aussage", "")),
                "hook": None, "stil": {}, "schluss": sauber(k.get("schluss", "")),
                "status": "befund" if befunde else "zerlegt", "befunde": befunde,
            }
            schreiben(take / "stuecke" / f"{nr:02d}" / "rezept.json", rezept)
        return Ergebnis("befund" if befunde else "ok", f"{'befund' if befunde else 'ok'}: "
                         f"{take.name} in {len(stuecke)} Stücke zerlegt")
    except Exception as e:
        return Ergebnis("fehler", f"fehler: Zerlegen {take.name}: {e}")


def befehl(args):
    es = [verarbeite(t, args.neu) for t in takes() if not args.ziel or t.name in args.ziel]
    es = es or [Ergebnis("nichts", "nichts: kein Take zum Zerlegen")]
    for e in es:
        print(e.meldung)
    return int(any(e.status == "fehler" for e in es))
