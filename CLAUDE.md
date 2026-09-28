# Social-Media-Pipeline

Dieses Repo macht aus einer Handy-Aufnahme Beiträge für Instagram, TikTok,
YouTube Shorts, Pinterest und Threads und veröffentlicht sie nach Plan. Die
Person, mit der du arbeitest, programmiert nicht. Erklär knapp und in ihrer
Sprache, was du tust.

## Wo was liegt

- `pipeline/`: der Code, ein Modul je Schritt. `cli.py` zeigt, welcher Befehl
  welches Modul aufruft. `ARCHITEKTUR.md` beschreibt alle Dateiformate.
- `konfig/`: alles, was die Person einstellt. `marke.toml` (Name, Farben,
  Schriften, Zielgruppe), `kanaele.toml` (Plattformen, Sendeplätze, Wege,
  Grenzen), `stile.toml` (welche Stile je Plattform), `pipeline.toml`
  (Modell, Schnittwerte, Freigabe), `sicherheitsrahmen.toml` (freie Ränder je
  Plattform).
- `vorlagen/prompts/`: die Aufträge an das Modell. Hier passt man Ton und
  Zielgruppe an, nicht im Code.
- `eingang/`: neue Rohvideos. `arbeit/`: Transkripte, Stücke, Plan, Protokolle.
  `ausgabe/`: fertige Dateien. Diese drei sind nicht im Git.

## Regeln

- **Nie echt veröffentlichen, solange die Person es nicht ausdrücklich sagt.**
  `pipeline posten` und `pipeline tag` ohne `--echt` sind Trockenläufe.
- **Geheimnisse**: `.env` nie ausgeben, nie in den Chat, nie committen.
- **Freigabe**: `[freigabe] pauschal` in `konfig/pipeline.toml` bleibt `false`,
  bis die Person bewusst entscheidet, ohne Sichtung zu senden (Modul S4).
- **Pixel statt Zeichen**: Ob Text passt, misst `pipeline/schrift.py` in Pixeln.
  Nie Zeichengrenzen für Bildtext einführen.
- **Kein Text über ffmpeg**: Das Homebrew-ffmpeg hat kein drawtext und kein
  libass. Text im Video ist immer ein Pillow-PNG plus Overlay.
- **Urteil gegen Code**: Inhaltliche Entscheidungen laufen über
  `pipeline/urteil.py`, alles andere ist Code. Keine zweite Stelle einführen,
  die ein Modell aufruft.
- **Nie still scheitern**: Jeder Schritt meldet `ok`, `befund`, `fehler` oder
  `nichts`. Ein Befund stoppt nichts, er muss sichtbar sein.
- Nach jeder Änderung am Code: `uv run pytest -q`.

## Wenn etwas nicht läuft

1. `uv run pipeline pruefen`: Ampel mit Handlungshinweis.
2. `uv run pipeline status`: was wo steht, offene Befunde.
3. `arbeit/logs/<datum>.log`: das Tagesprotokoll.
4. `arbeit/urteile.jsonl`: jeder Modellaufruf mit Auftrag und Antwort.

## Sackgassen

- Untertitel mit ffmpeg `subtitles` oder `drawtext` einbrennen: geht mit dem
  Homebrew-ffmpeg nicht. Nicht versuchen, ffmpeg neu zu bauen.
- TikTok über die eigene Schnittstelle ohne Audit: alles wird privat. Erst nach
  bestandenem Audit einen Weg `tiktok_api` bauen.
- Den Tagesdeckel für YouTube hochsetzen, weil das Kontingent reicht: Eine Flut
  von Uploads hat im Vorbild alle weiteren Shorts auf null Aufrufe gedrückt.
