from pipeline import rohmaterial, transkript, zerlegen, hook


def test_eingang_akzeptiert_grosse_endung(repo):
    (repo / "eingang" / "Mein Video.MOV").write_bytes(b"x")
    assert rohmaterial.eingang()[0].status == "ok"
    assert (repo / "arbeit" / "mein-video" / "quelle.mov").exists()


def test_saetze_an_pause_und_zeichen():
    w = [{"w":"Hallo","s":0,"e":.2},{"w":"Welt","s":.3,"e":.5},{"w":"Nächster","s":1.0,"e":1.2},{"w":"Satz.","s":1.3,"e":1.5}]
    assert [x["text"] for x in transkript.saetze(w)] == ["Hallo Welt", "Nächster Satz."]


def test_ueberlappung_wird_auf_satzkante_bereinigt():
    s=[{"nr":i,"s":i*10,"e":i*10+8,"text":"Satz."} for i in range(5)]
    r=zerlegen.bereinige([{"von_satz":0,"bis_satz":2},{"von_satz":2,"bis_satz":4}],s,1,200)
    assert r == [{"von_satz":0,"bis_satz":2},{"von_satz":3,"bis_satz":4}]


def test_kurzes_stueck_wird_zusammengelegt():
    s=[{"nr":0,"s":0,"e":4,"text":"Kurz."},{"nr":1,"s":5,"e":45,"text":"Lang."}]
    assert zerlegen.bereinige([{"von_satz":0,"bis_satz":0},{"von_satz":1,"bis_satz":1}],s,30,200) == [{"von_satz":0,"bis_satz":1}]


def test_hook_schwellen():
    assert hook.vorziehen(7,5)
    assert hook.vorziehen(6,2)
    assert not hook.vorziehen(6,4)
