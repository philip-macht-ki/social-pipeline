"""Tests für die Bildstile: Rendern, Kontrast, Sicherheitsrahmen, Titelversprechen, Rotation.

Kein Netz, kein Modell (Bildstile brauchen ohnehin kein Urteil). `boxen` bzw.
`im.textboxen` kommt direkt aus `gemeinsam.text()`, deshalb prüfen die Tests
echte gerenderte Größen und Farben, nie geschätzte Werte.
"""
from __future__ import annotations

from pipeline.stile import pinterest_auswahl
from pipeline.stile import pinterest, instagram, tiktok, threads
from pipeline.stile.gemeinsam import MINDESTKONTRAST, kontrast
from pipeline.kern import konfig

DATEN = {
    "titel": "Klare Schritte für den Alltag",
    "aussage": "Ein klarer Satz für den Alltag.",
    "saetze": [f"Punkt {i} ist klar und nützlich für den Alltag." for i in range(1, 10)],
    "punkte": [f"Punkt {i} ist klar und nützlich." for i in range(1, 10)],
    "quelle": "Eigene Quelle",
    "statistik": [("A", 20), ("B", 40), ("C", 60)],
}


def _pruefe_boxen(im, breite_px: int, hoehe_px: int, sicherheitsrahmen: tuple[int, int] | None = None) -> None:
    """Jede gezeichnete Box: im Bild, im Sicherheitsrahmen, genug Kontrast.
    `sicherheitsrahmen` ist (oberer_rand, unterer_rand): erlaubter y-Bereich."""
    boxen = getattr(im, "textboxen", None)
    assert boxen, "Der Stil hat keine Textboxen gemeldet (fehlt boxen= beim text()-Aufruf?)."
    for box in boxen:
        assert box["x"] >= 0 and box["y"] >= 0, box
        assert box["x"] + box["w"] <= breite_px, box
        assert box["y"] + box["h"] <= hoehe_px, box
        assert box["kontrast"] >= MINDESTKONTRAST, box
        # Der Kontrastwert im Protokoll muss auch wirklich stimmen, nicht nur gemeldet sein.
        assert kontrast(box["farbe"], box["hintergrund"]) >= MINDESTKONTRAST - 0.05, box
        if sicherheitsrahmen:
            oben, unten = sicherheitsrahmen
            assert box["y"] >= oben, f"Box {box} liegt vor dem Sicherheitsrahmen (oben {oben})."
            assert box["y"] + box["h"] <= unten, f"Box {box} ragt in den Sicherheitsrahmen (unten {unten})."


def test_instagram_bilder_rendern_lesbar(repo):
    for stil in ["zahl", "einwand", "vorher_nachher", "raster", "notiz", "zitat_standbild"]:
        im, befund = instagram.bild_stil(stil, {**DATEN, "text": "7"})
        assert im is not None and not befund, (stil, befund)
        assert im.size == (1080, 1350)
        _pruefe_boxen(im, 1080, 1350)


def test_instagram_karussells_rendern_lesbar(repo):
    for stil in ["schritte", "kette", "woche_hell"]:
        folien, befund = instagram.karussell(stil, DATEN, 6)
        assert len(folien) == 6 and not befund
        for folie in folien:
            assert folie.size == (1080, 1350)
            _pruefe_boxen(folie, 1080, 1350)


def test_tiktok_fotobeitraege_rendern_lesbar(repo):
    # Sicherheitsrahmen: TikTok blendet oben und unten App-Oberfläche ein
    # (oberer_sicherheitsrand=270, unterer_sicherheitsrand=520 in tiktok.py).
    rahmen = (270, 1920 - 520)
    for stil in ["foto_schritte", "foto_zitat"]:
        im, befund = tiktok.foto_stil(stil, DATEN)
        assert im is not None and not befund, (stil, befund)
        assert im.size == (1080, 1920)
        _pruefe_boxen(im, 1080, 1920, rahmen)
        # Lesetext bei 1080x1920 braucht mindestens 56 px (Befund 28.09.2026).
        lesetext_boxen = [b for b in im.textboxen if b["haupttext"]]
        assert lesetext_boxen and all(b["groesse"] >= 56 for b in lesetext_boxen), lesetext_boxen


def test_pinterest_pins_rendern_lesbar(repo):
    for stil in konfig("stile")["pinterest"]["pin"]:
        im, befund = pinterest.pin(stil, DATEN)
        assert im is not None and not befund, (stil, befund)
        assert im.size == (1000, 1500)
        _pruefe_boxen(im, 1000, 1500)
        # Lesetext auf Pins braucht mindestens 30 px (Befund 28.09.2026, Stil editorial).
        lesetext_boxen = [b for b in im.textboxen if b["haupttext"]]
        assert lesetext_boxen and all(b["groesse"] >= 30 for b in lesetext_boxen), (stil, lesetext_boxen)


def test_threads_zitatkarte_rendert_lesbar(repo):
    im, befund = threads.zitatkarte(DATEN["saetze"][0])
    assert im is not None and not befund
    _pruefe_boxen(im, 1080, 1350)


def test_raster_ohne_neun_beispiele_gibt_befund(repo):
    daten = {**DATEN, "saetze": ["Nur", "wenige", "Punkte"]}
    im, befund = instagram.bild_stil("raster", daten)
    assert im is None and "neun" in befund


def test_raster_mit_neun_beispielen_rendert(repo):
    im, befund = instagram.bild_stil("raster", DATEN)
    assert im is not None and not befund


def test_titelversprechen_passend_ist_ok(repo):
    im, befund = pinterest.pin("szene", {**DATEN, "titel": "3 Szenen für deinen Alltag", "punkte": ["eins", "zwei", "drei", "vier"]})
    assert im is not None and not befund


def test_titelversprechen_unpassend_gibt_befund(repo):
    im, befund = pinterest.pin("spickzettel", {**DATEN, "titel": "5 Wege", "punkte": ["eins", "zwei"]})
    assert im is None and "5" in befund and "2" in befund


def test_titelversprechen_zaehlt_tatsaechlich_gezeigte_punkte(repo):
    # szene zeigt höchstens 3 Punkte. Ein Titel, der 7 verspricht, muss auch dann
    # scheitern, wenn 7 Punkte GELIEFERT werden, weil nur 3 davon zu sehen sind
    # (Befund 28.09.2026: die Prüfung verglich bisher gegen die volle Liste).
    im, befund = pinterest.pin("szene", {**DATEN, "titel": "7 klare Schritte für deinen Alltag"})
    assert im is None and "7" in befund and "3" in befund


def test_titelversprechen_ohne_zahl_im_titel_ist_immer_ok(repo):
    im, befund = pinterest.pin("szene", {**DATEN, "titel": "Klare Szenen für deinen Alltag"})
    assert im is not None and not befund


def test_titelversprechen_gilt_nicht_fuer_toolraster_und_statistik(repo):
    # toolraster zeichnet immer ein festes 3x3-Raster, statistik zeigt Balken
    # aus eigenen Werten. Beide haben kein "N Punkte"-Versprechen.
    im, befund = pinterest.pin("toolraster", {**DATEN, "titel": "3 Werkzeuge"})
    assert im is not None and not befund
    im, befund = pinterest.pin("statistik", {**DATEN, "titel": "3 Phasen im Test"})
    assert im is not None and not befund


def test_stilauswahl_am_wenigsten_benutzte_zuerst(repo):
    cfg = konfig("stile")
    benutzt = {"szene": {"anzahl": 0, "datum": "2026-01-01"}, "spickzettel": {"anzahl": 4, "datum": "2026-01-01"}}
    auswahl = pinterest_auswahl(benutzt, cfg, "2026-01-02")
    assert auswahl[0] == "szene"


def test_stilauswahl_kein_stil_zweimal_am_tag(repo):
    cfg = konfig("stile")
    heute = "2026-01-02"
    # spickzettel wurde heute schon benutzt (anzahl 0, aber heutiges Datum):
    # er darf trotz niedrigster Anzahl nicht wieder gewählt werden.
    benutzt = {"spickzettel": {"anzahl": 0, "datum": heute}}
    auswahl = pinterest_auswahl(benutzt, cfg, heute)
    assert "spickzettel" not in auswahl


def test_stilauswahl_gesperrte_nie(repo):
    cfg = konfig("stile")
    cfg["pinterest"]["gesperrt"] = ["szene"]
    assert "szene" not in pinterest_auswahl({}, cfg, "2026-01-02")


def test_stilauswahl_respektiert_je_lauf(repo):
    cfg = konfig("stile")
    cfg["pinterest"]["je_lauf"] = 3
    auswahl = pinterest_auswahl({}, cfg, "2026-01-02")
    assert len(auswahl) == 3
