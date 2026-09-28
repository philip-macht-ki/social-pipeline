"""Erzeugt ein Beispielvideo in eingang/, damit die ganze Kette ohne eigene Aufnahme läuft.

Die Stimme kommt von macOS (`say`), das Bild ist ein ruhiger Verlauf mit einer
hellen Ellipse als "Kopf" auf Augenhöhe. Der Sprechtext hat drei klar
getrennte Themen, jedes lang genug für ein eigenes Stück (über 30 Sekunden
nach dem Pausenschnitt), mit einem Anlauf ("äh, also") und kurzen Pausen,
damit Zerlegen, Hook und Pausenschnitt etwas zu tun haben.
"""
from __future__ import annotations

import subprocess
import tempfile

from PIL import Image, ImageDraw

from .kern import dauer, pfad

TEXT = """Letzte Woche hat mir eine Kundin geschrieben, dass sie seit drei Monaten nichts mehr gepostet hat. [[slnc 1100]] Nicht, weil ihr die Ideen fehlen. Sie hat jeden Abend eine Idee, und jeden Abend ist sie zu müde, um daraus einen Beitrag zu machen. [[slnc 900]] Genau das ist der Punkt. Das Problem ist nicht der Inhalt, sondern die zwanzig Handgriffe zwischen dem Gedanken und dem fertigen Video. Schneiden, Untertitel, ein Titel, ein Text, der richtige Zeitpunkt. Wenn diese Handgriffe verschwinden, bleibt nur noch das, was sie ohnehin gut kann: reden. [[slnc 1100]] Und reden dauert fünf Minuten am Tag. [[slnc 2600]]
Äh, also, der zweite Punkt ist die Frage, was man überhaupt aufnimmt. [[slnc 1100]] Die meisten warten auf das perfekte Thema. Dabei liegen die Themen längst in deinem Postfach. Jede Frage, die dir ein Kunde zweimal stellt, ist ein Beitrag. [[slnc 900]] Schreib dir eine Woche lang jede dieser Fragen auf. Am Freitag hast du zehn Themen, und jedes davon hat schon einmal jemanden interessiert. Das ist mehr, als die meisten in einem Monat finden. [[slnc 1100]] Nimm dir morgen früh die erste Frage und beantworte sie so, wie du es am Telefon tun würdest. [[slnc 2600]]
Am Freitag ist bei mir ein Video mit dreißig Sekunden Stille am Anfang rausgegangen. [[slnc 1100]] Niemand hat es gemerkt, bis die Zahlen kamen. Fast keine Aufrufe. [[slnc 900]] Seitdem prüft die Pipeline jedes Stück, bevor es geplant wird. Sie misst die Länge, sie schaut, ob der Ton da ist, und sie meldet einen Befund, statt still weiterzumachen. Das ist der eigentliche Wert von so einem System. Nicht, dass es alles alleine macht, sondern dass es dir sagt, wenn etwas nicht stimmt. [[slnc 1100]] Welche Frage hörst du diese Woche am häufigsten?"""

SPRECHTEMPO = 165  # Wörter je Minute, etwa normales Sprechtempo


def _stimme() -> str | None:
    stimmen = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    for bevorzugt in ("Anna", "Petra", "Markus"):
        if any(z.startswith(bevorzugt + " ") for z in stimmen.splitlines()):
            return bevorzugt
    return next((z.split()[0] for z in stimmen.splitlines() if "de_DE" in z), None)


def befehl(args) -> int:
    ziel = pfad("eingang", "beispiel.mov")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists() and not args.neu:
        print("nichts: Beispielvideo liegt schon in eingang/ (mit --neu neu erzeugen)")
        return 0
    try:
        stimme = _stimme()
        if not stimme:
            print("befund: Keine deutsche Stimme gefunden. Systemeinstellungen, Bedienungshilfen, "
                  "Gesprochene Inhalte, Systemstimme, eine deutsche Stimme laden.")
        with tempfile.TemporaryDirectory() as tmp:
            audio = f"{tmp}/ton.aiff"
            cmd = ["say", "-o", audio, "-r", str(SPRECHTEMPO)] + (["-v", stimme] if stimme else []) + [TEXT]
            subprocess.run(cmd, check=True)
            laenge = dauer(audio) + 1.0
            kopf = f"{tmp}/kopf.png"
            bild = Image.new("RGBA", (260, 360), (0, 0, 0, 0))
            ImageDraw.Draw(bild).ellipse((0, 0, 260, 360), fill="#f1e8d6")
            bild.save(kopf)
            # Kein drawtext und kein zoompan: die Kopfellipse ist eine eigene Bildspur.
            # y = 500 legt die Ellipsenmitte auf etwa 0,36 der Bildhöhe (Augenlinie).
            filt = "[0:v][1:v]overlay=x=410+20*sin(t):y=510+12*sin(0.7*t)[aus]"
            quelle = f"gradients=s=1080x1920:r=30:c0=#243246:c1=#6b1f2a:duration={laenge:.1f}:speed=0.002"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", quelle, "-loop", "1", "-i", kopf, "-i", audio,
                 "-filter_complex", filt, "-map", "[aus]", "-map", "2:a", "-t", f"{laenge:.1f}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(ziel)],
                check=True, capture_output=True, text=True,
            )
        print(f"ok: Beispielvideo {ziel.name} erzeugt, {dauer(ziel):.0f} s, Stimme {stimme or 'Standard'}")
        return 0
    except Exception as e:
        print(f"fehler: Beispielvideo: {e}")
        return 1
