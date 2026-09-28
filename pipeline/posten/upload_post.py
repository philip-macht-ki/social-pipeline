"""Veröffentlichen über Upload-Post (upload-post.com): ein Schlüssel für viele Plattformen.

Warum dieser Weg: TikTok stellt ohne eigenes Audit jeden Beitrag über die eigene
Schnittstelle nur privat ein, und das App-Postfach kürzte im Vorbild 16 von 17
Videos auf 0 bis 28 Sekunden (25.09.2026). Upload-Post hat ein geprüftes TikTok-
Konto und nimmt dieselben Dateien für Pinterest, Threads, Instagram und mehr.

Feldnamen wie im laufenden Vorbild (Stand 28.09.2026) und in der Doku:
https://docs.upload-post.com/api/reference/

Der Schlüssel steht nur im Header und nie im Protokoll.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

from ..kern import konfig, pfad

API = "https://api.upload-post.com/api"


def _kopf() -> dict:
    schluessel = os.environ.get("UPLOAD_POST_KEY", "")
    if not schluessel:
        raise RuntimeError("UPLOAD_POST_KEY fehlt in .env (Modul S5, Lektion 1).")
    return {"Authorization": f"Apikey {schluessel}"}


def _datei(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else pfad(p)


def anfrage(e: dict) -> tuple[str, list[tuple[str, str]], list[Path]]:
    """Baut (Endpunkt, Formularfelder, Dateien) für einen Planeintrag, ohne zu senden."""
    kanal, art = e["kanal"], e["art"]
    k = konfig("kanaele").get(kanal, {})
    text = e.get("text", "") or ""
    titel = (e.get("titel") or next((z for z in text.splitlines() if z.strip()), ""))[:100]
    dateien = [_datei(x) for x in e.get("dateien", [])]
    felder: list[tuple[str, str]] = [
        ("user", os.environ.get("UPLOAD_POST_USER", "")),
        ("platform[]", kanal),
        # Ohne Termin sofort senden, aber nicht auf das Ende des Uploads warten:
        # die Antwort bringt eine request_id, deren Stand der nächste Lauf abfragt.
        ("async_upload", "true"),
    ]

    if kanal == "tiktok":
        # Ohne eigenes TikTok-Audit stellt TikTok alles privat ein, egal was hier steht.
        sicht = k.get("privacy_level", "SELF_ONLY")
        if art == "fotobeitrag":
            felder += [("tiktok_title", titel[:90]), ("description", text[:4000]),
                       ("auto_add_music", "true"), ("photo_cover_index", "0")]
        else:
            felder += [("tiktok_title", text[:2200]), ("disable_comment", "false"),
                       ("disable_duet", "false"), ("disable_stitch", "false"), ("is_aigc", "false")]
        felder += [("privacy_level", sicht), ("post_mode", "DIRECT_POST")]
    elif kanal == "pinterest":
        board = e.get("board_id") or k.get("board_id", "")
        felder += [("title", titel), ("pinterest_title", titel),
                   ("pinterest_description", text[:500]),
                   ("pinterest_board_id", str(board)),
                   ("pinterest_link", e.get("link") or konfig("marke").get("link", ""))]
    elif kanal == "threads":
        felder += [("title", text[:500]), ("threads_title", text[:500])]
        if k.get("topic_tag"):
            felder.append(("threads_topic_tag", k["topic_tag"]))
    elif kanal == "instagram":
        felder += [("title", text[:2200])]
        if art == "reel":
            felder += [("media_type", "REELS"), ("share_to_feed", "true")]
    else:
        felder += [("title", titel), ("description", text)]

    if art == "text":
        ziel = "/upload_text"
    elif art in ("bild", "karussell", "pin", "fotobeitrag"):
        ziel = "/upload_photos"
    else:
        ziel = "/upload"
    return ziel, felder, dateien


def geschwaerzt(e: dict) -> dict:
    """Die Anfrage so, wie sie ins Protokoll darf: ohne Schlüssel, Profil geschwärzt."""
    ziel, felder, dateien = anfrage(e)
    return {
        "url": API + ziel,
        "felder": [[k, "***" if k == "user" else v] for k, v in felder],
        "dateien": [p.name for p in dateien],
        "header": {"Authorization": "Apikey ***"},
    }


def _antwort(r: requests.Response) -> dict:
    try:
        daten = r.json()
    except ValueError:
        daten = {"roh": r.text[:300]}
    return daten | {"_http": r.status_code}


def _plattform_ergebnis(antwort: dict, kanal: str) -> tuple[str | None, str | None]:
    """Liest results[] aus der Antwort (Feld laut UploadStatusResponse in der API-Doku:
    platform, success, message) für die eigene Plattform. Der äußere Status "completed"
    zählt nur, wie viele Plattformen fertig sind, nicht ob sie geklappt haben — ein
    "completed" mit success: false für die eigene Plattform ist trotzdem ein Fehlschlag.
    Gibt (Fehlermeldung_oder_None, url_oder_None) zurück."""
    ergebnisse = antwort.get("results") if isinstance(antwort.get("results"), list) else []
    eigene = [x for x in ergebnisse if not kanal or x.get("platform") == kanal] or ergebnisse
    fehlgeschlagen = [x for x in eigene if x.get("success") is False]
    if fehlgeschlagen:
        meldung = "; ".join(x.get("message", "") for x in fehlgeschlagen if x.get("message"))
        return meldung or "Plattform meldet Fehlschlag.", None
    url = None
    for ergebnis in eigene:
        url = url or ergebnis.get("post_url") or ergebnis.get("url")
    return None, url


def senden(e: dict) -> dict:
    """Sendet und gibt zurück: {"zustand": "ok"|"offen", "extern_id", "antwort"}.
    Wirft bei einem Fehler mit lesbarer Meldung."""
    ziel, felder, dateien = anfrage(e)
    offen: list = []
    try:
        if ziel == "/upload_text":
            r = requests.post(API + ziel, headers=_kopf(), data=felder, timeout=120)
        elif ziel == "/upload":
            f = open(dateien[0], "rb")
            offen.append(f)
            r = requests.post(API + ziel, headers=_kopf(), data=felder,
                              files={"video": (dateien[0].name, f, "video/mp4")}, timeout=1800)
        else:
            teile = []
            for p in dateien[:35]:
                f = open(p, "rb")
                offen.append(f)
                teile.append(("photos[]", (p.name, f, "image/jpeg")))
            r = requests.post(API + ziel, headers=_kopf(), data=felder, files=teile, timeout=600)
    finally:
        for f in offen:
            f.close()
    antwort = _antwort(r)
    if r.status_code >= 400 or antwort.get("success") is False:
        raise RuntimeError(f"Upload-Post antwortet {r.status_code}: {str(antwort)[:300]}")
    kennung = antwort.get("request_id") or antwort.get("job_id")
    if kennung:
        return {"zustand": "offen", "extern_id": kennung, "antwort": antwort}
    # Keine Kennung: die Antwort ist schon das Endergebnis. Enthält sie bereits
    # Ergebnisse je Plattform, zählt das eigene, nicht der pauschale HTTP-Erfolg.
    fehler, url = _plattform_ergebnis(antwort, e["kanal"])
    if fehler:
        raise RuntimeError(f"Upload-Post meldet Fehlschlag für {e['kanal']}: {fehler}")
    return {"zustand": "ok", "antwort": antwort, "url": url}


def nachfragen(kennung: str, kanal: str | None = None) -> dict:
    """Stand eines laufenden Uploads. {"zustand": "ok"|"offen"|"fehler", "antwort", "url", "meldung"}"""
    feld = "job_id" if str(kennung).startswith("scheduler") else "request_id"
    r = requests.get(API + "/uploadposts/status", headers=_kopf(), params={feld: kennung}, timeout=60)
    antwort = _antwort(r)
    status = str(antwort.get("status", "")).lower()
    text = str(antwort).lower()
    if r.status_code >= 400 or "failed" in text or "error" in text:
        return {"zustand": "fehler", "antwort": antwort}
    laeuft_noch = any(w in text for w in ("pending", "processing", "in_progress", "queued"))
    if status in ("pending", "in_progress") or laeuft_noch:
        return {"zustand": "offen", "antwort": antwort}
    # status == "completed" ist nur die Gesamtzahl (Felder completed/total der
    # UploadStatusResponse); ob GENAU DIESE Plattform ging, steht in results[].success.
    fehler, url = _plattform_ergebnis(antwort, kanal)
    if fehler:
        return {"zustand": "fehler", "antwort": antwort, "meldung": fehler}
    return {"zustand": "ok", "antwort": antwort, "url": url}
