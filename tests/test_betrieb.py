import argparse
from pipeline import betrieb
def test_zeitplan_trocken(repo,capsys):
 (repo/'zeitplan').mkdir();(repo/'zeitplan/de.pipeline.takt.plist.vorlage').write_text('__REPO__ uv run')
 betrieb.befehl_zeitplan(argparse.Namespace(ziel=['einrichten'],trocken=True));assert 'trocken' in capsys.readouterr().out
