import argparse
import json
from datetime import timedelta
from pipeline import kern, plan

def _cfg(repo, text): (repo / "konfig/kanaele.toml").write_text(text)
def _zeit(minuten=0): return (kern.jetzt().replace(second=0, microsecond=0) + timedelta(minutes=minuten)).isoformat()
def _k(kanal="instagram", art="reel", take="take-a", teil=1, von=1, dauer=30):
    return {"kanal":kanal,"art":art,"take":take,"quelle":take+"-"+str(teil),"teil":teil,"von_teilen":von,"dauer_s":dauer}
def _e(k, zeit): return {**k,"zeit":zeit.isoformat() if hasattr(zeit,"isoformat") else zeit,"status":"geplant"}

def test_plan_legt_reel_an(repo):
    d=repo/'ausgabe'/'take-01';d.mkdir();(d/'instagram.mp4').write_bytes(b'x');(d/'stueck.json').write_text(json.dumps({'id':'take-01','status':'fertig','dauer_s':30,'dateien':{'instagram':'instagram.mp4'},'befunde':['hinweis']}));(d/'texte.json').write_text(json.dumps({'instagram':{'caption':'Text'}}))
    # Zwei Tage: am Abend sind die heutigen Plätze schon vorbei (Test war uhrzeitabhängig).
    plan.befehl_planen(argparse.Namespace(tage=2)); es=json.loads((repo/'arbeit/plan.json').read_text())['eintraege'];assert es and es[0]['befunde']==['hinweis']

def test_freigabe(repo):
    (repo/'arbeit/plan.json').write_text('{"eintraege":[{"id":"p-0001","freigegeben":false}]}');plan.befehl_freigeben(argparse.Namespace(ziel=['p-0001'],alle=False));assert json.loads((repo/'arbeit/plan.json').read_text())['eintraege'][0]['freigegeben']

def test_nachtruhe_slot_wird_nicht_geplant(repo):
    _cfg(repo, '''[instagram]\nan=true\nweg="upload_post"\nslots=[{zeit="21:00",art="reel"},{zeit="10:00",art="reel"}]\ntagesdeckel=9\nmindestabstand_minuten=0\nnachtruhe=["20:00","07:00"]\n''')
    d=repo/'ausgabe'/'n';d.mkdir();(d/'x.mp4').write_bytes(b'x');(d/'stueck.json').write_text(json.dumps({'id':'n-1','status':'fertig','dauer_s':20,'dateien':{'instagram':'x.mp4'}}));(d/'texte.json').write_text('{}')
    plan.befehl_planen(argparse.Namespace(tage=2));assert all(plan._dt(e['zeit']).hour != 21 for e in json.loads((repo/'arbeit/plan.json').read_text())['eintraege'])

def test_vorziehen_zieht_spaeteren_eintrag_in_luecke(repo):
    _cfg(repo, '''[instagram]\nan=true\nweg="upload_post"\nslots=[{zeit="10:00",art="reel"}]\ntagesdeckel=9\nmindestabstand_minuten=0\nnachtruhe=["00:00","00:00"]\n''')
    morgen=kern.jetzt().replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(days=1); uebermorgen=morgen+timedelta(days=1); eintrag={**_k(),'id':'p-0001','zeit':uebermorgen.isoformat(),'slot':1,'status':'geplant','freigegeben':False};(repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[eintrag]}))
    # Vor 10 Uhr ist schon der heutige Platz frei (Test lief am 29.09.2026 um 08:51 rot).
    heute=morgen-timedelta(days=1); erster=heute if heute>kern.jetzt() else morgen
    assert plan.vorziehen(argparse.Namespace(tage=3)) == 1;assert plan._dt(json.loads((repo/'arbeit/plan.json').read_text())['eintraege'][0]['zeit']) == erster

def test_tagesdeckel_wird_eingehalten(repo):
    cfg={'tagesdeckel':1,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};z=plan._dt(_zeit(60));assert not plan._erlaubt(_k(),z,[_e(_k(take='alt'),z-timedelta(minutes=1))],cfg)
def test_instagram_mindestabstand_80_minuten(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':80,'nachtruhe':['00:00','00:00']};z=plan._dt(_zeit(120));assert not plan._erlaubt(_k(),z,[_e(_k(take='alt'),z-timedelta(minutes=79))],cfg)
def test_instagram_keine_bilder_aufeinander(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};z=plan._dt(_zeit(120));assert not plan._erlaubt(_k(art='bild'),z,[_e(_k(art='karussell',take='alt'),z-timedelta(minutes=1))],cfg)
def test_youtube_lehnt_zu_langes_stueck_ab(repo):
    cfg={'max_laenge_s':179,'tagesdeckel':9,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};assert not plan._erlaubt(_k('youtube','short',dauer=180),plan._dt(_zeit(120)),[],cfg)
def test_take_nicht_direkt_hintereinander(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};z=plan._dt(_zeit(120));assert not plan._erlaubt(_k(take='gleich'),z,[_e(_k(take='gleich'),z-timedelta(minutes=1))],cfg)
def test_mehrteiler_teil_zwei_nicht_vor_teil_eins(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};z=plan._dt(_zeit(120));assert not plan._erlaubt(_k(take='serie',teil=2,von=2),z,[],cfg);assert plan._erlaubt(_k(take='serie',teil=2,von=2),z,[_e(_k(take='serie',teil=1,von=2),z-timedelta(minutes=1))],cfg)
def test_unbesetzbarer_slot_stoppt_weitere_slots_nicht(repo):
    _cfg(repo, '''[instagram]\nan=true\nweg="upload_post"\nslots=[{zeit="10:00",art="bild"},{zeit="12:00",art="reel"}]\ntagesdeckel=9\nmindestabstand_minuten=0\nnachtruhe=["00:00","00:00"]\n''')
    d=repo/'ausgabe'/'x';d.mkdir();(d/'x.mp4').write_bytes(b'x');(d/'stueck.json').write_text(json.dumps({'id':'x-1','status':'fertig','dauer_s':30,'dateien':{'instagram':'x.mp4'}}));(d/'texte.json').write_text('{}');plan.befehl_planen(argparse.Namespace(tage=2));es=json.loads((repo/'arbeit/plan.json').read_text())['eintraege'];assert len(es)==1 and es[0]['art']=='reel'
def test_threads_bekommt_keine_reels(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':0,'nachtruhe':['00:00','00:00']};assert not plan._erlaubt(_k('threads','reel'),plan._dt(_zeit(120)),[],cfg)

def test_verpasst_und_fehler_werden_neu_eingeplant(repo):
    # Verpasste/gescheiterte Zeilen (posten.py setzt diesen Status bei
    # Überfälligkeit bzw. einem Sendefehler) dürfen den nächsten `planen`-Lauf
    # nicht dauerhaft blockieren: derselbe Beitrag muss einen neuen Platz finden.
    _cfg(repo, '''[instagram]\nan=true\nweg="upload_post"\nslots=[{zeit="10:00",art="reel"}]\ntagesdeckel=9\nmindestabstand_minuten=0\nnachtruhe=["00:00","00:00"]\n''')
    d=repo/'ausgabe'/'take-01';d.mkdir();(d/'instagram.mp4').write_bytes(b'x')
    (d/'stueck.json').write_text(json.dumps({'id':'take-01','status':'fertig','dauer_s':30,'dateien':{'instagram':'instagram.mp4'}}))
    (d/'texte.json').write_text(json.dumps({'instagram':{'caption':'Text'}}))
    alt={'id':'p-0001','kanal':'instagram','art':'reel','quelle':'take-01','take':'take-01','teil':1,'von_teilen':1,'zeit':_zeit(-60*24),'slot':1,'freigegeben':True,'freigegeben_am':None,'status':'verpasst','befunde':[]}
    (repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[alt]}))
    plan.befehl_planen(argparse.Namespace(tage=2))
    es=json.loads((repo/'arbeit/plan.json').read_text())['eintraege']
    neue=[e for e in es if e is not alt and e.get('status')=='geplant' and e.get('quelle')=='take-01']
    assert len(es)==2 and len(neue)==1

def test_fehler_eintrag_blockiert_slot_nicht_mehr(repo):
    cfg={'tagesdeckel':9,'mindestabstand_minuten':80,'nachtruhe':['00:00','00:00']}
    z=plan._dt(_zeit(120))
    gescheitert=_e(_k(take='alt'),z-timedelta(minutes=10)); gescheitert['status']='fehler'
    assert plan._erlaubt(_k(),z,[gescheitert],cfg)


def test_eine_aufnahme_fuellt_trotzdem_mehrere_plaetze(repo):
    # Erster Gesamtlauf 28.09.2026: Mit nur einem Take sperrte die Abwechslungsregel
    # alles nach dem ersten Stück, je Kanal ging genau ein Beitrag raus.
    for nr in (1, 2, 3):
        d = repo / 'ausgabe' / f'take-0{nr}'
        d.mkdir()
        (d / 'instagram.mp4').write_bytes(b'x')
        (d / 'stueck.json').write_text(json.dumps({'id': f'take-0{nr}', 'status': 'fertig', 'dauer_s': 40,
                                                   'dateien': {'instagram': 'instagram.mp4'}, 'befunde': []}))
        (d / 'texte.json').write_text(json.dumps({'instagram': {'caption': 'Text'}}))
    plan.befehl_planen(argparse.Namespace(tage=3))
    es = [e for e in json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'] if e['kanal'] == 'instagram']
    assert len(es) == 3, es
