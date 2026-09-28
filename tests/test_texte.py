"""Tests für Texte je Plattform: Grenzen, Verbote, Nachfrage bei Verstoß, UTM-Link.

`pruefe_*` sind reine Funktionen (kein Netz, kein Modell), deshalb prüft der
größte Teil hier sie direkt. Nur `test_nachfrage_bei_verstoss` und
`test_pinterest_link_kommt_immer_vom_code` laufen über `texte.befehl()` mit
`urteil.frage` gemockt bzw. dem Rückfall-Pfad (`URTEIL_BACKEND=ohne`).
"""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import texte
from pipeline.kern import konfig, lesen, schreiben

MARKE = {"cta_zeile": "Mehr dazu findest du über den Link im Profil.", "hashtags": ["#eins", "#zwei"]}
HOOK = "Dieser Satz ist der klare Hook für heute."

CAPTION_GUT = (
    "Dieser Satz ist der klare Hook für heute.\n\n"
    "Ein Testinhalt ohne verbotene Zeichen.\n"
    "Was nimmst du für dich mit?\n"
    "Mehr dazu findest du über den Link im Profil.\n"
    "#eins #zwei"
)


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------

def test_instagram_gueltige_caption_ist_ok():
    assert texte.pruefe_instagram({"caption": CAPTION_GUT}, HOOK, MARKE, {}) is None


def test_instagram_obergrenze_2200_zeichen():
    caption = CAPTION_GUT.replace("Ein Testinhalt", "Ein Testinhalt " + "x" * 2200)
    befund = texte.pruefe_instagram({"caption": caption}, HOOK, MARKE, {})
    assert befund and "2200" in befund


def test_instagram_erste_zeile_muss_hook_aufgreifen():
    caption = CAPTION_GUT.replace("Dieser Satz ist der klare Hook für heute.", "Ein ganz anderer Einstieg ohne Bezug.")
    befund = texte.pruefe_instagram({"caption": caption}, HOOK, MARKE, {})
    assert befund and "erste Zeile" in befund


def test_instagram_braucht_frage_vor_cta():
    caption = CAPTION_GUT.replace("Was nimmst du für dich mit?", "Das ist einfach so.")
    befund = texte.pruefe_instagram({"caption": caption}, HOOK, MARKE, {})
    assert befund and "Frage" in befund


def test_instagram_braucht_cta_zeile():
    caption = CAPTION_GUT.replace("Mehr dazu findest du über den Link im Profil.\n", "")
    befund = texte.pruefe_instagram({"caption": caption}, HOOK, MARKE, {})
    assert befund and "CTA" in befund


def test_instagram_braucht_genau_eine_hashtag_zeile_mit_2_bis_4_tags():
    zu_wenig = CAPTION_GUT.replace("#eins #zwei", "#eins")
    befund = texte.pruefe_instagram({"caption": zu_wenig}, HOOK, MARKE, {})
    assert befund and "Hashtag" in befund
    zu_viele = CAPTION_GUT.replace("#eins #zwei", "#eins #zwei #drei #vier #fuenf")
    befund = texte.pruefe_instagram({"caption": zu_viele}, HOOK, MARKE, {})
    assert befund and "Hashtag" in befund


def test_instagram_mehrteiler_braucht_teil_zeile_am_ende():
    rezept = {"nr": 2, "von_stuecken": 3}
    befund = texte.pruefe_instagram({"caption": CAPTION_GUT}, HOOK, MARKE, rezept)
    assert befund and "Mehrteiler" in befund
    caption_mit_teil = CAPTION_GUT + "\nTeil 2 von 3."
    assert texte.pruefe_instagram({"caption": caption_mit_teil}, HOOK, MARKE, rezept) is None


# ---------------------------------------------------------------------------
# TikTok
# ---------------------------------------------------------------------------

CAPTION_TIKTOK_GUT = "Ein Gedanke für deinen Alltag. Mehr im Link im Profil. #eins #zwei"


def test_tiktok_gueltige_caption_ist_ok():
    assert texte.pruefe_tiktok({"caption": CAPTION_TIKTOK_GUT}) is None


def test_tiktok_obergrenze_2200_zeichen():
    befund = texte.pruefe_tiktok({"caption": CAPTION_TIKTOK_GUT + " " + "x" * 2200})
    assert befund and "2200" in befund


def test_tiktok_hoechstens_fuenf_hashtags():
    caption = CAPTION_TIKTOK_GUT + " #drei #vier #fuenf #sechs"
    befund = texte.pruefe_tiktok({"caption": caption})
    assert befund and "fünf" in befund


def test_tiktok_braucht_link_im_profil_verweis():
    befund = texte.pruefe_tiktok({"caption": "Ein Gedanke ohne Verweis. #eins"})
    assert befund and "Link" in befund


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

BESCHREIBUNG_GUT = "Ein klarer Gedanke für deinen Alltag. Nimm ihn als Anlass für den nächsten Schritt. https://example.de"


def test_youtube_gueltiger_titel_ist_ok():
    assert texte.pruefe_youtube({"titel": "Ein griffiger Titel", "beschreibung": BESCHREIBUNG_GUT}, "https://example.de", HOOK) is None


def test_youtube_titel_hoechstens_100_zeichen():
    befund = texte.pruefe_youtube({"titel": "x" * 101, "beschreibung": BESCHREIBUNG_GUT}, "https://example.de", HOOK)
    assert befund and "100" in befund


def test_youtube_titel_darf_nicht_der_hook_sein():
    befund = texte.pruefe_youtube({"titel": HOOK, "beschreibung": BESCHREIBUNG_GUT}, "https://example.de", HOOK)
    assert befund and "identisch" in befund


def test_youtube_beschreibung_braucht_zwei_bis_vier_saetze():
    befund = texte.pruefe_youtube({"titel": "Ein Titel", "beschreibung": "Nur ein Satz. https://example.de"}, "https://example.de", HOOK)
    assert befund and "Sätze" in befund


def test_youtube_beschreibung_braucht_den_link():
    befund = texte.pruefe_youtube({"titel": "Ein Titel", "beschreibung": "Ein Satz. Noch einer ohne Link."}, "https://example.de", HOOK)
    assert befund and "Link" in befund


# ---------------------------------------------------------------------------
# Pinterest
# ---------------------------------------------------------------------------

BESCHREIBUNG_PIN_GUT = "Ein klarer Gedanke, der dir einen einfachen Startpunkt für deinen nächsten Schritt im Alltag gibt."


def test_pinterest_gueltiges_paar_ist_ok():
    assert texte.pruefe_pinterest({"titel": "Ein klarer Impuls", "beschreibung": BESCHREIBUNG_PIN_GUT}) is None


def test_pinterest_titel_hoechstens_100_zeichen():
    befund = texte.pruefe_pinterest({"titel": "x" * 101, "beschreibung": BESCHREIBUNG_PIN_GUT})
    assert befund and "100" in befund


def test_pinterest_beschreibung_60_bis_500_zeichen():
    befund = texte.pruefe_pinterest({"titel": "Titel", "beschreibung": "Zu kurz."})
    assert befund and "60" in befund
    befund = texte.pruefe_pinterest({"titel": "Titel", "beschreibung": "x" * 501})
    assert befund and "500" in befund


def test_pinterest_link_kommt_immer_vom_code(repo):
    """Das Urteil liefert nur Titel und Beschreibung (siehe pinterest.md), den Link
    mit UTM-Parametern setzt `_machen()` danach immer selbst (ARCHITEKTUR.md:
    Zeiten, Maße, Dateien... ist Code). Getestet über den Rückfall-Pfad, ohne Modell."""
    ordner = repo / "arbeit" / "take" / "stuecke" / "01"
    ordner.mkdir(parents=True)
    schreiben(ordner / "rezept.json", {"id": "take-01", "take": "take", "nr": 1, "von_stuecken": 1, "titel": "Ein Titel", "aussage": "Eine Aussage"})
    schreiben(repo / "arbeit" / "take" / "saetze.json", [{"nr": 1, "text": "Dieser Satz ist der klare Hook für heute."}])
    assert texte.befehl(SimpleNamespace(ziel=["take-01"], neu=True)) == 0
    daten = lesen(repo / "ausgabe" / "take-01" / "texte.json")
    marke = konfig("marke")
    assert daten["pinterest"]["link"] == texte._utm(marke.get("link", ""))
    assert "utm_source=pinterest" in daten["pinterest"]["link"]


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def test_threads_gueltiger_text_ist_ok():
    assert texte.pruefe_threads({"text": "Ein Gedanke für deinen Alltag. #Alltag"}) is None


def test_threads_hoechstens_500_zeichen():
    befund = texte.pruefe_threads({"text": "x " * 300 + "#Alltag"})
    assert befund and "500" in befund


def test_threads_braucht_genau_einen_topic_tag():
    befund = texte.pruefe_threads({"text": "Ein Gedanke ohne Tag."})
    assert befund and "Topic-Tag" in befund
    befund = texte.pruefe_threads({"text": "Ein Gedanke. #eins #zwei"})
    assert befund and "Topic-Tag" in befund


def test_threads_verweist_nicht_auf_andere_beitraege():
    befund = texte.pruefe_threads({"text": "Wie ich im Reel schon sagte. #Alltag"})
    assert befund and "anderen Beitrag" in befund


# ---------------------------------------------------------------------------
# Gedankenstrich- und Teilen-Verbot (gilt für alle Plattformen über _allgemein)
# ---------------------------------------------------------------------------

def test_gedankenstrich_verboten_ueberall():
    assert texte.pruefe_instagram({"caption": CAPTION_GUT.replace("Ein Testinhalt", "Ein Test – Inhalt")}, HOOK, MARKE, {})
    assert texte.pruefe_tiktok({"caption": CAPTION_TIKTOK_GUT.replace("Ein Gedanke", "Ein Gedanke – wirklich")})
    assert texte.pruefe_threads({"text": "Ein Gedanke – wirklich. #Alltag"})


def test_teilen_aufforderung_verboten_ueberall():
    assert texte.pruefe_instagram({"caption": CAPTION_GUT.replace("Was nimmst du für dich mit?", "Teile das mit einer Freundin?")}, HOOK, MARKE, {})
    assert texte.pruefe_tiktok({"caption": CAPTION_TIKTOK_GUT.replace("Mehr im", "Schick das an jemanden, mehr im")})
    assert texte.pruefe_threads({"text": "Leite das weiter. #Alltag"})


# ---------------------------------------------------------------------------
# Nachfrage bei Verstoß: urteil.frage gemockt, erste Antwort verletzt, zweite passt.
# ---------------------------------------------------------------------------

def test_nachfrage_bei_verstoss(monkeypatch, repo):
    ordner = repo / "arbeit" / "take" / "stuecke" / "01"
    ordner.mkdir(parents=True)
    schreiben(ordner / "rezept.json", {"id": "take-01", "take": "take", "nr": 1, "von_stuecken": 1, "titel": "Ein Titel", "aussage": "Eine Aussage"})
    schreiben(repo / "arbeit" / "take" / "saetze.json", [{"nr": 1, "text": "Dieser Satz ist der klare Hook für heute."}])

    schlechte_caption = CAPTION_GUT.replace("Ein Testinhalt", "Ein Test – Inhalt")  # verletzt das Gedankenstrich-Verbot
    versuche = {"instagram": 0}

    def fake_frage(auftrag, *, zweck, rueckfall=None, pruefe=None):
        if zweck != "texte_instagram":
            return rueckfall()
        versuche["instagram"] += 1
        antwort = schlechte_caption if versuche["instagram"] == 1 else CAPTION_GUT
        antwort = {"caption": antwort}
        mangel = pruefe(antwort) if pruefe else None
        if mangel:
            # Genau das tut urteil.frage() selbst: bei einem Mangel wird intern
            # noch einmal gefragt, bevor das Ergebnis an den Aufrufer zurückgeht.
            antwort = {"caption": CAPTION_GUT}
            assert pruefe(antwort) is None
        return antwort

    monkeypatch.setattr(texte, "frage", fake_frage)
    assert texte.befehl(SimpleNamespace(ziel=["take-01"], neu=True)) == 0
    daten = lesen(repo / "ausgabe" / "take-01" / "texte.json")
    assert daten["instagram"]["caption"] == CAPTION_GUT
    assert daten["befunde"] == []


# ---------------------------------------------------------------------------
# Bestehende Integrationstests
# ---------------------------------------------------------------------------

def test_rueckfall_holt_alle_grenzen(repo):
    o = repo / "arbeit" / "take" / "stuecke" / "01"
    o.mkdir(parents=True)
    schreiben(o / "rezept.json", {"id": "take-01", "take": "take", "nr": 1, "von_stuecken": 2, "titel": "Klarer Titel", "aussage": "Ein klarer Gedanke", "status": "gebaut"})
    schreiben(repo / "arbeit" / "take" / "saetze.json", [{"nr": 1, "text": "Dieser Satz ist der klare Hook für heute."}])
    assert texte.befehl(SimpleNamespace(ziel=["take-01"], neu=True)) == 0
    d = lesen(repo / "ausgabe" / "take-01" / "texte.json")
    assert texte.pruefe_instagram(d["instagram"], "Dieser Satz ist der klare Hook für heute.", konfig("marke"), lesen(o / "rezept.json")) is None
    assert d["instagram"]["caption"].splitlines()[-1] == "Teil 1 von 2."


def test_harte_pruefungen():
    assert texte.pruefe_tiktok({"caption": "— " + ("#a " * 6) + " Link im Profil"})
    assert texte.pruefe_threads({"text": "auf Instagram #a"})
    assert texte.pruefe_instagram({"caption": "Hook\n#eins #zwei #drei #vier #fuenf"}, "Hook", {"hashtags": ["#eins", "#zwei"]}, {})
