# Umbau: dein eigenes Handyvideo per KI verändern

Zwei Dinge kann dieser Ordner:

1. **Eine echte Aufnahme von dir umbauen.** Du filmst dich einmal selbst, und
   die KI tauscht einzelne Abschnitte aus: dein T-Shirt wird ein Hawaiihemd,
   der Blick aus dem Fenster wird London, der Stift in deiner Hand wird ein
   Apfel. Dein Gesicht, deine Stimme und deine Bewegung bleiben echt.
2. **Einen Clip ganz ohne Kamera erzeugen**, aus einem gemalten Storyboard.
   Gut für Werbeclips oder Erklärclips ohne Gesicht.

Du musst dafür nicht programmieren können. Alles, was Claude für dich
übernimmt, steht unten als fertiger Satz zum Kopieren.

## Was das kostet

OpenRouter rechnet in Dollar ab, deshalb unten beide Angaben; die Euro-Beträge
sind zum Kurs vom 30.09.2026 (1 € = 1,1355 $) gerechnet und schwanken mit dem
Wechselkurs leicht. Ein ganzes Umbau-Reel mit mehreren Abschnitten kostet
meist zwischen 1 und 1,30 Euro. Ein Werbeclip ohne Kamera kostet rund
3,30 Euro. Das sind Beträge für Rechenzeit, keine Abos: du zahlst nur für
das, was du wirklich erzeugst.

| Werkzeug | Wofür | Preis (ungefähr) |
|---|---|---|
| `black-forest-labs/flux-video-edit` | **Deine echte Aufnahme umbauen**: Gegenstand, Fensterblick, Outfit | rund 2,6 Cent je Sekunde (3 Cent-Dollar) |
| `runway/aleph-2` | Premium-Alternative zum Umbauen, manchmal natürlicheres Gesicht | rund 25 Cent je Sekunde (28 Cent-Dollar) |
| `bytedance/seedance-2.0` | **Neue Szenen ohne Gesicht erzeugen**: Werbeclip, Erklärclip, aus Storyboard | rund 33 Cent je Sekunde (ca. 38 Cent-Dollar) in 1080x1920 |
| `bytedance/seedance-2.0-fast` | Schneller, günstiger Test in 720p | rund 8 Cent je Sekunde (ca. 9 Cent-Dollar) |
| `black-forest-labs/flux-video-upscale` | Optional schärfen | rund 12 Cent je Sekunde (ca. 14 Cent-Dollar), nur bei großen Flächen nah an der Kamera spürbar besser |
| Maske beim Einsetzen | Qualität ohne Aufpreis | 0, immer an |

Merksatz dazu: **FLUX, wenn du dich selbst umbaust. Seedance, wenn du etwas
ohne Kamera erzeugst. Die Maske macht den Unterschied.**

Echte Beispielrechnung aus einem echten Lauf: fünf Umbauten mit
flux-video-edit (zusammen 33 Sekunden) kosteten 1,03 Euro (1,17 Dollar), mit
Maske ohne Aufpreis. Ein Werbeclip mit Seedance (10 Sekunden) kostete
3,31 Euro (3,76 Dollar). Derselbe Abschnitt mit der Premium-Alternative
Aleph statt FLUX kostete für nur 4,4 Sekunden 1,23 Euro (1,40 Dollar), der
optionale Schärfer für dieselben 4,4 Sekunden 0,55 Euro (0,62 Dollar).

## Einrichtung

Sag deinem Claude:

> Richte den Ordner umbau nach umbau/README.md ein. Ich brauche noch ein
> OpenRouter-Konto mit Guthaben, danach leg den Schlüssel sicher im
> Schlüsselbund ab, ich füge ihn ein, wenn du fragst.

Was dabei passiert:

1. **OpenRouter-Konto.** Du legst selbst ein Konto auf openrouter.ai an und
   lädst etwa 10 Dollar Guthaben auf, rund 9 Euro (OpenRouter rechnet nur in
   Dollar ab). Das reicht für rund acht Umbau-Reels oder zwei Werbeclips plus
   ein paar Tests. Danach erzeugst du dort einen Schlüssel (eine lange
   Zeichenfolge, die mit `sk-or-` beginnt).
2. **Schlüssel im Schlüsselbund.** Gib den Schlüssel nie in den Chat.
   Claude legt ihn für dich im macOS-Schlüsselbund unter dem Namen
   `openrouter-api-key` ab, du fügst den Wert nur einmal in den
   Schlüsselbund-Dialog ein. Von da an liest jedes Werkzeug hier ihn selbst
   aus. Wer lieber eine Umgebungsvariable nutzt, setzt stattdessen
   `OPENROUTER_API_KEY`.
3. **Google Drive mit rclone.** OpenRouter nimmt Videos und Bilder nur als
   kurzzeitige HTTPS-Adresse, keine Datei direkt. Claude richtet dafür
   `rclone` mit deinem Google-Drive-Konto ein (ein Remote namens `gdrive`),
   du bestätigst das einmal im Browser. Die Dateien landen kurz in
   `gdrive:umbau-tmp` und werden danach wieder endgültig gelöscht, nie im
   Papierkorb liegen gelassen (aus dem Papierkorb bleibt der Link sonst
   weiter abrufbar). Einen anderen Ordner nutzt du über die
   Umgebungsvariable `UMBAU_RCLONE_ZIEL`.
4. Für Lektion 2 (Storyboard) brauchst du zusätzlich ein Bildwerkzeug, mit
   dem jemand dir ein Storyboard malt: Codex im ChatGPT-Abo oder ChatGPT
   Plus reicht. Für eigene Musik optional ein ElevenLabs-Konto (Schlüssel
   im Schlüsselbund unter `elevenlabs-api-key`, oder Umgebungsvariable
   `ELEVENLABS_API_KEY`).

## Ablauf 1: deine eigene Aufnahme umbauen

So nimmst du auf: **Hochformat, 9:16** (wie ein normales Reel), iPhone-Kamera
ohne HDR, 30 Bilder pro Sekunde (HDR wirkt nach der Umrechnung flau, 24 Bilder
pro Sekunde ruckeln im Schnitt). Handy fest halten. Kündige im Satz an, was
passiert ("mein Stift, oder besser: mein Zauberstab"), und gib bei einem
Wechsel ein klares Signal, zum Beispiel ein Klatschen.

Alle Befehle unten arbeiten in einem einzigen, einheitlichen Arbeitsordner
je Video, zum Beispiel `umbau/arbeit/<name>`. Leg ihn einmal an (oder lass
ihn von Claude anlegen) und bleib dann für diese Aufnahme konsequent bei
genau diesem Pfad, auch wenn du die Befehle aus einem anderen Verzeichnis
heraus aufrufst.

Sag deinem Claude danach:

> Ich hab eine Aufnahme <Datei> abgelegt. Mach ein Transkript mit Wortzeiten,
> schlag mir Abschnitte für einen Umbau vor und bau sie dann mit umbau/ um,
> alles im Arbeitsordner umbau/arbeit/<name>.

Was dabei im Hintergrund passiert:

1. **Transkript mit Wortzeiten.** Falls die Pipeline schon eingerichtet ist,
   nutzt Claude `uv run pipeline transkript`. Sonst reicht ein lokales
   Whisper-Werkzeug (`mlx_whisper` auf einem Mac mit Apple-Chip, sonst
   `faster-whisper`), das jedes Wort mit Start- und Endzeit ausgibt.
2. **Abschnitte festlegen.** Aus den Wortzeiten entsteht
   `umbau/arbeit/<name>/abschnitte.json`: eine Liste von
   `{"name": "hawaii", "von": 39.74, "bis": 44.10}`. Ein Abschnitt beginnt
   kurz vor dem Wort, das den Umbau ankündigt, und endet vor dem nächsten.
   Höchstens etwa 11 Sekunden je Abschnitt.
3. **Vorlage und Abschnitte schneiden:**
   `python3 umbau/abschnitte.py <aufnahme> umbau/arbeit/<name>`
   baut `umbau/arbeit/<name>/master.mov` (die durchgehende Vorlage) und je
   Eintrag `umbau/arbeit/<name>/seg-<abschnittsname>.mp4`.
4. **Umbauen**, je Abschnitt einmal:
   `python3 umbau/umbauen.py umbau/arbeit/<name>/seg-<abschnittsname>.mp4 umbau/arbeit/<name>/edit-<abschnittsname>.mp4 "<prompt>"`
   Jeder Prompt endet mit einem Behalte-Satz, der alles andere unverändert
   lässt (siehe unten). Optional danach schärfen mit
   `--modell black-forest-labs/flux-video-upscale` über dasselbe Werkzeug,
   oder mit der Premium-Alternative `--modell runway/aleph-2`.
5. **Ansehen, bevor du weitermachst.** Lass dir von Claude einen Kontaktbogen
   bauen (ein Bildraster über die Dauer des Clips) und sieh jeden Umbau an.
   Wirkt ein Gegenstand falsch, wirf den Versuch weg und beschreibe ihn
   genauer (siehe Fallen unten).
6. **Wandfeld für den Farbabgleich markieren (Pflichtschritt).** Das
   Umbaumodell gibt das Bild oft dunkler zurück, und wie stark hängt von
   deiner Aufnahme ab, nicht von einem festen Wert. Sag deinem Claude:
   "Markiere auf einem Standbild ein Stück Wand, das in keinem Umbau
   verändert wird, und zeig es mir." Du bekommst daraus vier Zahlen
   (B:H:X:Y, also Breite:Höhe:X:Y in Pixeln).
7. **Einsetzen mit Maske und Farbabgleich:**
   `python3 umbau/einsetzen.py umbau/arbeit/<name> --feld B:H:X:Y`
   Ohne `--feld` bricht das Werkzeug mit einer klaren Meldung ab, statt ein
   Feld zu raten, das zu deiner Aufnahme gar nicht passt. Das Ergebnis ist
   `umbau/arbeit/<name>/master_umbau.mov`: dieselbe Zeitachse wie deine
   Aufnahme, Originalton, nur die Abschnitte sind ausgetauscht.

   Was die Maske wirklich tut: Sie übernimmt nur, was sich zwischen Original
   und Umbau deutlich verändert hat (Hemd, Fensterblick, Gegenstand). Gesicht
   und Arme bleiben in der Regel echtes Video, weil sie sich dort kaum
   ändern, nicht weil die Maske sie erkennt. Prüf das Ergebnis am
   Kontaktbogen: Flackert ein Rand am Hals oder Ärmel, probier
   `--schwelle 35` bis `--schwelle 45`. Fehlt ein dünner Gegenstand
   zeitweise, probier `--schwelle 20`.
8. **Schneiden.** `umbau/arbeit/<name>/master_umbau.mov` geht danach in den
   normalen Schnitt deiner Pipeline, genau wie jede andere Aufnahme.

### Prompts, die funktioniert haben

Jeder Prompt endet mit diesem Satz, damit alles andere gleich bleibt:

> Keep everything else exactly identical frame by frame: the person's face,
> expression, mouth movements, hand and arm movements, timing, camera, the
> room and the lighting. Do not add any text or logos.

Beispiele:

- Gegenstand: "Replace the pencil in the person's hand with a shiny red
  apple. Whenever it moves or gets tossed, the apple moves and flies the
  same way and lands back in the hand."
- Fensterblick: "Replace the view through the window on the left with a New
  York view: Manhattan skyscrapers, the Empire State Building clearly
  visible, window frame unchanged." Ein Wahrzeichen ausdrücklich groß
  verlangen, sonst steht es nur klein am Horizont.
- Outfit: "Change the person's plain t-shirt into a loud colorful Hawaiian
  shirt with a collar and short sleeves, bright turquoise and orange
  hibiscus flowers. The arms below the sleeves stay unchanged."

## Ablauf 2: ein Clip ganz ohne Kamera (Storyboard)

Für Werbeclips oder Erklärclips ohne Gesicht: erst malt dir jemand ein
Storyboard, danach setzt Seedance es als Video um.

1. **Storyboard malen lassen** (Codex oder ChatGPT, 2 Spalten mal 5 Zeilen,
   ein Feld je Sekunde). Regeln dabei: keine Schrift im Bild (Bildmodelle
   malen nur Buchstabenähnliches), keine Gesichter (Seedance lehnt sie ab,
   und bei einer bezahlten Anzeige lehnt auch Meta die Kombination aus
   Gesicht und Angebot ab), Hände sind in Ordnung, Farbwelt deiner Marke.
   Hast du schon einen echten Screenshot oder ein Mockup, gib ihn als
   Vorlage mit, sonst male das Storyboard den falschen Klickweg.
2. **Video erzeugen:**
   `python3 umbau/storyboard_video.py storyboard.png ziel.mp4 "folge dem Storyboard Feld für Feld, eine Sekunde je Feld"`
   Zum günstigen Testen in 720p:
   `python3 umbau/storyboard_video.py storyboard.png test.mp4 "folge dem Storyboard Feld für Feld, eine Sekunde je Feld" --modell bytedance/seedance-2.0-fast --dauer 4 --size 720x1280`
   Mit einem `-fast`-Modell setzt `storyboard_video.py` `--dauer 4` und
   `--size 720x1280` auch automatisch, wenn du sie weglässt; ausdrücklich
   angegebene Werte haben trotzdem Vorrang.
3. **Endkarte und Schritt-Einblendungen** baust du am besten als HTML und
   rendertst sie mit einem Headless-Browser, dann stimmen Schrift und
   Abstand. Bildschirmschrift kommt in Seedance nur angedeutet, deshalb
   Schritte als Einblendung darüberlegen, nicht erhoffen, dass Seedance sie
   lesbar malt.
4. **Eigene Musik:**
   `python3 umbau/musik.py musik.mp3 10 "ruhiger, moderner Beat, warm, treibend"`
   Eigene Erzeugung heißt keine Rechteprobleme mit fremder Musik.

## Fallen aus dem echten Betrieb

- **Keine Marken- oder Werknamen im Prompt.** "wie bei Harry Potter" wird
  als geschütztes Werk abgelehnt, kostet aber nichts. Beschreiben statt
  benennen löst es fast immer.
- **Dünne Gegenstände werden gern zu dick.** Ein erster Zauberstab sah aus
  wie ein Knüppel. "thin, slim like a pencil, tapering to a fine point" hat
  geholfen.
- **Wahrzeichen stehen sonst klein am Horizont.** Willst du sie groß im
  Bild, verlang das ausdrücklich.
- **503 "over capacity" heißt warten, nicht kaputt.** `umbauen.py`
  wiederholt das automatisch bis zu vier Mal im Abstand von 30 Sekunden.
- **Das Umbaumodell gibt das Bild oft 4 bis 13 Prozent dunkler zurück.**
  Deshalb immer mit `einsetzen.py` einsetzen, nie die Umbau-Datei roh
  überlagern.
- **`resolution` und `aspect_ratio` lehnt flux-video-edit ab.** Es übernimmt
  Format und Länge der Eingabe von selbst. Diese Felder nie mitschicken.
- **Unbekannte Felder werden still ignoriert, und der Auftrag läuft trotzdem
  los.** Das kostet echtes Geld für einen Test, der nie ankam. Ein neues
  Modell deshalb nie mit einem echten Aufruf ausprobieren, sondern erst mit
  `python3 umbau/schema_pruefen.py <modellname>`. Das schickt absichtlich
  einen falschen Typ, kostet nichts und zeigt in der Fehlermeldung meist die
  erwarteten Felder.
- **Videos und Bilder gehen nur als HTTPS-Adresse an OpenRouter.** Dieser
  Ordner legt sie dafür kurz über rclone auf Google Drive und löscht sie
  danach sofort wieder endgültig, nicht nur in den Papierkorb (von dort
  bliebe der Link weiter abrufbar).

## Sag deinem Claude

Fertige Sätze zum Kopieren:

> Richte den Ordner umbau nach umbau/README.md ein.

> Bau in meiner Aufnahme <Datei> das T-Shirt in ein Hawaiihemd um, nur den
> Abschnitt ab Sekunde 3, und setz es mit Maske ein.

> Zeig mir mein OpenRouter-Guthaben und rechne aus, wie viele Umbau-Reels
> und Werbeclips es noch reicht.

> Prüf das Schema von <neuer Modellname>, bevor wir damit etwas erzeugen.
