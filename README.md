# Social-Media-Pipeline

Du sprichst einmal ins Handy, und daraus werden Beiträge für die ganze Woche:
Reels mit Untertiteln, YouTube Shorts, TikTok-Videos, Karussells, Pinterest-Pins
und Threads-Texte, jede Plattform mit eigener Fassung und eigenem Text. Ein Plan
verteilt sie auf Sendeplätze, und ein Takt veröffentlicht sie zur richtigen Zeit.

Das Repo ist die Vorlage zum Kurs „Die Social-Media-Pipeline“ im
Mitgliederbereich von LÄUFT. Der Kurs erklärt jeden Schritt, jede Einstellung
und die Fehler, die im echten Betrieb passiert sind.

## Schnellstart

Öffne die Claude-App und schreib deinem Claude:

> Hol dir https://github.com/philip-macht-ki/social-pipeline auf meinen Schreibtisch
> und richte es nach der Datei einrichten.md darin ein.

Mehr musst du nicht tun. Claude lädt alles, installiert, was fehlt, und fragt
dich nach deiner Marke. Ein GitHub-Konto brauchst du dafür nicht; mit einem
kostenlosen Konto kann Claude dir später Neuerungen holen („Hol die neueste
Fassung der Pipeline“).

Wer lieber selbst im Terminal arbeitet:

```
git clone https://github.com/philip-macht-ki/social-pipeline.git
cd social-pipeline
brew install ffmpeg uv
uv sync --extra mac --extra dev --extra youtube
uv run pipeline pruefen
uv run pipeline beispiel
uv run pipeline tag
uv run pipeline zeigen
```

Das läuft komplett im Trockenlauf. Veröffentlicht wird erst mit `--echt` und
nur, was freigegeben ist.

## Was passiert

| Schritt | Befehl | Wer entscheidet |
|---|---|---|
| Neue Aufnahmen übernehmen | `pipeline eingang` | Code |
| Jedes Wort mit Zeitstempel, lokal | `pipeline transkript` | Code (Whisper) |
| Aufnahme in Stücke nach Themen | `pipeline zerlegen` | Modell, Code prüft Satzkanten und Längen |
| Stärksten ersten Satz nach vorn | `pipeline hook` | Modell, Code entscheidet nach Punkten |
| Pausen raus, Bild und Ton sauber | `pipeline bauen` | Code |
| Fassung je Plattform mit Untertiteln | `pipeline fassungen` | Code |
| Texte je Plattform | `pipeline texte` | Modell, Code prüft Grenzen |
| Bilder, Karussells, Pins, Threads | `pipeline bilder` | Modell für Text, Code für Bild |
| Auf Sendeplätze verteilen | `pipeline planen` | Code |
| Ansehen und freigeben | `pipeline zeigen`, `pipeline freigeben` | du |
| Veröffentlichen | `pipeline posten --echt` | Code |
| Lücken melden | `pipeline vorrat`, `pipeline status` | Code |
| Verbrauch ansehen | `pipeline verbrauch` | Code |
| KI-Monatsbudget ansehen | `pipeline ki-budget` | Code |
| Alles in einem Lauf | `pipeline tag` | |
| Automatisch alle 20 Minuten | `pipeline zeitplan einrichten` | |

## Stile je Plattform

| Plattform | Stile |
|---|---|
| Instagram Reel | `klar`, `titelband`, `stichworte` |
| Instagram Bild | `zitat_standbild`, `zahl`, `einwand`, `vorher_nachher`, `raster`, `notiz` |
| Instagram Karussell | `schritte`, `kette`, `woche_hell` |
| TikTok | Video wie Reel mit höheren Untertiteln, Fotobeitrag `foto_schritte`, `foto_zitat` |
| YouTube Short | wie Reel, eigener Titel, nur bis 179 Sekunden |
| Pinterest | `spickzettel`, `szene`, `notizbuch`, `editorial`, `typomix`, `tabelle`, `toolraster`, `statistik` |
| Threads | `merksatz`, `einwand`, `zahl`, `frage`, `kette`, `bild_zeile` |

An und aus in `konfig/stile.toml`.

## Veröffentlichen

Je Plattform in `konfig/kanaele.toml` ein Weg:
- `upload_post`: über upload-post.com, ein Schlüssel für TikTok, Pinterest,
  Threads und Instagram. Einfachster Start.
- `instagram_api`: Instagram über die eigene Meta-App.
- `youtube_api`: YouTube Shorts über ein eigenes Google-Cloud-Projekt.

TikTok über die eigene Schnittstelle stellt ohne bestandenes TikTok-Audit alles
privat ein. Deshalb gibt es diesen Weg hier noch nicht.

## Voraussetzungen

Mac mit Apple-Chip, 16 GB Arbeitsspeicher, rund 30 GB frei. Claude Code mit
Pro-Abo oder höher (die inhaltlichen Entscheidungen laufen über `claude -p`).
ffmpeg und uv über Homebrew.

### Welches Abo reicht

Jedes Urteil ruft `claude -p` schlank auf: ohne Werkzeuge, ohne MCP-Server,
ohne CLAUDE.md. Das sind rund 5.000 Tokens statt rund 60.000 (gemessen am
29.09.2026). Eine Aufnahme mit vier Stücken braucht damit etwa 100.000 Tokens.
Das Transkript rechnet Whisper lokal: kostet nichts und die Aufnahme bleibt
auf deinem Mac. Es hört in Fenstern von 12 bis 22 Sekunden, geschnitten in
Sprechpausen, weil Whisper am Stück nach einer Weile Satzzeichen verliert und
sich öfter verhört. Den Satz `prompt` unter `[transkript]` in
`konfig/pipeline.toml` passt du an deine Wörter an (Namen, Werkzeuge).

| Wie du arbeitest | Abo |
|---|---|
| Eine Aufnahme am Tag, Einrichtung über ein paar Abende verteilt | Claude Pro, 20 € im Monat |
| Zwei bis drei Aufnahmen am Tag, oder Einrichtung an einem Wochenende, oder Claude auch sonst täglich im Einsatz | Claude Max 5x, rund 100 € im Monat |
| Mehrere Marken, Claude den ganzen Tag im Dauerbetrieb | Claude Max 20x, rund 200 € im Monat |
| Du stößt an die Grenze und willst nicht hochstufen | ChatGPT Plus mit Codex dazu, rund 23 € im Monat, `backend = "codex"` unter `[urteil]` in `konfig/pipeline.toml` (oder einmalig `URTEIL_BACKEND=codex`) |

Anthropic veröffentlicht keine festen Token-Zahlen je Abo; die Tabelle ist ein
Richtwert. `uv run pipeline verbrauch` zeigt, was die Pipeline je Tag wirklich
gebraucht hat, und in der Claude-App steht unter Einstellungen, Nutzung, wie
viel vom Fenster übrig ist.

## KI-Video umbauen und erzeugen

Der Ordner `umbau/` baut aus einer eigenen Handyaufnahme per KI ein neues
Video: Gegenstand, Fensterblick oder Outfit ändern sich, Gesicht und Stimme
bleiben echt. Dasselbe Werkzeug kann auch Clips ganz ohne Kamera erzeugen,
aus einem gemalten Storyboard. Beides erklärt `umbau/README.md`, dazu Kosten
in Euro je Sekunde, Modellwahl und die Fallen aus dem echten Betrieb. Im Kurs
ist das Modul S7 „KI-Video: umbauen und erzeugen".

Unter `[ki]` in `konfig/pipeline.toml` steht der Monatsdeckel fuer kostenpflichtige
KI-Videos. `einblendung = false` ist der sichere Standard. Wenn sie eingeschaltet
ist, setzt die Pipeline hoechstens eine kurze Szene je Reel ein und faellt bei
fehlendem Budget oder Modell immer auf das normale Rohvideo zurueck.

## Lizenz

Code: MIT, siehe `LICENSE`. Schriften in `schriften/`: SIL Open Font License,
je Familie eine `OFL-*.txt`.
