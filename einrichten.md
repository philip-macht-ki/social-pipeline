# Einrichten: gib diese Datei deinem Claude

Du bist der Claude einer selbstständigen Person, die nicht programmiert. Sie hat
dieses Repo gerade auf ihren Mac geholt und diesen Ordner in der Claude-App
geöffnet. Richte die Pipeline ein. Arbeite die Schritte der Reihe nach ab,
erkläre jeden in einem Satz, bevor du ihn ausführst, und frag nach, wo unten
„fragen“ steht.

## 1. Ziel

Die Pipeline läuft auf diesem Mac: Aus dem mitgelieferten Beispielvideo
entstehen im Trockenlauf fertige Reels, Bilder, Texte und ein Sendeplan. Es
wird nichts veröffentlicht.

## 2. Abnahme

Fertig ist es erst, wenn du diese Befehle selbst ausgeführt hast und die
Ausgaben zeigst:

```
uv run pipeline pruefen
```
Keine Zeile ROT. GELB bei den Schlüsseln ist in Ordnung, die kommen in Modul S5.

```
uv run pipeline beispiel
uv run pipeline tag
```
Am Ende steht „Tageslauf fertig“, und es gibt:
- mindestens eine Datei `ausgabe/*/instagram.mp4`, ansehen mit `open`
- `ausgabe/*/texte.json`
- Bilder unter `ausgabe/bilder/`, darunter mindestens zwei Pinterest-Pins
- Einträge in `arbeit/plan.json`
- Zeilen mit `"trocken": true` in `arbeit/postlog.json`

## 3. Schritte

1. **Homebrew prüfen**: `brew --version`. Fehlt es, erklär, was Homebrew ist
   (ein Installationsprogramm für Werkzeuge auf dem Mac), und **frag**, ob du
   es installieren darfst. Der Befehl steht auf https://brew.sh. Er fragt nach
   dem Mac-Passwort; das tippt die Person selbst im Terminal ein, nie in den Chat.
2. **ffmpeg und uv**: `brew install ffmpeg uv`, falls `ffmpeg -version` oder
   `uv --version` fehlen.
3. **Python-Pakete**: `uv sync --extra mac --extra dev --extra youtube`. Auf einem
   Mac mit Apple-Chip läuft die Spracherkennung dann lokal; `--extra youtube` ist
   dabei, weil YouTube in `konfig/kanaele.toml` standardmäßig an ist.
4. **Marke eintragen**: Öffne `konfig/marke.toml` und **frag** nach den
   Angaben aus Abschnitt 5. Trag sie ein. Farben als Hex-Wert; kennt die
   Person ihren Hex-Wert nicht, schlag zwei Farben vor und lass sie wählen.
5. **Plattformen**: In `konfig/kanaele.toml` die Plattformen auf `an = false`
   setzen, die sie nicht bespielen will. Sonst nichts ändern.
6. **Spiegeln prüfen**: **Frag**, ob ihre Frontkamera spiegelt (Test: einen
   Text vor die Kamera halten und aufnehmen; ist er in der Aufnahme
   seitenverkehrt, ja). Dann in `konfig/pipeline.toml` unter `[schnitt]`
   `entspiegeln = true`.
7. **Schlüsseldatei anlegen**: `cp .env.example .env`. Die Werte trägt die
   Person selbst ein, später, in Modul S5. Du liest `.env` nie aus und gibst
   keinen Wert aus.
8. **Selbsttest**: `uv run pipeline pruefen`. Ist eine Zeile ROT, behebe die
   Ursache und prüfe erneut.
9. **Erster Durchlauf**: `uv run pipeline beispiel`, dann
   `uv run pipeline tag`. Beim ersten Mal lädt die Spracherkennung ihr Modell
   (rund 1,5 GB). Das dauert einige Minuten und sieht aus, als würde nichts
   passieren. Warte.
10. **Zeigen**: Öffne das erste `instagram.mp4` mit `open`, zeig die Liste der
    erzeugten Dateien und die ersten Planeinträge (`uv run pipeline zeigen`).

## 4. Verboten

- Nichts veröffentlichen. Nie `--echt` benutzen.
- Keine Konten anlegen, keine Schlüssel erzeugen, nichts bezahlen.
- `.env` nicht lesen, keinen Schlüssel in den Chat schreiben.
- Nichts außerhalb dieses Ordners löschen oder ändern. Ausnahme: Homebrew,
  ffmpeg und uv nach Rückfrage installieren.
- Keinen Zeitplan einrichten (`pipeline zeitplan`). Das kommt in Modul S4 und
  schreibt nach `~/Library/LaunchAgents`, was eine eigene Rückfrage braucht.

## 5. Fragen, bevor du etwas einträgst

- Name der Marke, wie er klein auf jedem Beitrag stehen soll
- Handle, etwa @name
- Zielgruppe in einem Satz („für wen sprichst du?“)
- Link, auf den Beiträge verweisen
- Akzentfarbe und dunkle Grundfarbe
- Welche Plattformen: Instagram, TikTok, YouTube Shorts, Pinterest, Threads
- Spiegelt die Frontkamera?
- Soll unter Instagram-Beiträgen ein Aufruf stehen (`cta_zeile`)? Wenn ja, welcher?

Rate nichts. Fehlt eine Angabe, frag. Lässt die Person etwas offen, trag nichts
ein und schreib es in den Abschlussbericht.

## 6. Abschlussbericht

Kurz, in dieser Reihenfolge:
1. Was eingetragen wurde (Marke, Farben, Plattformen, Spiegeln)
2. Ausgabe von `uv run pipeline pruefen`, gekürzt
3. Erzeugte Dateien mit Größe (`ls -la ausgabe/*/`)
4. Die ersten fünf Planeinträge
5. Offene Befunde und was noch fehlt
6. Der nächste Schritt: eine eigene Aufnahme in `eingang/` legen (Modul S1)
