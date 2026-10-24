# Lektion 1: das erste Blöcke-Projekt

Ziel: ein kleines PRG32-Spiel erstellen, das ein Quadrat für die Spielfigur zeichnet.

## 1. Erstelle das Projekt

1. Öffne die Startseite.
2. Klicke auf **Neues Projekt**.
3. Lass **Blöcke** ausgewählt. (Das Fenster bietet auch **C**, **Assembly (RISC-V)** und
   **Python (PRG32 Python)** an: Sie beginnen mit einem kleinen, schon funktionierenden Spiel,
   als Code geschrieben und Zeile für Zeile erklärt.)
4. Nenne es `First Square`.
5. Klicke auf **Erstellen**.

## 2. Lege den Startzustand fest

Im Blöcke-Bereich:

1. Ziehe `wenn das Spiel startet` hinein.
2. Füge `setze player_x auf 150` hinzu.
3. Füge `setze player_y auf 180` hinzu.

## 3. Zeichne das Quadrat

1. Ziehe `in jedem Frame zeichnen` hinein.
2. Füge `leere den Bildschirm schwarz` hinzu.
3. Füge `zeichne Rechteck x player_x y player_y b 16 h 16 Farbe gelb` hinzu.

## 4. Führe es aus

Klicke auf **Ausführen** (Shift+F10). Das Kit baut dein Spiel und startet es im Simulator
rechts: Du solltest ein gelbes Quadrat auf dem PRG32-Bildschirm sehen.

## 5. Speichern und exportieren

1. Klicke auf **Speichern** (Ctrl+S).
2. Öffne das Menü **Projekt** und wähle **Als JSON exportieren**.

Die heruntergeladene Datei ist ein PRG32-Blöckespiel, als JSON gespeichert.

## 6. Hol dir eine Cartridge für deine PRG32

Klicke auf **Kompilieren** (dafür brauchst du ein Konto) und dann im Tab **Build** auf den Link
**esp32c6-.prg32 herunterladen**. Das Kit kompiliert deine Blöcke, und dein Browser speichert
eine Datei wie `first-square-esp32c6.prg32`. Diese Datei ist deine PRG32-Cartridge: Kopiere sie
in einen Cartridge-Platz der Platine. Der Link **qemu-.prg32 herunterladen** daneben ist
dasselbe Spiel für den QEMU-Emulator.
