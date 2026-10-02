from __future__ import annotations

from io import BytesIO
import subprocess
import sys
import types

from PIL import Image

from pipeline import bausteine, einwort, gesicht, schrift


def _worte(text: str) -> list[dict]:
    return [{"w": w, "s": i * 1.0, "e": i * 1.0 + .7} for i, w in enumerate(text.split())]


def test_sticker_verneinung_und_obergrenze(repo, monkeypatch):
    monkeypatch.setattr(bausteine, "logo_holen", lambda *args, **kwargs: False)
    karten = bausteine.finden(_worte("nicht kostenlos gratis schneller teuer gefährlich"), {})
    sticker = [k for k in karten if k["art"] in {"haken", "kreuz"}]
    assert not any(k["text"] == "kostenlos" for k in sticker)
    assert len(sticker) <= 2
    assert all(b["von"] - a["von"] >= 8 for a, b in zip(sticker, sticker[1:]))


def test_ki_fenster_und_spur_ueberlappen_nie(repo, monkeypatch):
    monkeypatch.setattr(bausteine, "logo_holen", lambda *args, **kwargs: False)
    karten = bausteine.finden(_worte("gratis erstens zweitens"), {"ki_einblendung": {"von": 0, "bis": 3}})
    assert all(not (k["von"] < 3 and k["bis"] > 0) for k in karten)
    spur = bausteine.spur(karten, 9, links=60, rechts=900)
    assert all(b[0] >= a[1] for a, b in zip(spur, spur[1:]))


def test_lange_woerter_passen_in_den_rahmen(repo):
    for wort in ("Einzelunternehmer", "Datenschutzgrundverordnung"):
        font, _ = einwort._font_fuer(wort, "text", 840, 82)
        assert schrift.breite(wort, font) <= 840


def test_gesicht_rueckfall_und_ausweichen(repo):
    assert gesicht._rueckfall()[0]["x"] == .33
    karten = bausteine.platzieren([{"art": "haken", "von": 0, "bis": 2, "text": "gratis"}],
                                   [{"s": 0, "x": .05, "y": .65, "b": .5, "h": .25}],
                                   links=60, rechts=900)
    assert karten and karten[0]["y"] != 1290


def test_logo_holen_mit_gemocktem_netz(repo):
    puffer = BytesIO()
    Image.new("RGBA", (128, 128), "red").save(puffer, format="PNG")

    class Antwort:
        url = "https://beispiel.test"
        text = '<link rel="icon" href="/icon.png">'
        content = puffer.getvalue()

    ziel = repo / "medien" / "logos" / "beispiel.test.png"
    assert bausteine.logo_holen("beispiel.test", ziel, get=lambda *args, **kwargs: Antwort())
    assert Image.open(ziel).size == (256, 256)


def test_ki_modulfenster_berichtigt_bausteine(repo, monkeypatch):
    modul = types.ModuleType("pipeline.ki_einblendung")

    def anwenden(*args):
        args[1]["ki_einblendung"] = {"von": 0, "bis": 4}
        return args[3]

    modul.anwenden = anwenden
    monkeypatch.setitem(sys.modules, "pipeline.ki_einblendung", modul)
    rezept = {}
    modul.anwenden(None, rezept, None, None, None)
    karten = bausteine.finden(_worte("gratis erstens zweitens"), rezept)
    assert not karten
    assert [k["art"] for k in karten] == []


def test_alle_bausteinboxen_liegen_im_rahmen(repo):
    karten = [
        {"art": "haken", "text": "gratis", "von": 0, "bis": 2},
        {"art": "zaehler", "nr": 1, "gesamt": 2, "von": 2, "bis": 4},
        {"art": "korrektur", "alt": "Chaos", "y_text": "Plan", "von": 4, "bis": 6},
        {"art": "kommentarblase", "text": "Ist das wirklich nötig?", "von": 6, "bis": 8},
        {"art": "logo", "domain": "fehlt.test", "text": "Marke", "von": 8, "bis": 10},
        {"art": "verbindung", "domains": ["fehlt.test", "auch.test"], "von": 10, "bis": 12},
    ]
    gesetzt = bausteine.platzieren(karten, [{"s": 0, "x": .33, "y": .26, "b": .34, "h": .21}],
                                    links=60, rechts=900)
    for karte in gesetzt:
        box = bausteine._karte(karte, links=60, rechts=900).getbbox()
        assert box is not None
        assert 60 <= box[0] and box[2] <= 900
        assert 270 <= box[1] and box[3] <= 1620


def test_verbindung_zwischen_zwei_marken_im_zeitfenster(repo, monkeypatch):
    monkeypatch.setattr(bausteine, "logo_holen", lambda *args, **kwargs: False)
    karten = bausteine.finden(_worte("claude und chatgpt"), {})
    assert [k["art"] for k in karten] == ["verbindung"]


def test_handyrahmen_holt_standbild(repo):
    roh = repo / "testsrc.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=360x740:rate=30",
                    "-t", "1", "-pix_fmt", "yuv420p", str(roh)], check=True, capture_output=True)
    bild = bausteine._karte({"art": "handyrahmen", "von": .4, "bis": .9, "pos_x": 60, "y": 500},
                             links=60, rechts=900, roh=roh)
    assert bild.getbbox() is not None
    assert bild.getpixel((200, 700))[3] > 0


def test_handyrahmen_bleibt_ueber_tiktok_leiste(repo):
    karte = {"art": "handyrahmen", "von": 0, "bis": 2, "pos_x": 60, "y": 1230}
    bild = bausteine._karte(karte, links=60, rechts=900, unten=520)
    assert bild.getbbox()[3] <= 1920 - 520
