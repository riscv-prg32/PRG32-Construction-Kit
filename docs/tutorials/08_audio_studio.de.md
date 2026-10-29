# Lektion 8: Soundeffekte und Musik mit AudioStudio

Zeit: etwa 30 Minuten. Du brauchst ein Blöcke-Projekt (das Fangspiel aus Lektion 2 passt
perfekt).

## 1. Öffne AudioStudio

Öffne dein Projekt und drücke **AudioStudio**. Der Tab **Stimmen** zeigt die 8 Stimmen der
PRG32-Konsole. Drücke **Ausprobieren**: Du hörst Stimme 0. Schiebe den Regler für den
**Anschlag** (Attack) nach rechts und probiere es noch einmal: Jetzt blendet sich die Note ein.
Sieh zu, wie sich das Bild der Hüllkurve ändert.

## 2. Mach einen Soundeffekt

1. Öffne **Soundeffekte** und drücke **Neu**.
2. Nenne ihn `Catch`.
3. Setze **Note** auf 76 und **Länge** auf 120 ms. Wähle den Klang **pulse**.
4. Setze **Halten** (Sustain) auf 0 und **Abfall** (Decay) auf 60: ein kurzes „Blip“. Drücke
   **Ausprobieren**.

## 3. Schreib eine kleine Melodie

1. Öffne **Soundtracks** und drücke **Neu**. Nenne ihn `Theme`.
2. Klicke auf den ersten Schritt von Stimme 0 und tippe `C4`. Drücke die Pfeiltaste nach rechts
   und tippe `E4`, dann `G4`, dann `C5`.
3. Setze `off` hinter die letzte Note, damit sie aufhört.
4. Hake **Schleife** an und drücke **Abspielen**. Drücke **Esc**, um anzuhalten.
5. Füge auf Stimme 1 eine Basslinie hinzu (`C3` auf Schritt 1, `G2` auf Schritt 5). Benutze
   **Stumm** auf Stimme 0, um nur den Bass zu hören.

AudioStudio speichert von selbst. Die Karte **Was der Code sagt** zeigt die C-Zeilen, zu denen
deine Blöcke werden.

## 4. Benutze sie im Spiel

Geh zurück in den Blöcke-Editor und öffne die Kategorie **Klang**:

- setze **spiele Soundtrack Theme** in *wenn das Spiel startet*;
- setze **spiele Soundeffekt Catch** dorthin, wo die Spielfigur etwas fängt.

Drücke **Ausführen** (Shift+F10): Du hörst dieselben Klänge wie in AudioStudio. Sieh dir das
erzeugte C an: `prg32_audio_play_track(0);` und `prg32_audio_note(7, 8, 76, 255, 120);`. Kannst
du sagen, was jede Zahl bedeutet? (Tipp: Stimme, Instrument, Note, Lautstärke, Millisekunden.)

## 5. Fragen für die Klasse

- Warum hat ein Soundeffekt seine eigene Stimme? Was passiert, wenn die Musik diese Stimme auch
  benutzt?
- Ändere das Tempo des Soundtracks von 120 auf 180. Was ändert sich im erzeugten C, und was
  nicht?
- Benenne den Soundeffekt um. Was sagt der Codegenerator, und warum rät er nicht?
