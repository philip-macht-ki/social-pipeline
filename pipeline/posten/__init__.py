"""uv run pipeline posten [--echt] [--kanal x]

Nimmt fällige, freigegebene Planeinträge und veröffentlicht sie über den Weg,
der in konfig/kanaele.toml je Plattform steht. Ohne --echt ist es ein
Trockenlauf: Die vollständige Anfrage (ohne Schlüssel) landet im Protokoll
und auf dem Bildschirm, gesendet wird nichts, und am Plan ändert sich nichts.

Was vor jedem echten Senden geprüft wird, und woher die Regel stammt:
- Schon gesendet? Schlüssel ist (kanal, plan_id). Im Vorbild stand dieselbe
  Nummer für YouTube und Instagram im Protokoll, und Instagram übersprang zwei
  Beiträge, weil es nicht nach Kanal filterte (22.09.2026).
- Vor dem Senden steht ein "laeuft"-Eintrag im Protokoll. Ein zweiter Lauf,
  der gleichzeitig startet, sieht ihn und sendet nicht doppelt.
- Tagesdeckel und Mindestabstand gegen das Protokoll, nicht nur gegen den Plan.
  Nachholer mit 25 bis 40 Minuten Abstand kamen im Vorbild auf 2 bis 12 Konten
  Reichweite (23.09.2026); YouTube-Flut mit 28 Uploads an einem Tag (22.09.2026).
- Datei da, Videolänge messbar. Ohne Länge kein Upload (ein 186-s-Stück ging
  sonst als "Short" raus, 25.09.2026).
- Upload läuft bei Upload-Post noch: nicht neu senden, im nächsten Lauf
  nachfragen (TikTok-Doppel, 26.09.2026).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..kern import Sperre, dauer, jetzt, konfig, lesen, pfad, schreiben

ERLEDIGT = ("laeuft", "offen", "ok")  # zählt als gesendet oder unterwegs
FAELLIG_HOECHSTENS = timedelta(hours=12)
# Ab hier gilt ein "laeuft"-Eintrag ohne Nachfolger als abgestürzt, nicht als noch unterwegs.
HAENGEND_NACH = timedelta(minutes=30)


def _protokoll() -> list[dict]:
    return lesen(pfad("arbeit", "postlog.json"), []) or []


def _plan() -> dict:
    return lesen(pfad("arbeit", "plan.json"), {"eintraege": []}) or {"eintraege": []}


def _datei(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else pfad(p)


def _letzter(log: list[dict], kanal: str, plan_id: str) -> dict | None:
    echte = [x for x in log if x.get("kanal") == kanal and x.get("plan_id") == plan_id and not x.get("trocken")]
    return echte[-1] if echte else None


def _gesendet_seit(log: list[dict], kanal: str, seit: datetime) -> list[datetime]:
    zeiten = []
    for x in log:
        if x.get("kanal") != kanal or x.get("trocken") or x.get("status") not in ERLEDIGT:
            continue
        try:
            t = datetime.fromisoformat(x["zeit"])
        except (KeyError, ValueError):
            continue
        if t >= seit:
            zeiten.append(t)
    return zeiten


def _grenzen_ok(log: list[dict], kanal: str, now: datetime) -> str | None:
    """Gibt einen Grund zurück, warum jetzt nicht gesendet werden darf, oder None."""
    k = konfig("kanaele").get(kanal, {})
    tag = _gesendet_seit(log, kanal, now.replace(hour=0, minute=0, second=0, microsecond=0))
    if len(tag) >= k.get("tagesdeckel", 99):
        return f"Tagesdeckel {k['tagesdeckel']} für {kanal} erreicht"
    if kanal == "youtube":
        grenze = k.get("max_uploads_24h", 3)
        if len(_gesendet_seit(log, kanal, now - timedelta(hours=24))) >= grenze:
            return f"YouTube: schon {grenze} Uploads in 24 Stunden"
    abstand = k.get("mindestabstand_minuten", 0)
    if abstand and tag:
        letzte = max(_gesendet_seit(log, kanal, now - timedelta(days=1)))
        if now - letzte < timedelta(minutes=abstand):
            return f"Mindestabstand {abstand} min auf {kanal} noch nicht um"
    return None


def _weg(kanal: str) -> str:
    return konfig("kanaele").get(kanal, {}).get("weg", "upload_post")


def _geschwaerzt(e: dict) -> dict:
    from . import upload_post
    if _weg(e["kanal"]) == "upload_post":
        return upload_post.geschwaerzt(e)
    return {"weg": _weg(e["kanal"]), "dateien": [Path(d).name for d in e.get("dateien", [])],
            "text_anfang": (e.get("text") or e.get("titel") or "")[:80]}


def _senden(e: dict) -> dict:
    weg = _weg(e["kanal"])
    if weg == "instagram_api":
        from .instagram import senden
    elif weg == "youtube_api":
        from .youtube import senden
    elif weg == "upload_post":
        from .upload_post import senden
    else:
        raise RuntimeError(f"Unbekannter Weg '{weg}' für {e['kanal']} in konfig/kanaele.toml")
    antwort = senden(e)
    antwort.setdefault("zustand", "ok")
    return antwort


def _pruefe_dateien(e: dict) -> None:
    if e.get("art") == "text":
        return
    if not e.get("dateien"):
        raise RuntimeError("Planeintrag ohne Datei")
    for d in e["dateien"]:
        if not _datei(d).exists():
            raise RuntimeError(f"Datei fehlt: {d}")
    if e["art"] in ("reel", "short", "video"):
        laenge = dauer(_datei(e["dateien"][0]))
        if laenge <= 0:
            raise RuntimeError("Videolänge nicht messbar, kein Upload ohne Länge")
        if e["kanal"] == "youtube" and laenge > konfig("kanaele").get("youtube", {}).get("max_laenge_s", 179):
            raise RuntimeError(f"{laenge:.0f} s ist zu lang für ein Short")


def _offene_nachfragen(log: list[dict], plan: dict) -> None:
    """Uploads, die Upload-Post noch verarbeitet hat, einmal je Lauf nachfragen."""
    from . import upload_post
    eintraege = {e["id"]: e for e in plan.get("eintraege", [])}
    for x in list(log):
        if x.get("status") != "offen" or x.get("trocken"):
            continue
        if _letzter(log, x["kanal"], x["plan_id"]) is not x:
            continue
        try:
            stand = upload_post.nachfragen(x["extern_id"], x["kanal"])
        except Exception as fehler:
            print(f"befund: Nachfrage {x['plan_id']} ({x['kanal']}) klappte nicht: {fehler}")
            continue
        if stand["zustand"] == "offen":
            continue
        neu = {"plan_id": x["plan_id"], "kanal": x["kanal"], "zeit": jetzt().isoformat(timespec="seconds"),
               "status": "ok" if stand["zustand"] == "ok" else "fehler", "trocken": False,
               "weg": "upload_post", "extern_id": x["extern_id"], "url": stand.get("url"),
               "antwort": stand.get("antwort")}
        if stand.get("meldung"):
            neu["fehler"] = stand["meldung"]
        log.append(neu)
        if x["plan_id"] in eintraege:
            eintraege[x["plan_id"]]["status"] = "veroeffentlicht" if neu["status"] == "ok" else "fehler"
        print(f"{neu['status']}: {x['plan_id']} auf {x['kanal']} ist jetzt {stand['zustand']}")


def _haengend_klaeren(e: dict, vorher: dict, log: list[dict]) -> None:
    """Ein 'laeuft'-Eintrag ohne Nachfolger, mindestens HAENGEND_NACH alt: der Lauf, der
    ihn geschrieben hat, ist vermutlich abgestürzt, bevor die Antwort ankam. Neu senden
    würde einen Doppelpost riskieren, also nur bei Upload-Post mit bekannter Kennung
    nachfragen; sonst zur Prüfung markieren, statt still zu warten oder blind erneut
    zu senden."""
    kennung = vorher.get("extern_id")
    if vorher.get("weg") == "upload_post" and kennung:
        from . import upload_post
        try:
            stand = upload_post.nachfragen(kennung, e["kanal"])
        except Exception as fehler:
            print(f"befund: Nachfrage zum hängenden Lauf {e['id']} klappte nicht: {fehler}")
        else:
            if stand["zustand"] != "offen":
                zeit = jetzt().isoformat(timespec="seconds")
                status = "ok" if stand["zustand"] == "ok" else "fehler"
                log.append({"plan_id": e["id"], "kanal": e["kanal"], "zeit": zeit, "status": status,
                            "trocken": False, "weg": "upload_post", "extern_id": kennung,
                            "url": stand.get("url"), "antwort": stand.get("antwort")})
                e["status"] = "veroeffentlicht" if stand["zustand"] == "ok" else "fehler"
                print(f"{'ok' if stand['zustand'] == 'ok' else 'fehler'}: {e['id']} auf {e['kanal']} "
                      f"war hängend, jetzt über Upload-Post geklärt")
                return
    meldung = ("Senden wurde unterbrochen. Auf der Plattform nachsehen, ob der Beitrag online ist, "
               f"dann `pipeline freigeben {e['id']}` erneut oder den Eintrag löschen.")
    log.append({"plan_id": e["id"], "kanal": e["kanal"], "zeit": jetzt().isoformat(timespec="seconds"),
                "status": "unklar", "trocken": False, "weg": vorher.get("weg")})
    e["status"] = "pruefen"
    e.setdefault("befunde", []).append(meldung)
    print(f"befund: {e['id']} auf {e['kanal']}: {meldung}")


def _befehl(args) -> int:
    echt = bool(getattr(args, "echt", False))
    nur = getattr(args, "kanal", None)
    plan, log, now = _plan(), _protokoll(), jetzt()
    if echt:
        _offene_nachfragen(log, plan)
    gesendet = fehler = 0
    for e in plan.get("eintraege", []):
        if nur and e.get("kanal") != nur:
            continue
        if e.get("status") != "geplant" or not e.get("freigegeben"):
            continue
        zeit = datetime.fromisoformat(e["zeit"])
        if zeit > now:
            continue
        if now - zeit > FAELLIG_HOECHSTENS:
            # Trockenlauf meldet nur, er ändert den Plan nicht (sonst verändert eine
            # Sichtung ungewollt den Stand, bevor überhaupt echt gesendet wurde).
            print(f"befund: {e['id']} ({e['kanal']}) ist über 12 Stunden überfällig, "
                  f"`pipeline planen` legt ihn neu ein.")
            if echt:
                e["status"] = "verpasst"
            continue
        vorher = _letzter(log, e["kanal"], e["id"])
        if vorher and vorher.get("status") in ERLEDIGT:
            haengt = (vorher["status"] == "laeuft"
                      and now - datetime.fromisoformat(vorher["zeit"]) > HAENGEND_NACH)
            if echt and haengt:
                _haengend_klaeren(e, vorher, log)
            else:
                print(f"nichts: {e['id']} ist auf {e['kanal']} schon {vorher['status']}")
            continue
        try:
            _pruefe_dateien(e)
            if echt:
                grund = _grenzen_ok(log, e["kanal"], now)
                if grund:
                    print(f"nichts: {e['id']} wartet, {grund}")
                    continue
        except Exception as x:
            print(f"fehler: {e['id']}: {x}")
            e.setdefault("befunde", []).append(str(x))
            fehler += 1
            continue

        eintrag = {"plan_id": e["id"], "kanal": e["kanal"], "zeit": now.isoformat(timespec="seconds"),
                   "weg": _weg(e["kanal"]), "anfrage": _geschwaerzt(e)}
        if not echt:
            log.append(eintrag | {"status": "trocken", "trocken": True})
            print(f"trocken: {e['id']} {e['kanal']} {e['art']} -> {eintrag['anfrage'].get('url', eintrag['weg'])}")
            continue

        log.append(eintrag | {"status": "laeuft", "trocken": False})
        schreiben(pfad("arbeit", "postlog.json"), log)  # sofort, gegen Doppelpost
        try:
            antwort = _senden(e)
            status = "offen" if antwort.get("zustand") == "offen" else "ok"
            log.append(eintrag | {"status": status, "trocken": False, "extern_id": antwort.get("extern_id"),
                                  "url": antwort.get("url"), "antwort": antwort.get("antwort"),
                                  "zeit": jetzt().isoformat(timespec="seconds")})
            e["status"] = "veroeffentlicht" if status == "ok" else "geplant"
            gesendet += 1
            print(f"{status}: {e['id']} auf {e['kanal']} {antwort.get('url') or antwort.get('extern_id') or ''}")
        except Exception as x:
            log.append(eintrag | {"status": "fehler", "trocken": False, "fehler": str(x)[:500],
                                  "zeit": jetzt().isoformat(timespec="seconds")})
            e["status"] = "fehler"
            e.setdefault("befunde", []).append(str(x)[:200])
            fehler += 1
            print(f"fehler: {e['id']} auf {e['kanal']}: {x}")
        schreiben(pfad("arbeit", "postlog.json"), log)

    schreiben(pfad("arbeit", "postlog.json"), log)
    schreiben(pfad("arbeit", "plan.json"), plan)
    art = "gesendet" if echt else "im Trockenlauf gezeigt"
    print(f"ok: {gesendet if echt else 'alle fälligen'} Einträge {art}, {fehler} Fehler")
    return 1 if fehler else 0


def befehl(args) -> int:
    """Eigene Sperre, eigener Name: `tag` hält Sperre("lauf") und ruft diesen Befehl
    trotzdem auf, ein zweiter manueller `posten`-Lauf nebenher darf sich aber nicht
    mit einem laufenden `posten` überschneiden (sonst sehen beide denselben Plan und
    dasselbe Protokoll noch ohne den anderen Eintrag und senden doppelt)."""
    try:
        with Sperre("posten"):
            return _befehl(args)
    except RuntimeError:
        print("nichts: ein anderer Veröffentlichungslauf ist aktiv")
        return 0
