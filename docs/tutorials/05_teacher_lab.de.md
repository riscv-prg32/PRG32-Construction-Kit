# Lektion 5: eine Laborstunde für die Lehrkraft

Ziel: eine Unterrichtsaktivität von 45 Minuten durchführen.

## Vorbereitung

1. Starte PRG32-Construction-Kit. Mit Docker (`docker compose up -d --build`)
   funktioniert das Bauen von Cartridges sofort. Prüfe es vor der Stunde mit
   `docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2`
   (siehe `../install_cartridge_build.md`).
2. Optional: starte den Cartridge Store.
3. Optional: schließe ein PRG32-Gerät an oder richte QEMU ein.
4. Prüfe, dass die Schülerinnen und Schüler die Web-App öffnen können.

## 0-5 Minuten: Vorführung

Zeige das Startprojekt. Bewege das Quadrat der Spielfigur im Simulator.

## 5-20 Minuten: die Klasse baut

Die Schülerinnen und Schüler ändern:

- die Farbe der Spielfigur;
- die Geschwindigkeit der Spielfigur;
- die Startposition;
- den Titeltext.

## 20-30 Minuten: Gespräch über das erzeugte C

Die Klasse klickt auf **Erzeugen** und öffnet `game.c` unter **Erzeugt (nur lesen)**, um die
C-Anweisung zu finden, die ein Block erzeugt. Ältere Schülerinnen und Schüler öffnen daneben
`game.S` und finden denselben Block im Assembler: Sein Kommentar zeigt die C-Zeile, und jede
Anweisung sagt, was sie tut (siehe `../generated_code.md`). `game.py` zeigt dieselben Blöcke in
PRG32 Python.

## 30-40 Minuten: Sprites und Artefakte

Die Klasse zeichnet ein Sprite, wandelt es in C um und lädt das Artefakt herunter.
Gibt es eine PRG32-Platine oder QEMU, klicken die Schülerinnen und Schüler auf **Kompilieren**,
laden im Tab **Build** herunter und laden ihre eigene PRG32-Cartridge.

## 40-45 Minuten: Rückblick

Frage:

- Welcher Block hat eine Variable geändert?
- Zu welcher C-Anweisung ist er geworden?
- Welche RISC-V-Anweisungen machen dieselbe Arbeit?
- Warum hilft der Simulator, bevor man auf die Hardware geht?
- Was steckt in einer `.prg32`-Cartridge im Vergleich zum erzeugten C?

## Danach: eine Einheit über klassische Spiele

Die fünf fertigen Spiele in `examples/games/` haben jeweils eine Lektion von 90 bis 120 Minuten
und Folien (`docs/tutorials/games/`, Folien unter `/docs/presentations/<game>.html`). Pong führt
in die Spielschleife und Kollisionen ein; Breakout in Listen; Space Invaders in Bilder und
Objekt-Pools; Asteroids in Festkomma-Physik; Snake in Kacheln und Ringpuffer. Jede Präsentation
endet mit Übungen und einer Verständnisfrage.
