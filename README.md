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

## Lizenz

Code: MIT, siehe `LICENSE`. Schriften in `schriften/`: SIL Open Font License,
je Familie eine `OFL-*.txt`.
