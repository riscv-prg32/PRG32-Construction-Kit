# Lektion 10: deine Grafik in Blöcken, Python, C und Assembler

Zeit: etwa 40 Minuten. Du brauchst nur das Kit (auch als Gast). Die Regeln stehen in
[Grafik und Sound des Projekts im Spiel](../project_art.md).

## 1. Star Catcher hinzufügen

1. Suche unter **Projekte** bei den Beispielen **Star Catcher (Blocks)** (Abzeichen *Sprites und
   Sound*) und drücke **Hinzufügen**.
2. Öffne es und drücke **Ausführen** (Shift+F10). Bewege die Rakete mit den Pfeiltasten und fange
   den fallenden Stern.
3. Öffne in den Projektdateien **Sprites → rocket**. Sprite Lab öffnet sich als Tab.

## 2. Die Grafik ändern, nicht den Code

1. Male in Sprite Lab die Spitze der Rakete in einer anderen Farbe an und drücke **Speichern**.
2. Drücke wieder **Ausführen**: Das Spiel zeichnet die neue Rakete. Du hast keinen Block
   geändert.
3. Schau in Sprite Lab unter **In deinem Spiel benutzen**. Wähle **Blöcke**, dann **PRG32
   Python**, **C** und **Assembler**: dasselbe Sprite, in vier Sprachen benutzt.

## 3. Die Blöcke lesen

Die Kategorie **Sprites und Kacheln** hat drei Blöcke für deine Grafik:

```text
wenn das Spiel startet:   lade Hintergrund sky
in jedem Frame zeichnen:  zeichne Hintergrund sky
                          zeichne Sprite rocket x rocket_x y 160
                          zeichne Sprite star x star_x y star_y
```

Lade einen Hintergrund nur einmal, zeichne ihn in jedem Frame zuerst und zeichne dann die Sprites
darüber. Drücke **Erzeugen** und öffne `game.c`: Teil 3 enthält `rocket_draw`, `star_draw`,
`sky_load` und `sky_draw`, aus der Grafik gemacht.

## 4. Dasselbe Spiel in PRG32 Python

Füge **Star Catcher (Python)** hinzu und öffne `game.py`. Die Grafik wird in Anführungszeichen
genannt:

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

Ändere `"star"` in `"stars"` und speichere. Das Feld Probleme sagt in dieser Zeile, dass das
Projekt kein Sprite mit diesem Namen hat. Mach es wieder rückgängig.

## 5. Dasselbe Spiel in C

Füge **Star Catcher (C)** hinzu. Oben in `game.c` steht eine Zeile für die ganze Grafik:

```c
#include "prg32_assets.h"
```

Öffne in den Projektdateien **Grafik und Sound des Projekts → prg32_assets.h**: Die Datei ist nur
zum Lesen und zeigt den Code, den das Kit beim Übersetzen an die Stelle dieser Zeile schreibt.
Finde `rocket_draw`, `ROCKET_WIDTH`, `sky_load`, `sfx_coin` und `TRACK_THEME`, dann die Stellen,
an denen `game.c` sie benutzt.

## 6. Dasselbe Spiel in Assembler

Füge **Star Catcher (Assembly)** hinzu. Seine Zeile ist `#include "prg32_assets.S"`, und seine
Grafik wird wie eine Firmware-Funktion aufgerufen:

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

Führe alle vier Spiele aus: Sie zeichnen genau dasselbe Bild.

## 7. Probier es selbst

- Zeichne in Sprite Lab ein neues Sprite namens `comet` und speichere es. Zeichne es in jedem
  Spiel: ein Block, eine Zeile `prg32.sprite("comet", ...)`, `comet_draw(x, y);` in C,
  `call comet_draw` in Assembler.
- Füge in **Hintergründe** zu `sky` eine zweite Ebene mit Wolken hinzu. `zeichne Hintergrund sky`
  zeichnet sie davor, mit Kachel 0 durchsichtig.
- Ändere in AudioStudio den Klang **Coin**. Jedes Spiel spielt den neuen Klang.
