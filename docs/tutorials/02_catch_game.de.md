# Lektion 2: ein Fangspiel

Ziel: die Spielfigur nach links und rechts bewegen und auf dem Bildschirm halten.

## 1. Beginne mit Lektion 1

Öffne dein Projekt oder erstelle ein neues.

## 2. Füge Bewegung hinzu

Füge in `in jedem Frame aktualisieren` hinzu:

```text
wenn Taste links gehalten wird
  ändere player_x um -3

wenn Taste rechts gehalten wird
  ändere player_x um 3

halte player_x zwischen 0 und 304
```

## 3. Teste die Bewegung

1. Klicke auf **Ausführen** (Shift+F10) und dann auf den Spielbildschirm.
2. Benutze die Pfeiltasten links und rechts.
3. Prüfe, dass das Quadrat den Bildschirm nicht verlassen kann.

## 4. Sieh dir das C an

Klicke auf **Erzeugen** und finde:

```c
uint32_t input = prg32_input_read();
if (input & PRG32_BTN_LEFT) {
    player_x += -3;
}
```

Besprecht, warum der Block von Tasten spricht, das C aber eine Bitmaske benutzt.
