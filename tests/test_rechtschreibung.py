"""Tests für pipeline/rechtschreibung.py: Kategorienfilter, Ausnahmeliste,
UPPERCASE_SENTENCE_START, Absatztrennung im Request, Netzfehler.

Kein echtes Netz hier (`requests.post` ist immer gemockt) - der echte Lauf
gegen die LanguageTool-API ist Teil der Abnahme, nicht der Testsuite.
`konfig` ist gemockt, damit die Tests unabhängig vom echten Inhalt von
konfig/pipeline.toml und konfig/marke.toml sind.
"""
from __future__ import annotations

from pipeline import rechtschreibung

PIPELINE_CFG = {"rechtschreibung": {"an": True, "dienst": "https://lt.example/check", "ausnahmen": ["testausnahme"]}}
MARKE_CFG = {"name": "Testmarke", "handle": "@testmarke", "wortmarke": "TESTMARKE"}


def _konfig(cfg):
    def fake(name):
        if name == "pipeline":
            return cfg
        if name == "marke":
            return MARKE_CFG
        raise AssertionError(f"unerwarteter konfig-Aufruf: {name}")
    return fake


class _Antwort:
    def __init__(self, treffer):
        self._treffer = treffer

    def json(self):
        return {"matches": self._treffer}


def _treffer(text: str, wort: str, kategorie: str, regel_id: str = "IRGENDEINE", message: str = "Fehler", vorschlaege=()):
    offset = text.index(wort)
    return {"offset": offset, "length": len(wort), "message": message,
            "rule": {"id": regel_id, "category": {"id": kategorie}},
            "replacements": [{"value": v} for v in vorschlaege]}


def test_kategorienfilter_laesst_nur_die_vier_kategorien_durch(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))
    text = "Bestehene Folien für den Entwurf."
    treffer = [
        _treffer(text, "Bestehene", "TYPOS", message="Möglicher Tippfehler", vorschlaege=["Bestehende"]),
        _treffer(text, "Entwurf", "STYLE", message="Stilhinweis, keine echte Fehlerkategorie"),
    ]
    monkeypatch.setattr(rechtschreibung.requests, "post", lambda *a, **k: _Antwort(treffer))
    befunde = rechtschreibung.pruefe({"feld": text})
    assert len(befunde) == 1
    assert "Bestehene" in befunde[0] and "Bestehende" in befunde[0]


def test_ausnahmeliste_filtert_eigene_und_konfigurierte_woerter(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))
    text = "Der Hook und testausnahme sind hier kein Fehler, Zeitplen schon."
    treffer = [
        _treffer(text, "Hook", "TYPOS"),
        _treffer(text, "testausnahme", "TYPOS"),
        _treffer(text, "Zeitplen", "TYPOS", vorschlaege=["Zeitplan"]),
    ]
    monkeypatch.setattr(rechtschreibung.requests, "post", lambda *a, **k: _Antwort(treffer))
    befunde = rechtschreibung.pruefe({"feld": text})
    assert len(befunde) == 1
    assert "Zeitplen" in befunde[0]


def test_uppercase_sentence_start_wird_ignoriert(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))
    text = "so geht's, klein am Satzanfang."
    treffer = [_treffer(text, "so", "CASING", regel_id="UPPERCASE_SENTENCE_START_A")]
    monkeypatch.setattr(rechtschreibung.requests, "post", lambda *a, **k: _Antwort(treffer))
    assert rechtschreibung.pruefe({"feld": text}) == []


def test_felder_werden_mit_leerzeile_verbunden(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))
    gesendet = {}

    def fake_post(url, data=None, timeout=None):
        gesendet["url"] = url
        gesendet["text"] = data["text"]
        gesendet["language"] = data["language"]
        return _Antwort([])

    monkeypatch.setattr(rechtschreibung.requests, "post", fake_post)
    rechtschreibung.pruefe({"a": "Erster Absatz.", "b": "Zweiter Absatz."})
    assert gesendet["text"] == "Erster Absatz.\n\nZweiter Absatz."
    assert gesendet["language"] == "de-DE"
    assert gesendet["url"] == "https://lt.example/check"


def test_netzfehler_bricht_nicht_ab(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))

    def fake_post(*a, **k):
        raise ConnectionError("kein Netz")

    monkeypatch.setattr(rechtschreibung.requests, "post", fake_post)
    befunde = rechtschreibung.pruefe({"feld": "Ein Text, egal welcher."})
    assert befunde == ["Rechtschreibprüfung nicht erreichbar."]


def test_aus_liefert_keine_befunde_und_ruft_kein_netz(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig({"rechtschreibung": {"an": False}}))
    aufgerufen = []
    monkeypatch.setattr(rechtschreibung.requests, "post", lambda *a, **k: aufgerufen.append(1))
    assert rechtschreibung.pruefe({"feld": "Ein Text."}) == []
    assert aufgerufen == []


def test_leere_felder_rufen_kein_netz(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "konfig", _konfig(PIPELINE_CFG))
    aufgerufen = []
    monkeypatch.setattr(rechtschreibung.requests, "post", lambda *a, **k: aufgerufen.append(1))
    assert rechtschreibung.pruefe({"feld": "", "andere": None}) == []
    assert aufgerufen == []
