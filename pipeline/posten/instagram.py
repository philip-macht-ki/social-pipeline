"""Instagram Login API: Container anlegen, geduldig auf Status warten, senden.

Referenz und bekannte Fallstricke stehen in befund_takt.md (Vorbild-System,
Stand 28.09.2026). Diese Datei ruft nur `senden(planeintrag)` und
`befehl_token` über cli.py auf.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from ..kern import konfig, pfad
from .medien import bereitstellen

# Instagram lässt höchstens 10 Kinder je Karussell zu (harte Grenze der API).
KARUSSELL_MAX = 10


def _basis() -> str:
    return "https://graph.instagram.com/" + konfig("kanaele")["instagram"].get("api_version", "v21.0")


def _req(method: str, pfad_teil: str, **kw) -> dict:
    kw.setdefault("params", {}).update({"access_token": os.environ.get("INSTAGRAM_TOKEN", "")})
    r = requests.request(method, _basis() + pfad_teil, timeout=120, **kw)
    daten = r.json()
    if r.status_code >= 400:
        raise RuntimeError(str(daten.get("error", daten)))
    return daten


def _als_jpeg(datei: Path) -> tuple[Path, bool]:
    """Instagram nimmt nur JPEG-Bilder. Wandelt PNG lokal um und meldet, ob eine
    Datei zum Aufräumen entstanden ist. Ohne diesen Schritt scheitert der
    Bild-Container stumm mit einem generischen Fehler (siehe befund_takt.md)."""
    if datei.suffix.lower() != ".png":
        return datei, False
    from PIL import Image
    ziel = datei.with_suffix(".jpg")
    with Image.open(datei) as bild:
        # Transparenz gibt es bei JPEG nicht: auf Weiß legen statt schwarz zu füllen.
        hintergrund = Image.new("RGB", bild.size, "white")
        maske = bild.split()[3] if bild.mode == "RGBA" else None
        hintergrund.paste(bild.convert("RGB"), mask=maske)
        hintergrund.save(ziel, "JPEG", quality=92)
    return ziel, True


def _hochladen(pfad_lokal: str) -> tuple[str, list]:
    """Lädt eine lokale Bild- oder Videodatei hoch und gibt (url, aufraeumer) zurück.
    aufraeumer sammelt alle Funktionen, die nach dem Senden aufgerufen werden müssen."""
    aufraeumer = []
    datei, temp_erzeugt = _als_jpeg(Path(pfad_lokal))
    url, entfernen = bereitstellen(str(datei))
    aufraeumer.append(entfernen)
    if temp_erzeugt:
        aufraeumer.append(lambda: datei.unlink(missing_ok=True))
    return url, aufraeumer


def _cover_url(video_datei: str) -> tuple[str | None, list]:
    """Reel bekommt ein eigenes Titelbild, wenn cover.jpg daneben liegt.
    Ohne cover_url fällt Instagram auf einen automatischen Videoframe zurück,
    der selten der gewünschte ist."""
    kandidat = Path(video_datei).parent / "cover.jpg"
    if not kandidat.exists():
        return None, []
    return _hochladen(str(kandidat))


def senden(e: dict) -> dict:
    user = os.environ.get("INSTAGRAM_USER_ID", "")
    aufraeumer: list = []
    try:
        urls = []
        for datei in e["dateien"]:
            url, aufraeumer_datei = _hochladen(datei)
            urls.append(url)
            aufraeumer += aufraeumer_datei

        gemeinsam = {"caption": e.get("text", "")}
        if e["art"] == "reel":
            cover, aufraeumer_cover = _cover_url(e["dateien"][0])
            aufraeumer += aufraeumer_cover
            daten = {"media_type": "REELS", "video_url": urls[0], "share_to_feed": "true"} | gemeinsam
            if cover:
                daten["cover_url"] = cover
        elif e["art"] == "bild":
            daten = {"image_url": urls[0]} | gemeinsam
        else:
            urls = urls[:KARUSSELL_MAX]
            kinder = [_req("POST", f"/{user}/media", data={"image_url": u, "is_carousel_item": "true"})["id"]
                      for u in urls]
            daten = {"media_type": "CAROUSEL", "children": ",".join(kinder)} | gemeinsam

        container_id = _req("POST", f"/{user}/media", data=daten)["id"]
        _warten_auf_container(container_id)
        medien_id = _veroeffentlichen_mit_geduld(user, container_id)
        permalink = _req("GET", f"/{medien_id}", params={"fields": "permalink"}).get("permalink")
        return {"extern_id": medien_id, "url": permalink}
    finally:
        for entfernen in aufraeumer:
            entfernen()


def _warten_auf_container(container_id: str) -> None:
    """Bis zu 5 Minuten auf FINISHED warten, ERROR/EXPIRED bricht sofort ab."""
    for _ in range(60):
        status = _req("GET", f"/{container_id}", params={"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {status}")
        time.sleep(5)
    raise RuntimeError("Container wurde nicht rechtzeitig fertig.")


def _veroeffentlichen_mit_geduld(user: str, container_id: str) -> str:
    """Fehler 9007 und 2207027 bedeuten "noch nicht so weit", kein echter
    Fehlschlag: wiederholt mit wachsender Pause versuchen (befund_takt.md)."""
    for pause in (0, 15, 30, 60, 90, 120):
        if pause:
            time.sleep(pause)
        try:
            return _req("POST", f"/{user}/media_publish", data={"creation_id": container_id})["id"]
        except RuntimeError as x:
            if "9007" not in str(x) and "2207027" not in str(x):
                raise
    raise RuntimeError("Instagram-Veröffentlichung blieb nicht verfügbar.")


def befehl_token(args) -> int:
    params = {"grant_type": "ig_refresh_token", "access_token": os.environ.get("INSTAGRAM_TOKEN", "")}
    r = requests.get("https://graph.instagram.com/refresh_access_token", params=params, timeout=60)
    daten = r.json()
    if r.status_code >= 400:
        print(f"fehler: Token konnte nicht verlängert werden: {daten}")
        return 1
    env = pfad(".env")
    text = env.read_text() if env.exists() else ""
    neuer_token = daten["access_token"]
    zeilen = [f"INSTAGRAM_TOKEN={neuer_token}" if z.startswith("INSTAGRAM_TOKEN=") else z
              for z in text.splitlines()]
    if not any(z.startswith("INSTAGRAM_TOKEN=") for z in zeilen):
        zeilen.append(f"INSTAGRAM_TOKEN={neuer_token}")
    env.write_text("\n".join(zeilen) + "\n")
    print(f"ok: Instagram-Token verlängert, gültig für {daten.get('expires_in', 'unbekannt')} Sekunden.")
    return 0
