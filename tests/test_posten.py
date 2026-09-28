import argparse,json,sys,types
from datetime import timedelta
from pathlib import Path
from pipeline import posten,kern
from pipeline import plan as plan_modul
from pipeline.posten import upload_post,instagram,youtube,medien

def _eintrag(repo, kanal='threads', ident='p-0001', alt=1):
 f=repo/'ausgabe'/'x.jpg';f.write_bytes(b'x');return {'id':ident,'kanal':kanal,'art':'bild','dateien':[str(f)],'zeit':(kern.jetzt()-timedelta(minutes=alt)).isoformat(),'freigegeben':True,'status':'geplant','text':'hi'}

def test_trocken_keine_netzanfrage(repo,monkeypatch):
 e=_eintrag(repo);(repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[e]}));monkeypatch.setattr(posten.upload_post,'senden',lambda x: (_ for _ in ()).throw(AssertionError()));posten.befehl(argparse.Namespace(echt=False,kanal=None));l=json.loads((repo/'arbeit/postlog.json').read_text());assert l[-1]['trocken'] and '***' in str(l[0])

def test_kanalschluessel_enthält_kanal_und_plan_id(repo,monkeypatch):
 e=_eintrag(repo,'instagram');(repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[e]}));(repo/'arbeit/postlog.json').write_text(json.dumps([{'kanal':'youtube','plan_id':'p-0001','status':'ok'}]));gerufen=[];monkeypatch.setattr(posten.upload_post,'senden',lambda x:gerufen.append(x) or {'zustand':'ok','extern_id':'ig'})
 posten.befehl(argparse.Namespace(echt=True,kanal=None));assert gerufen and json.loads((repo/'arbeit/plan.json').read_text())['eintraege'][0]['status']=='veroeffentlicht'

def test_doppelpost_schutz(repo):
 e=_eintrag(repo);(repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[e]}));(repo/'arbeit/postlog.json').write_text(json.dumps([{'kanal':'threads','plan_id':'p-0001','status':'ok'}]));posten.befehl(argparse.Namespace(echt=False,kanal=None));assert json.loads((repo/'arbeit/plan.json').read_text())['eintraege'][0]['status']=='geplant'

def test_aelter_als_12_stunden_wird_verpasst(repo):
 # Überfällige Zeilen gehen nicht mehr raus, planen legt sie neu ein (nur echt, s.u.).
 e=_eintrag(repo,alt=13*60);(repo/'arbeit/plan.json').write_text(json.dumps({'eintraege':[e]}));posten.befehl(argparse.Namespace(echt=True,kanal=None));assert json.loads((repo/'arbeit/plan.json').read_text())['eintraege'][0]['status']=='verpasst'


def test_trockenlauf_laesst_ueberfaellige_zeile_im_plan_bytegleich(repo):
    # Befund 28.09.2026: der Trockenlauf setzte ueberfaellige Zeilen auf "verpasst" und
    # aenderte damit den Plan, obwohl ein Trockenlauf nur zeigen soll. Die Plan-Datei
    # muss vor und nach einem Trockenlauf byte-fuer-byte gleich sein.
    e = _eintrag(repo, alt=13 * 60)
    plan_pfad = repo / 'arbeit/plan.json'
    kern.schreiben(plan_pfad, {'eintraege': [e]})  # kanonisch formatiert, wie posten es selbst schreibt
    vorher = plan_pfad.read_bytes()
    posten.befehl(argparse.Namespace(echt=False, kanal=None))
    assert plan_pfad.read_bytes() == vorher
    assert json.loads(plan_pfad.read_text())['eintraege'][0]['status'] == 'geplant'


def test_trockenlauf_aendert_plan_nicht_und_blockiert_echten_lauf_nicht(repo, monkeypatch):
    # Fehler aus dem ersten Bau (28.09.2026): Der Trockenlauf markierte Einträge als
    # veröffentlicht, danach wäre nie etwas echt gesendet worden.
    e = _eintrag(repo)
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    posten.befehl(argparse.Namespace(echt=False, kanal=None))
    assert json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'][0]['status'] == 'geplant'
    gerufen = []
    monkeypatch.setattr(posten.upload_post, 'senden', lambda x: gerufen.append(x) or {'zustand': 'ok', 'extern_id': 'r1'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    assert len(gerufen) == 1
    assert json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'][0]['status'] == 'veroeffentlicht'


def test_tagesdeckel_und_abstand_gegen_protokoll(repo, monkeypatch):
    e = _eintrag(repo, kanal='instagram')
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    vor_zehn = (kern.jetzt() - timedelta(minutes=10)).isoformat()
    (repo / 'arbeit/postlog.json').write_text(json.dumps([{'kanal': 'instagram', 'plan_id': 'p-0000', 'status': 'ok', 'zeit': vor_zehn}]))
    gerufen = []
    monkeypatch.setattr(posten.upload_post, 'senden', lambda x: gerufen.append(x) or {'zustand': 'ok', 'extern_id': 'ig'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    assert not gerufen, 'Mindestabstand 80 min muss greifen'


def test_offener_upload_wird_nachgefragt_nicht_neu_gesendet(repo, monkeypatch):
    e = _eintrag(repo)
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    monkeypatch.setattr(posten.upload_post, 'senden', lambda x: {'zustand': 'offen', 'extern_id': 'req-1'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    monkeypatch.setattr(posten.upload_post, 'senden', lambda x: (_ for _ in ()).throw(AssertionError('doppelt')))
    monkeypatch.setattr(posten.upload_post, 'nachfragen', lambda k, kanal=None: {'zustand': 'ok', 'url': 'https://x'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    log = json.loads((repo / 'arbeit/postlog.json').read_text())
    assert log[-1]['status'] == 'ok' and log[-1]['extern_id'] == 'req-1'


def test_offene_nachfrage_gibt_plattform_an_upload_post_weiter(repo, monkeypatch):
    # Die Statusabfrage braucht die eigene Plattform, um results[] filtern zu koennen
    # (Befund: "completed" ist nur die Gesamtzahl, nicht der eigene Erfolg).
    e = _eintrag(repo, kanal='pinterest')
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    monkeypatch.setattr(posten.upload_post, 'senden', lambda x: {'zustand': 'offen', 'extern_id': 'req-9'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    gerufen = []

    def nachfragen(kennung, kanal=None):
        gerufen.append((kennung, kanal))
        return {'zustand': 'ok', 'url': 'https://x'}

    monkeypatch.setattr(posten.upload_post, 'nachfragen', nachfragen)
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    assert gerufen == [('req-9', 'pinterest')]

def test_upload_post_anfragen_enthalten_plattformspezifische_felder(repo):
 basis={'art':'text','text':'Beschreibung','titel':'Titel','dateien':[]}
 for kanal,felder in {'tiktok':{'privacy_level','tiktok_title'},'pinterest':{'pinterest_title','pinterest_description','pinterest_board_id','pinterest_link'},'threads':{'threads_title','threads_topic_tag'}}.items():
  _,daten,_=upload_post.anfrage({**basis,'kanal':kanal});assert felder <= {k for k,_ in daten}

def test_instagram_container_finished_und_9007_geduldig(repo,monkeypatch):
 monkeypatch.setattr(instagram,'bereitstellen',lambda f:('https://media/x',lambda:None));monkeypatch.setattr(instagram.time,'sleep',lambda _:None);antworten=iter([{'id':'container'},{'status_code':'IN_PROGRESS'},{'status_code':'FINISHED'},RuntimeError("{'message':'9007'}"),{'id':'media'},{'permalink':'https://instagram/p'}]);aufrufe=[]
 def req(*a,**kw):
  x=next(antworten);aufrufe.append(a[1]);
  if isinstance(x,Exception):raise x
  return x
 monkeypatch.setattr(instagram,'_req',req);res=instagram.senden({'art':'reel','dateien':['x.mp4'],'text':'x'});assert res['extern_id']=='media' and sum(x.endswith('/media_publish') for x in aufrufe)==2

class _Exec:
 def __init__(self,v):self.v=v
 def execute(self):return self.v
class _Channels:
 def __init__(self, ident):self.ident=ident
 def list(self,**kw):return _Exec({'items':[{'id':self.ident}]})
class _Videos:
 def __init__(self):self.insertiert=[];self.aktualisiert=[]
 def insert(self,**kw):self.insertiert.append(kw);return _Exec({'id':'vid'})
 def update(self,**kw):self.aktualisiert.append(kw);return _Exec({})
class _Dienst:
 def __init__(self,ident):self.ident=ident;self.v=_Videos()
 def channels(self):return _Channels(self.ident)
 def videos(self):return self.v

def test_youtube_kanalsperre_und_upload(repo,monkeypatch):
 monkeypatch.setenv('YOUTUBE_KANAL_ID','richtig');f=repo/'ausgabe'/'x.mp4';f.write_bytes(b'x');e={'dateien':[str(f)],'titel':'T','text':'B','zeit':(kern.jetzt()-timedelta(minutes=1)).isoformat()};
 try: youtube.senden(e,_Dienst('falsch'))
 except RuntimeError: pass
 else: raise AssertionError('Kanalsperre fehlte')
 http=types.ModuleType('googleapiclient.http');http.MediaFileUpload=lambda *a,**k:object();sys.modules['googleapiclient.http']=http;d=_Dienst('richtig');assert youtube.senden(e,d)['extern_id']=='vid' and d.v.insertiert and d.v.aktualisiert


def test_youtube_titel_und_beschreibung_werden_gekuerzt(repo, monkeypatch):
    monkeypatch.setenv('YOUTUBE_KANAL_ID', 'richtig')
    f = repo / 'ausgabe' / 'x.mp4'; f.write_bytes(b'x')
    http = types.ModuleType('googleapiclient.http')
    http.MediaFileUpload = lambda *a, **k: object()
    sys.modules['googleapiclient.http'] = http
    e = {'dateien': [str(f)], 'titel': 'T' * 150, 'text': 'B' * 6000,
         'zeit': (kern.jetzt() - timedelta(minutes=1)).isoformat()}
    d = _Dienst('richtig')
    youtube.senden(e, d)
    snippet = d.v.insertiert[0]['body']['snippet']
    assert len(snippet['title']) == 100 and len(snippet['description']) == 5000
    assert '#Shorts' not in snippet['title']


def test_youtube_24h_deckel_greift_ueber_kalendertag_hinweg(repo):
    # max_uploads_24h ist eine rollende Grenze, keine Kalendertagsgrenze: drei
    # Uploads am späten Vortag müssen einen Upload kurz nach Mitternacht noch
    # sperren, auch wenn der Tagesdeckel (nach Kalenderdatum) nicht greift.
    from datetime import datetime
    now = datetime(2026, 9, 28, 1, 0, tzinfo=kern.zone())
    log = [{'kanal': 'youtube', 'plan_id': f'p-{i}', 'status': 'ok', 'trocken': False,
            'zeit': (now - timedelta(hours=20 + i)).isoformat()} for i in range(3)]
    grund = posten._grenzen_ok(log, 'youtube', now)
    assert grund and '24 Stunden' in grund


def test_supabase_upload_header_content_type_und_eindeutiger_name(repo, monkeypatch, tmp_path):
    monkeypatch.setenv('SUPABASE_URL', 'https://proj.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'geheim')
    (repo / 'konfig/kanaele.toml').write_text('[instagram]\nmedien_weg="supabase"\nbucket="medien"\n')
    video = tmp_path / 'clip.mp4'; video.write_bytes(b'x')

    class _Antwort:
        status_code = 200
        def raise_for_status(self): pass

    aufrufe = []

    def fake_post(url, headers=None, data=None, timeout=None):
        aufrufe.append((url, headers))
        return _Antwort()

    monkeypatch.setattr(medien.requests, 'post', fake_post)
    url, _aufraeumen = medien.bereitstellen(str(video))
    _, header = aufrufe[0]
    assert header['x-upsert'] == 'true'
    assert header['Content-Type'] == 'video/mp4'
    name = url.rsplit('/', 1)[-1]
    assert name != 'clip.mp4' and name.endswith('clip.mp4'), 'Name muss eindeutig, aber wiedererkennbar bleiben'
    assert url.startswith('https://proj.supabase.co/storage/v1/object/public/medien/')


def test_instagram_cover_url_wird_bei_vorhandenem_cover_gesetzt(repo, tmp_path, monkeypatch):
    video = tmp_path / 'clip.mp4'; video.write_bytes(b'x')
    (tmp_path / 'cover.jpg').write_bytes(b'x')
    monkeypatch.setattr(instagram, 'bereitstellen', lambda f: (f'https://media/{Path(f).name}', lambda: None))
    monkeypatch.setattr(instagram.time, 'sleep', lambda _: None)
    container_daten = []

    def req(method, pfad, **kw):
        if method == 'POST' and pfad.endswith('/media'):
            container_daten.append(kw.get('data', {}))
            return {'id': 'container'}
        if method == 'GET' and kw.get('params', {}).get('fields') == 'status_code':
            return {'status_code': 'FINISHED'}
        if method == 'POST' and pfad.endswith('/media_publish'):
            return {'id': 'medienobjekt'}
        return {'permalink': 'https://instagram/p'}

    monkeypatch.setattr(instagram, '_req', req)
    instagram.senden({'art': 'reel', 'dateien': [str(video)], 'text': 'x'})
    assert container_daten[0].get('cover_url') == 'https://media/cover.jpg'


def test_instagram_ohne_cover_bleibt_cover_url_weg(repo, tmp_path, monkeypatch):
    video = tmp_path / 'clip.mp4'; video.write_bytes(b'x')
    monkeypatch.setattr(instagram, 'bereitstellen', lambda f: (f'https://media/{Path(f).name}', lambda: None))
    monkeypatch.setattr(instagram.time, 'sleep', lambda _: None)
    container_daten = []

    def req(method, pfad, **kw):
        if method == 'POST' and pfad.endswith('/media'):
            container_daten.append(kw.get('data', {}))
            return {'id': 'container'}
        if method == 'GET' and kw.get('params', {}).get('fields') == 'status_code':
            return {'status_code': 'FINISHED'}
        if method == 'POST' and pfad.endswith('/media_publish'):
            return {'id': 'medienobjekt'}
        return {'permalink': 'https://instagram/p'}

    monkeypatch.setattr(instagram, '_req', req)
    instagram.senden({'art': 'reel', 'dateien': [str(video)], 'text': 'x'})
    assert 'cover_url' not in container_daten[0]


def test_instagram_png_wird_vor_dem_hochladen_zu_jpeg(tmp_path):
    from PIL import Image
    quelle = tmp_path / 'bild.png'
    Image.new('RGBA', (10, 10), (255, 0, 0, 128)).save(quelle)
    ziel, temp_erzeugt = instagram._als_jpeg(quelle)
    assert temp_erzeugt and ziel.suffix == '.jpg' and ziel.exists()
    with Image.open(ziel) as geprueft:
        assert geprueft.format == 'JPEG'


def test_instagram_karussell_hoechstens_zehn_kinder(repo, tmp_path, monkeypatch):
    dateien = []
    for i in range(12):
        f = tmp_path / f'{i:02d}.jpg'; f.write_bytes(b'x')
        dateien.append(str(f))
    monkeypatch.setattr(instagram, 'bereitstellen', lambda f: (f'https://media/{Path(f).name}', lambda: None))
    monkeypatch.setattr(instagram.time, 'sleep', lambda _: None)
    kind_aufrufe, container_daten = [], []

    def req(method, pfad, **kw):
        if method == 'POST' and pfad.endswith('/media') and kw.get('data', {}).get('is_carousel_item'):
            kind_aufrufe.append(kw['data'])
            return {'id': f'kind-{len(kind_aufrufe)}'}
        if method == 'POST' and pfad.endswith('/media'):
            container_daten.append(kw.get('data', {}))
            return {'id': 'container'}
        if method == 'GET' and kw.get('params', {}).get('fields') == 'status_code':
            return {'status_code': 'FINISHED'}
        if method == 'POST' and pfad.endswith('/media_publish'):
            return {'id': 'medienobjekt'}
        return {'permalink': 'https://instagram/p'}

    monkeypatch.setattr(instagram, '_req', req)
    instagram.senden({'art': 'karussell', 'dateien': dateien, 'text': 'x'})
    assert len(kind_aufrufe) == 10
    assert len(container_daten[0]['children'].split(',')) == 10


class _Antwort:
    def __init__(self, daten, status_code=200):
        self._daten = daten
        self.status_code = status_code

    def json(self):
        return self._daten


def test_upload_post_nachfragen_erkennt_plattformspezifischen_fehlschlag(repo, monkeypatch):
    monkeypatch.setenv('UPLOAD_POST_KEY', 'x')
    # "completed" ist nur die Gesamtzahl (UploadStatusResponse.completed/total). Wenn
    # results[] fuer die eigene Plattform success: false meldet, ist es trotzdem ein Fehler.
    antwort = _Antwort({'status': 'completed', 'completed': 2, 'total': 2, 'results': [
        {'platform': 'tiktok', 'success': True, 'message': ''},
        {'platform': 'pinterest', 'success': False, 'message': 'board not found'},
    ]})
    monkeypatch.setattr(upload_post.requests, 'get', lambda *a, **kw: antwort)
    stand = upload_post.nachfragen('req-1', 'pinterest')
    assert stand['zustand'] == 'fehler' and 'board not found' in stand['meldung']


def test_upload_post_nachfragen_ok_wenn_eigene_plattform_erfolgreich(repo, monkeypatch):
    monkeypatch.setenv('UPLOAD_POST_KEY', 'x')
    antwort = _Antwort({'status': 'completed', 'completed': 2, 'total': 2, 'results': [
        {'platform': 'tiktok', 'success': False, 'message': 'nope'},
        {'platform': 'pinterest', 'success': True, 'post_url': 'https://pin/1'},
    ]})
    monkeypatch.setattr(upload_post.requests, 'get', lambda *a, **kw: antwort)
    stand = upload_post.nachfragen('req-1', 'pinterest')
    assert stand['zustand'] == 'ok' and stand['url'] == 'https://pin/1'


def test_upload_post_senden_prueft_eigene_plattform_bei_direkter_antwort(repo, monkeypatch, tmp_path):
    # Auch ohne request_id/job_id (synchrone Antwort) zaehlt das eigene Ergebnis, nicht
    # der pauschale HTTP-Erfolg.
    monkeypatch.setenv('UPLOAD_POST_KEY', 'x')
    datei = tmp_path / 'x.jpg'
    datei.write_bytes(b'x')
    antwort = _Antwort({'success': True, 'results': [
        {'platform': 'threads', 'success': False, 'message': 'rate limited'},
    ]})
    monkeypatch.setattr(upload_post.requests, 'post', lambda *a, **kw: antwort)
    try:
        upload_post.senden({'kanal': 'threads', 'art': 'bild', 'text': 'x', 'dateien': [str(datei)]})
    except RuntimeError as x:
        assert 'rate limited' in str(x)
    else:
        raise AssertionError('haette scheitern muessen')


def test_haengender_laeuft_eintrag_wird_zur_pruefung_markiert_nicht_neu_gesendet(repo, monkeypatch):
    # Absturz-Simulation: ein "laeuft"-Eintrag ohne Nachfolger, aelter als 30 Minuten.
    e = _eintrag(repo, kanal='threads')
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    alt = (kern.jetzt() - timedelta(minutes=45)).isoformat(timespec='seconds')
    (repo / 'arbeit/postlog.json').write_text(json.dumps(
        [{'kanal': 'threads', 'plan_id': 'p-0001', 'status': 'laeuft', 'trocken': False,
          'zeit': alt, 'weg': 'upload_post'}]))
    monkeypatch.setattr(posten.upload_post, 'senden',
                         lambda x: (_ for _ in ()).throw(AssertionError('haette nicht senden duerfen')))
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    plan = json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'][0]
    assert plan['status'] == 'pruefen'
    assert plan['befunde'] and 'unterbrochen' in plan['befunde'][-1]
    log = json.loads((repo / 'arbeit/postlog.json').read_text())
    assert log[-1]['status'] == 'unklar'


def test_haengender_laeuft_trockenlauf_aendert_nichts(repo):
    e = _eintrag(repo, kanal='threads')
    plan_pfad = repo / 'arbeit/plan.json'
    kern.schreiben(plan_pfad, {'eintraege': [e]})  # kanonisch formatiert
    alt = (kern.jetzt() - timedelta(minutes=45)).isoformat(timespec='seconds')
    (repo / 'arbeit/postlog.json').write_text(json.dumps(
        [{'kanal': 'threads', 'plan_id': 'p-0001', 'status': 'laeuft', 'trocken': False,
          'zeit': alt, 'weg': 'upload_post'}]))
    vorher = plan_pfad.read_bytes()
    posten.befehl(argparse.Namespace(echt=False, kanal=None))
    assert plan_pfad.read_bytes() == vorher


def test_haengender_laeuft_frisch_wird_nicht_angefasst(repo, monkeypatch):
    # Unter 30 Minuten alt: noch als "unterwegs" behandeln, nicht als abgestuerzt.
    e = _eintrag(repo, kanal='threads')
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    frisch = (kern.jetzt() - timedelta(minutes=5)).isoformat(timespec='seconds')
    (repo / 'arbeit/postlog.json').write_text(json.dumps(
        [{'kanal': 'threads', 'plan_id': 'p-0001', 'status': 'laeuft', 'trocken': False,
          'zeit': frisch, 'weg': 'upload_post'}]))
    monkeypatch.setattr(posten.upload_post, 'senden',
                         lambda x: (_ for _ in ()).throw(AssertionError('haette nicht senden duerfen')))
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    plan = json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'][0]
    assert plan['status'] == 'geplant' and 'befunde' not in plan


def test_haengender_laeuft_mit_bekannter_kennung_wird_bei_upload_post_nachgefragt(repo, monkeypatch):
    # Kam die Antwort doch noch an, bevor der Prozess starb, ist die Kennung im
    # "laeuft"-Eintrag bekannt: dann nachfragen statt zur Pruefung markieren.
    e = _eintrag(repo, kanal='threads')
    (repo / 'arbeit/plan.json').write_text(json.dumps({'eintraege': [e]}))
    alt = (kern.jetzt() - timedelta(minutes=45)).isoformat(timespec='seconds')
    (repo / 'arbeit/postlog.json').write_text(json.dumps(
        [{'kanal': 'threads', 'plan_id': 'p-0001', 'status': 'laeuft', 'trocken': False,
          'zeit': alt, 'weg': 'upload_post', 'extern_id': 'req-alt'}]))
    monkeypatch.setattr(posten.upload_post, 'nachfragen',
                         lambda k, kanal=None: {'zustand': 'ok', 'url': 'https://x'})
    posten.befehl(argparse.Namespace(echt=True, kanal=None))
    plan = json.loads((repo / 'arbeit/plan.json').read_text())['eintraege'][0]
    assert plan['status'] == 'veroeffentlicht'
    log = json.loads((repo / 'arbeit/postlog.json').read_text())
    assert log[-1]['status'] == 'ok' and log[-1]['extern_id'] == 'req-alt'


def test_pruefen_zeigt_haengende_eintraege(repo):
    daten = {'eintraege': [{
        'id': 'p-0001', 'kanal': 'threads', 'art': 'bild', 'zeit': kern.jetzt().isoformat(),
        'status': 'pruefen', 'freigegeben': True, 'dateien': [], 'text': 'x',
    }]}
    (repo / 'arbeit/plan.json').write_text(json.dumps(daten))
    import io, contextlib
    ausgabe = io.StringIO()
    with contextlib.redirect_stdout(ausgabe):
        plan_modul.befehl_zeigen(argparse.Namespace())
    assert 'p-0001' in ausgabe.getvalue()
