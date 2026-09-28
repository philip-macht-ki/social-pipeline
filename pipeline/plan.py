"""uv run pipeline planen [--tage n] / zeigen / freigeben <id…|--alle>

Verteilt fertige Stücke und Bildbeiträge auf freie, regelkonforme Sendeplätze
aus konfig/kanaele.toml und schreibt arbeit/plan.json.

Einträge mit Status "fehler" oder "verpasst" zählen nicht als vorhandene
Planung: Ihre (Kanal, Quelle, Teil, Art) bleibt frei, also plant der nächste
Lauf denselben Beitrag neu ein, statt ihn für immer als erledigt zu behandeln.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .kern import jetzt, konfig, lesen, pfad, schreiben, zone

# Diese Status zählen nicht als "schon geplant": ein verpasster oder
# gescheiterter Beitrag soll beim nächsten `planen` neu versucht werden.
NICHT_ENDGUELTIG = ("fehler", "verpasst")


def _plan() -> dict:
    return lesen(pfad("arbeit", "plan.json"), {"eintraege": []})


def _speichern(daten: dict) -> None:
    schreiben(pfad("arbeit", "plan.json"), daten)


def _dt(zeit: str) -> datetime:
    return datetime.fromisoformat(zeit).astimezone(zone())


def _art(art: str) -> str:
    """Bildet Sonderarten auf bild/reel ab. Ein Bildplatz nimmt Bild, Karussell,
    Pin oder Fotobeitrag: das sind alles Standbild-Beiträge."""
    return {"pin": "bild", "fotobeitrag": "bild", "karussell": "bild",
            "short": "reel", "video": "reel"}.get(art, art)


def _in_nachtruhe(zeit: datetime, nachtruhe: list[str] | None) -> bool:
    """True, wenn die lokale Uhrzeit im (auch über Mitternacht gehenden) Ruhefenster liegt."""
    if not nachtruhe or len(nachtruhe) != 2:
        return False
    start, ende = (datetime.strptime(x, "%H:%M").time() for x in nachtruhe)
    if start == ende:
        return False
    uhr = zeit.timetz().replace(tzinfo=None)
    return start <= uhr < ende if start < ende else (uhr >= start or uhr < ende)


def _kandidaten() -> list[dict]:
    """Liest nur fertige Manifestdaten. Befunde bleiben bewusst planbar, 22.09.2026."""
    raus = []
    for f in sorted(pfad("ausgabe").glob("*/stueck.json")):
        d = lesen(f, {})
        if d.get("status") not in ("fertig", "befund"):
            continue
        tex = lesen(f.parent / "texte.json", {})
        for kanal, datei in d.get("dateien", {}).items():
            if kanal not in konfig("kanaele"):
                continue
            text_dieses_kanals = tex.get(kanal, {}) or {}
            raus.append({
                "quelle": d.get("id", f.parent.name),
                "take": d.get("id", f.parent.name).rsplit("-", 1)[0],
                "teil": d.get("nr", 1),
                "von_teilen": d.get("von_stuecken", 1),
                "kanal": kanal,
                "art": "short" if kanal == "youtube" else "reel",
                "dateien": [str(f.parent / datei)],
                "text": text_dieses_kanals.get("caption", text_dieses_kanals.get("beschreibung", "")),
                "titel": text_dieses_kanals.get("titel", ""),
                "dauer_s": d.get("dauer_s", 0),
                "befunde": list(d.get("befunde", [])) + list(tex.get("befunde", [])),
            })
    for f in sorted(pfad("ausgabe", "bilder").glob("*/bild.json")):
        d = lesen(f, {})
        if d.get("status") not in ("fertig", "befund"):
            continue
        kanal, art = d.get("plattform"), d.get("art")
        if not kanal or kanal not in konfig("kanaele"):
            continue
        text = d.get("texte", {}).get(kanal, {})
        raus.append({
            "quelle": d.get("id", f.parent.name),
            "take": d.get("take", d.get("id", "").split("-")[0]),
            "teil": d.get("nr", 1),
            "von_teilen": 1,
            "kanal": kanal,
            "art": art,
            "dateien": [str(f.parent / x) for x in d.get("dateien", [])],
            "text": text.get("text", text.get("beschreibung", "")),
            "titel": text.get("titel", ""),
            "dauer_s": 0,
            "befunde": d.get("befunde", []),
        })
    return raus


def _erlaubt(kandidat: dict, zeit: datetime, eintraege: list[dict], cfg: dict, take_regel: bool = True) -> bool:
    if kandidat["kanal"] == "threads" and kandidat["art"] in ("reel", "video", "short"):
        return False
    if kandidat["kanal"] == "youtube" and kandidat.get("dauer_s", 0) > cfg.get("max_laenge_s", 179):
        return False
    if _in_nachtruhe(zeit, cfg.get("nachtruhe")):
        return False
    # Verpasste oder gescheiterte Zeilen sperren keinen Nachbarslot mehr, sonst
    # bliebe ihr alter Platz für immer blockiert, obwohl niemand dort gesendet hat.
    gleiche = [e for e in eintraege
               if e["kanal"] == kandidat["kanal"] and e.get("status") not in NICHT_ENDGUELTIG]
    tag = [e for e in gleiche if _dt(e["zeit"]).date() == zeit.date()]
    if len(tag) >= cfg.get("tagesdeckel", 99):
        return False
    abstand = cfg.get("mindestabstand_minuten", 0)
    if abstand and any(abs((_dt(e["zeit"]) - zeit).total_seconds()) < abstand * 60 for e in gleiche):
        return False
    # Reihenfolge und Nachbarschaft gelten auch beim Vorziehen.
    vorher = sorted((e for e in gleiche if _dt(e["zeit"]) < zeit), key=lambda e: e["zeit"])
    nachher = sorted((e for e in gleiche if _dt(e["zeit"]) > zeit), key=lambda e: e["zeit"])

    def gleiches_take(e: dict | None) -> bool:
        if not e or e.get("take") != kandidat["take"]:
            return False
        # Aufeinanderfolgende Teile desselben Mehrteilers sind die ausdrücklich erlaubte Ausnahme.
        beide_mehrteilig = kandidat.get("von_teilen", 1) > 1 and e.get("von_teilen", 1) > 1
        direkt_benachbart = abs(e.get("teil", 1) - kandidat.get("teil", 1)) == 1
        return not (beide_mehrteilig and direkt_benachbart)

    # Abwechslung ist eine Vorliebe, keine Sperre: befehl_planen versucht erst
    # alle Kandidaten mit dieser Regel und lockert sie nur, wenn sonst ein Platz
    # leer bliebe. Mit nur einer Aufnahme ginge sonst je Kanal genau ein Beitrag
    # raus (Befund im ersten Gesamtlauf, 28.09.2026).
    if take_regel and (gleiches_take(vorher[-1] if vorher else None)
                       or gleiches_take(nachher[0] if nachher else None)):
        return False
    if kandidat.get("von_teilen", 1) > 1:
        if any(e.get("take") == kandidat["take"] and e.get("teil") == kandidat["teil"] for e in gleiche):
            return False
        if kandidat["teil"] > 1 and not any(
                e.get("take") == kandidat["take"] and e.get("teil") == kandidat["teil"] - 1
                and _dt(e["zeit"]) < zeit for e in gleiche):
            return False
    if kandidat["kanal"] == "instagram" and _art(kandidat["art"]) in ("bild", "karussell"):
        if vorher and _art(vorher[-1]["art"]) in ("bild", "karussell"):
            return False
    return True


def vorziehen(args) -> int:
    """Füllt freie zukünftige Slots durch regelkonformes Vorziehen noch unveröffentlichter Planzeilen."""
    daten = _plan()
    eintraege = daten.setdefault("eintraege", [])
    kanaele = konfig("kanaele")
    start = jetzt().replace(second=0, microsecond=0)
    tage = getattr(args, "tage", None) or konfig("pipeline").get("plan", {}).get("tage", 7)
    gezogen = 0
    for tag in range(tage):
        datum = (start + timedelta(days=tag)).date()
        for kanal, cfg in kanaele.items():
            if not cfg.get("an", False):
                continue
            for slot, sd in enumerate(cfg.get("slots", []), 1):
                zeit = datetime.fromisoformat(f"{datum}T{sd['zeit']}").replace(tzinfo=zone())
                schon_belegt = any(e.get("kanal") == kanal and _dt(e["zeit"]) == zeit for e in eintraege)
                if zeit <= start or schon_belegt:
                    continue
                moeglich = sorted(
                    (e for e in eintraege if e.get("kanal") == kanal and e.get("status") == "geplant"
                     and _dt(e["zeit"]) > zeit and _art(e.get("art")) == _art(sd.get("art", "reel"))),
                    key=lambda e: e["zeit"])
                for e in moeglich:
                    ohne_diesen = [x for x in eintraege if x is not e]
                    if _erlaubt(e, zeit, ohne_diesen, cfg):
                        e["zeit"] = zeit.isoformat()
                        e["slot"] = slot
                        gezogen += 1
                        break
    if gezogen:
        _speichern(daten)
    return gezogen


def befehl_planen(args) -> int:
    daten = _plan()
    eintraege = daten.setdefault("eintraege", [])
    kanaele = konfig("kanaele")
    horizon = getattr(args, "tage", None) or konfig("pipeline").get("plan", {}).get("tage", 7)
    # Nur endgültige Einträge zählen als "schon geplant" (siehe Moduldocstring).
    vorhandene = {(e["kanal"], e.get("quelle"), e.get("teil", 1), e.get("art"))
                  for e in eintraege if e.get("status") not in NICHT_ENDGUELTIG}
    kandidaten = [k for k in _kandidaten() if (k["kanal"], k["quelle"], k.get("teil", 1), k.get("art"))
                  not in vorhandene]
    vorhandene_nummern = [int(e["id"].split("-")[-1]) for e in eintraege
                           if str(e.get("id", "")).startswith("p-")]
    naechste_nr = max(vorhandene_nummern or [0]) + 1
    gesetzt = 0
    start = jetzt().replace(second=0, microsecond=0)
    pauschal_frei = konfig("pipeline").get("freigabe", {}).get("pauschal", False)
    for tag in range(horizon):
        datum = (start + timedelta(days=tag)).date()
        for kanal, cfg in kanaele.items():
            if not cfg.get("an", False):
                continue
            for slot, sd in enumerate(cfg.get("slots", []), 1):
                zeit = datetime.fromisoformat(f"{datum}T{sd['zeit']}").replace(tzinfo=zone())
                if zeit <= start:
                    continue
                # FIFO je Art: erste passende Warteschlangenposition gewinnt. Erst mit
                # der Abwechslungsregel, dann ohne, damit kein Platz leer bleibt.
                passend = [(i, k) for i, k in enumerate(kandidaten)
                           if k["kanal"] == kanal and _art(k["art"]) == _art(sd.get("art", "reel"))]
                wahl = next(((i, k) for i, k in passend if _erlaubt(k, zeit, eintraege, cfg)), None)
                if wahl is None:
                    wahl = next(((i, k) for i, k in passend
                                 if _erlaubt(k, zeit, eintraege, cfg, take_regel=False)), None)
                for i, k in [wahl] if wahl else []:
                    eintrag = {feld: k[feld] for feld in
                               ("quelle", "take", "teil", "von_teilen", "kanal", "art", "dateien", "text",
                                "titel", "befunde")}
                    eintrag.update({
                        "id": f"p-{naechste_nr:04d}", "zeit": zeit.isoformat(), "slot": slot,
                        "freigegeben": pauschal_frei,
                        "freigegeben_am": jetzt().isoformat() if pauschal_frei else None,
                        "status": "geplant",
                    })
                    eintraege.append(eintrag)
                    kandidaten.pop(i)
                    naechste_nr += 1
                    gesetzt += 1
                    break
    _speichern(daten)
    vorgezogen = vorziehen(args)
    meldung = f"ok: {gesetzt} Planeinträge angelegt."
    if vorgezogen:
        meldung += f" {vorgezogen} vorgezogen."
    print(meldung)
    if kandidaten:
        print(f"befund: {len(kandidaten)} fertige Beiträge fanden keinen passenden Slot.")
    return 0


def befehl_zeigen(args) -> int:
    # "pruefen" sind Einträge mit hängendem Senden (Absturz mitten im Lauf, siehe posten/__init__.py):
    # ob der Beitrag online ist, muss von Hand auf der Plattform nachgesehen werden.
    offen = [e for e in _plan().get("eintraege", []) if e.get("status") in ("geplant", "laeuft", "pruefen")]
    if not offen:
        print("nichts: Keine offenen Planeinträge.")
        return 0
    for e in sorted(offen, key=lambda x: x["zeit"]):
        befunde = ", ".join(e.get("befunde", [])) or "keine"
        print(f"{e['id']} {e['zeit']} {e['kanal']} {e['art']} {', '.join(e.get('dateien', []))} | "
              f"{e.get('text', '')[:90]} | Befunde: {befunde}")
    return 0


def befehl_freigeben(args) -> int:
    daten = _plan()
    ziele = set(getattr(args, "ziel", []) or [])
    alle = getattr(args, "alle", False)
    freigegeben = 0
    for e in daten.get("eintraege", []):
        if not e.get("freigegeben") and (alle or e["id"] in ziele):
            e["freigegeben"] = True
            e["freigegeben_am"] = jetzt().isoformat()
            freigegeben += 1
    _speichern(daten)
    print(f"ok: {freigegeben} Planeinträge freigegeben.")
    return 0
