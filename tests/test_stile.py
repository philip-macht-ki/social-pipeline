"""Tests für die Bildstile: Rendern, Kontrast, Sicherheitsrahmen, Titelversprechen, Rotation.

Kein Netz, kein Modell (Bildstile brauchen ohnehin kein Urteil). `boxen` bzw.
`im.textboxen` kommt direkt aus `gemeinsam.text()`, deshalb prüfen die Tests
echte gerenderte Größen und Farben, nie geschätzte Werte.
"""
from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from pipeline import stile as stile_paket
from pipeline.stile import pinterest_auswahl
from pipeline.stile import pinterest, instagram, tiktok, threads
from pipeline.stile.gemeinsam import MINDESTKONTRAST, kontrast, linienpositionen
from pipeline.schrift import groesste_passende
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


def test_neue_instagram_karussells_rendern_lesbar(repo):
    neue_daten = {
        **DATEN,
        "titel": "Drei Zeilen\nmit viel Luft\nfür den Anfang",
        "frage": "Drei Zeilen\nmit viel Luft\nfür den Schluss",
        "unter": "Neun kurze Gedanken für den Alltag",
        "punkte": ["Ein vollständiger kurzer Satz für den Alltag."] * 5,
    }
    foto, befund = instagram.karussell("foto", {**neue_daten, "titel": "Erste Zeile\nzweite Zeile",
                                                  "punkte": neue_daten["punkte"][:4]})
    hand, hand_befund = instagram.karussell("handschrift_liste", neue_daten)
    raster, raster_befund = instagram.karussell("rasterposter", {**neue_daten, "titel": "KLARE SCHRITTE", "punkte": [
        {"stichwort": f"Punkt {index}", "satz": "Ein kurzer Satz für den Alltag."} for index in range(9)
    ]})
    for folien, grund in [(foto, befund), (hand, hand_befund), (raster, raster_befund)]:
        assert folien and not grund, grund
        for folie in folien:
            assert folie.size == (1080, 1350)
            _pruefe_boxen(folie, 1080, 1350)
    assert len(foto) == 6
    assert len(raster) == 2


def test_handschrift_grundlinien_liegen_auf_dem_papierraster(repo):
    daten = {**DATEN, "titel": "Drei Zeilen\nmit viel Luft\nfür den Anfang",
             "frage": "Drei Zeilen\nmit viel Luft\nfür den Schluss",
             "punkte": ["Ein vollständiger kurzer Satz für den Alltag."] * 5}
    folien, befund = instagram.karussell("handschrift_liste", daten)
    assert not befund
    papierlinien = linienpositionen(1350)
    for folie in folien:
        grundlinien = folie.handschrift_grundlinien
        assert grundlinien
        assert all(min(abs(grundlinie + 6 - papierlinie) for papierlinie in papierlinien) <= 1
                   for grundlinie in grundlinien)
        assert all(zweite - erste == 74 for erste, zweite in zip(grundlinien, grundlinien[1:]))


def test_rasterposter_nutzt_die_groesste_passende_titelstufe(repo):
    daten = {**DATEN, "titel": "KLARE SCHRITTE", "punkte": [
        {"stichwort": f"Punkt {index}", "satz": "Ein kurzer Satz für den Alltag."} for index in range(9)
    ]}
    folien, befund = instagram.karussell("rasterposter", daten)
    assert not befund
    erwartet, _ = groesste_passende(daten["titel"], "block", [132, 120, 108, 96, 84, 72, 60, 48], 984, 2)
    titelbox = next(box for box in folien[0].textboxen if box["rolle"] == "block")
    assert titelbox["groesse"] == erwartet


def test_neue_karussells_pruefen_ihre_festen_grenzen(repo):
    folien, befund = instagram.karussell("foto", {**DATEN, "punkte": ["nur einer"]})
    assert not folien and "vier" in befund
    folien, befund = instagram.karussell("handschrift_liste", {**DATEN, "punkte": ["nur einer"] * 4})
    assert not folien and "5 bis 8" in befund
    folien, befund = instagram.karussell("rasterposter", {**DATEN, "punkte": []})
    assert not folien and "neun" in befund


def test_foto_standbilder_liegen_zwischen_zwolf_und_achtundachtzig_prozent(repo, monkeypatch):
    quelle = repo / "arbeit" / "t1" / "quelle.mp4"
    quelle.parent.mkdir(parents=True)
    quelle.touch()
    zeiten = []

    def ffmpeg_ersatz(befehl, capture_output):
        zeiten.append(float(befehl[befehl.index("-ss") + 1]))
        Image.new("RGB", (1080, 1350), "#555555").save(befehl[-1])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(instagram.subprocess, "run", ffmpeg_ersatz)
    bilder = instagram._standbilder_aus_aufnahme(quelle, 100)
    assert len(bilder) == 6
    assert zeiten == [12.0, 27.2, 42.4, 57.6, 72.8, 88.0]


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


# ---------------------------------------------------------------------------
# Strukturprüfung nach dem Kürzen (_kuerzen/_kuerzung_gueltig): keine verlorenen
# Felder, keine verkürzten Listen, Titelfelder behalten ihre Satzzahl. Lehre aus
# dem Cashflow-Betrieb, 28.09.2026 (insta-sop/pinterest_bauen.py).
# ---------------------------------------------------------------------------

def test_kuerzung_verwirft_gestrichenen_satz_im_titel(monkeypatch, repo):
    alt = {"titel": "Erster Satz. Zweiter Satz.", "punkte": ["eins", "zwei", "drei"]}
    neu = {"titel": "Erster Satz.", "punkte": ["eins", "zwei", "drei"]}  # ein Satz im Titel fehlt
    monkeypatch.setattr(stile_paket, "frage", lambda *a, **k: neu)
    ergebnis, grund = stile_paket._kuerzen("pinterest", "spickzettel", alt, "120 px zu breit")
    assert ergebnis is None
    assert grund == "Kürzung hat Inhalt gestrichen"


def test_kuerzung_verwirft_gekuerzte_liste(monkeypatch, repo):
    alt = {"titel": "Ein Satz.", "punkte": ["eins", "zwei", "drei"]}
    neu = {"titel": "Ein Satz.", "punkte": ["eins", "zwei"]}  # ein Punkt fehlt
    monkeypatch.setattr(stile_paket, "frage", lambda *a, **k: neu)
    ergebnis, grund = stile_paket._kuerzen("pinterest", "spickzettel", alt, "Text zu lang")
    assert ergebnis is None
    assert grund == "Kürzung hat Inhalt gestrichen"


def test_kuerzung_verwirft_fehlendes_feld(monkeypatch, repo):
    alt = {"titel": "Ein Satz.", "unter": "Ein Merksatz.", "punkte": ["eins", "zwei"]}
    neu = {"titel": "Ein Satz.", "punkte": ["eins", "zwei"]}  # "unter" fehlt komplett
    monkeypatch.setattr(stile_paket, "frage", lambda *a, **k: neu)
    ergebnis, grund = stile_paket._kuerzen("pinterest", "spickzettel", alt, "zu lang")
    assert ergebnis is None
    assert grund == "Kürzung hat Inhalt gestrichen"


def test_kuerzung_gueltig_wird_uebernommen(monkeypatch, repo):
    alt = {"titel": "Ein Satz. Noch einer.", "punkte": ["eins", "zwei", "drei"]}
    neu = {"titel": "Kurz. Noch einer.", "punkte": ["eins", "zwei", "drei"]}  # gleiche Satzzahl, kürzer
    monkeypatch.setattr(stile_paket, "frage", lambda *a, **k: neu)
    ergebnis, grund = stile_paket._kuerzen("pinterest", "spickzettel", alt, "zu breit")
    assert ergebnis == neu
    assert grund is None


def test_kuerzung_ohne_antwort_liefert_keinen_grund(monkeypatch, repo):
    alt = {"titel": "Ein Satz.", "punkte": ["eins"]}
    monkeypatch.setattr(stile_paket, "frage", lambda *a, **k: None)
    ergebnis, grund = stile_paket._kuerzen("pinterest", "spickzettel", alt, "zu breit")
    assert ergebnis is None and grund is None
