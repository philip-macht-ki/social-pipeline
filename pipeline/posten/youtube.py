"""YouTube OAuth-Anmeldung und Upload mit Kanalsperre.

Titel und Beschreibung kommen aus texte.py unverändert: kein erzwungenes
"#Shorts" im Titel, YouTube erkennt ein Short an Seitenverhältnis und Länge
allein. Titel und Beschreibung werden hier nur auf die von YouTube erlaubte
Länge gekürzt (100 bzw. 5000 Zeichen), nicht inhaltlich verändert.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from ..kern import konfig, pfad

TITEL_MAX = 100
BESCHREIBUNG_MAX = 5000


def _hinweis_fehlendes_extra(fehler: ModuleNotFoundError) -> str:
    return (f"Für YouTube fehlt das Paket '{fehler.name}'. Einmalig installieren mit: "
            f"`uv sync --extra youtube`.")


def befehl_anmelden(args) -> int:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ModuleNotFoundError as e:
        print(f"fehler: {_hinweis_fehlendes_extra(e)}")
        return 1
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(pfad("arbeit", "youtube_client.json")), ["https://www.googleapis.com/auth/youtube.upload"])
        zugang = flow.run_local_server(port=0)
        pfad("arbeit", "youtube_token.json").write_text(zugang.to_json())
        print("ok: YouTube-Zugang gespeichert.")
        return 0
    except Exception as e:
        print(f"fehler: YouTube-Anmeldung fehlgeschlagen: {e}")
        return 1


def _dienst_bauen():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    zugang = Credentials.from_authorized_user_file(str(pfad("arbeit", "youtube_token.json")))
    return build("youtube", "v3", credentials=zugang)


def senden(e: dict, dienst=None) -> dict:
    if pfad("arbeit", ".youtube_pause").exists():
        raise RuntimeError("YouTube ist durch arbeit/.youtube_pause pausiert.")
    if dienst is None:
        try:
            dienst = _dienst_bauen()
        except ModuleNotFoundError as fehler:
            raise RuntimeError(_hinweis_fehlendes_extra(fehler)) from fehler

    # Kanalsperre zuerst: ein falscher Kanal soll nicht durch einen fehlenden
    # Paket-Import verdeckt werden.
    kanaele = dienst.channels().list(part="id", mine=True).execute().get("items", [])
    kanal_id = kanaele[0].get("id") if kanaele else None
    if not kanaele or kanal_id != os.environ.get("YOUTUBE_KANAL_ID", ""):
        raise RuntimeError("YouTube-Token zeigt nicht auf den konfigurierten Kanal.")

    try:
        from googleapiclient.http import MediaFileUpload
    except ModuleNotFoundError as fehler:
        raise RuntimeError(_hinweis_fehlendes_extra(fehler)) from fehler

    cfg = konfig("kanaele")["youtube"]
    body = {
        "snippet": {
            "title": e.get("titel", "")[:TITEL_MAX],
            "description": e.get("text", "")[:BESCHREIBUNG_MAX],
            "categoryId": cfg.get("kategorie", "22"),
            "defaultLanguage": "de",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": False},
    }
    hochladen = MediaFileUpload(e["dateien"][0], resumable=True)
    antwort = dienst.videos().insert(part="snippet,status", body=body, media_body=hochladen).execute()
    video_id = antwort["id"]

    zeit = datetime.fromisoformat(e["zeit"])
    if zeit > datetime.now(zeit.tzinfo):
        utc_zeit = zeit.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        veroeffentlichen = {"privacyStatus": "private", "publishAt": utc_zeit}
    else:
        veroeffentlichen = {"privacyStatus": "public"}
    dienst.videos().update(part="status", body={"id": video_id, "status": veroeffentlichen}).execute()
    return {"extern_id": video_id, "url": f"https://youtube.com/shorts/{video_id}"}
