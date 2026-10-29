# Lektion 4: ein Cartridge-Paket vorbereiten und veröffentlichen

Ziel: aus einem Blöcke-Projekt ein Paket für den Cartridge Store machen.

## 1. Erzeugen

Öffne ein Projekt und klicke auf **Erzeugen**. Prüfe, ob das erzeugte C sinnvoll aussieht.

## 2. Cartridge vorbereiten

Klicke auf **Kompilieren**.

Ist die PRG32-Build-Toolchain installiert, entsteht ein veröffentlichbares Paket mit `.prg32`-Dateien. Sonst erstellt das Kit ein Lehrpaket nur mit dem Quelltext; das Docker-Image enthält die Toolchain schon (siehe `../install_cartridge_build.md`).

Um eine einzelne Cartridge vor dem Veröffentlichen zu testen, drücke **Ausführen** (der Simulator rechts) oder lade eine aus dem Tab **Build** herunter.
Veröffentliche das Paket aus **Kompilieren**, damit der Store jede Architektur bekommt.

## 3. Ein Store-Profil einrichten

1. Öffne **Veröffentlichen**.
2. Füge ein Profil mit der Adresse des Cartridge Store hinzu.
3. Füge ein Bearer-Token hinzu, wenn dein Store eines verlangt.

## 4. Veröffentlichen

1. Finde das Paket in der Liste.
2. Klicke auf **Prüfen**: Die Seite zeigt genau, was gesendet wird (Store, Cartridge,
   Versionen, Fingerabdrücke der Dateien).
3. Setze das Häkchen, klicke auf **Bestätigen** und lies das Antwortfeld.

Zum Veröffentlichen brauchst du die Rolle publisher; ohne sie bitte deine Lehrkraft, für dich zu veröffentlichen.

Ein echter Cartridge Store kann mit einer wartenden Einreichung antworten, die eine Redaktion prüfen muss.
