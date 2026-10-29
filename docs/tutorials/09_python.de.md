# Lektion 9: dein erstes Spiel in PRG32 Python

Zeit: etwa 40 Minuten. Du brauchst nur das Kit (auch als Gast). Die Sprache ist in
[PRG32 Python](../python_language.md) beschrieben.

## 1. Erstelle ein Python-Projekt

1. Drücke auf **Projekte** auf **Neues Projekt**.
2. Wähle **Python (PRG32 Python)**, nenne es `Catcher` und drücke **Erstellen**.
3. Die IDE öffnet `game.py`: ein kleines Spiel, das schon funktioniert. Drücke **Ausführen**
   (Shift+F10). Klicke auf den Bildschirm und bewege das gelbe Quadrat mit den Pfeiltasten.

## 2. Lies die drei Funktionen

- `init()` läuft einmal, wenn das Spiel startet.
- `update()` läuft in jedem Frame: Es liest die Tasten und bewegt Dinge.
- `draw()` läuft in jedem Frame nach `update()`: Es malt den Bildschirm.

Fahre mit der Maus über `prg32.rect`, um zu lesen, was es tut. Tippe `prg32.` in eine neue Zeile
und drücke **Ctrl+Space**, um alles zu sehen, was die PRG32 bietet.

## 3. Füge einen fallenden Stern hinzu

Füge oben unter `score` zwei Variablen hinzu:

```python
star_x: int = 100
star_y: int = 0
```

In `update()` nennt die Zeile `global` jede äußere Variable, die `update()` ändert. Lass sie auch
den Stern nennen und lass den Stern dann nach unten fallen:

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

Zeichne ihn in `draw()`: `prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`. Drücke **Ausführen**.

## 4. Fang ihn

Immer noch in `update()`:

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

Zeige in `draw()` den Punktestand: `prg32.number(score, 8, 24, prg32.YELLOW)`.

## 5. Mach absichtlich einen Fehler

Schreibe `star_y = star_y / 2` und warte kurz: Der Editor unterstreicht `/` und sagt, dass
PRG32-Zahlen ganze Zahlen sind. Ändere es zu `//`. Schreibe jetzt `while True:` in eine neue
Zeile: Der Editor erklärt, warum Schleifen `for i in range(...)` benutzen müssen. Lösche es
wieder.

## 6. Sieh dir das C und den Assembler an

Drücke **Erzeugen** (Ctrl+Shift+G). Öffne unter **Erzeugt (nur lesen)** `game.c` und `game.S`.
Finde dein `star_y += 2`: Der Kommentar darüber sagt `Step "change star_y by 2"`, und die C-Zeile
ist `star_y += 2;`. Im Assembler ist derselbe Schritt ein Laden, ein `addi` und ein Speichern,
jeweils erklärt.

## 7. Debugge eine Zeile

Öffne den Tab **Debuggen** und drücke **Ausführen**. Drücke in **game.py** die Zeilennummer von
`score += 1`. Fang einen Stern: Das Spiel hält auf dieser Zeile an. Sieh dir die **Variablen** an
und drücke dann **Nächste Python-Zeile**. Drücke **Weiter**, um weiterzuspielen.

## Für Lehrkräfte

- Das Kit führt das Python der Schülerinnen und Schüler nie aus: Es wird gelesen, nach den Regeln
  von PRG32 Python geprüft und in dieselbe IR wie die Blöcke übersetzt, dann in C und Assembler
  mit Erklärungen.
- Dasselbe game.py ergibt immer byte-gleiches C, Assembler und Cartridge, in jeder Sprache der
  Oberfläche.
- Ein Python-Projekt bleibt ein Python-Projekt: Ein Speichern kann es nicht in Blöcke, C oder
  Assembler verwandeln. Um Sprachen zu vergleichen, mach ein C-Projekt aus derselben Idee oder
  öffne das erzeugte C.
