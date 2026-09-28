from pipeline import kern, schrift, urteil


def test_repo_ist_umgebogen(repo):
    assert kern.pfad("arbeit") == repo / "arbeit"
    kern.schreiben(kern.pfad("arbeit", "x.json"), {"a": 1})
    assert kern.lesen(repo / "arbeit" / "x.json") == {"a": 1}


def test_sperre_raeumt_verwaiste_auf(repo):
    (repo / "arbeit" / ".lauf.pid").write_text("999999")
    with kern.Sperre():
        assert (repo / "arbeit" / ".lauf.pid").exists()
    assert not (repo / "arbeit" / ".lauf.pid").exists()


def test_fett_ist_breiter_als_normal(repo):
    fett = schrift.breite("Hallo Welt", schrift.schrift("text", 60))
    normal = schrift.breite("Hallo Welt", schrift.schrift("text_normal", 60))
    assert fett > normal


def test_passt_meldet_pixel(repo):
    ok, befund, _ = schrift.passt("Ein viel zu langer Titel für einen schmalen Kasten", "titel", 96, 300, 1)
    assert not ok and "px" in befund


def test_urteil_ohne_modell_nimmt_regel(repo):
    assert urteil.frage("x", zweck="t", rueckfall=lambda: {"ok": True}) == {"ok": True}


def test_json_aus_text():
    assert urteil.json_aus('Hier: ```json\n{"a": [1, 2]}\n``` fertig') == {"a": [1, 2]}
