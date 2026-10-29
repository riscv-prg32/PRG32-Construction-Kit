# Lektion 7: mit dem Debugger in den Prozessor schauen

Dein Spiel ist eine Liste von RISC-V-Anweisungen. Der Prozessor führt sie eine nach der anderen
aus, sehr schnell: zehntausende in jedem Frame. Mit dem **Debugger** kannst du ihn anhalten und
eine Anweisung nach der anderen ausführen, um zu sehen, was wirklich passiert.

Du brauchst eine Cartridge, die das Kit gebaut hat: Drücke in der IDE auf **Ausführen** und
öffne den Tab **Debuggen** unter dem Editor, oder drücke **Kompilieren** und dann **Debuggen**
im Menü oben (der Player mit seinem Debugger unter dem Bildschirm). Auf dieser Seite kannst du
auch jede `.prg32`-Datei öffnen.

## Für Schülerinnen und Schüler

1. Schalte den **Debug-Modus** ein. Jetzt prüft der Prozessor vor jeder Anweisung, ob du ihn
   gebeten hast, dort anzuhalten.
2. Drücke **Schritt**. Die blaue Zeile ist die nächste Anweisung; nach jedem Schritt rückt sie
   nach unten. Sieh dir die **Register** an: das, das sich gerade geändert hat, wird gelb.
3. Klicke in die graue Fläche links neben einer Adresse. Ein roter **●** erscheint: das ist ein
   **Haltepunkt**. Drücke **Weiter**: Das Spiel läuft und hält genau vor dieser Anweisung an.
   Drücke noch einmal **Weiter**: Es läuft einen Frame weiter und hält wieder dort an.
4. **Frame-Schritt** läuft bis zum Ende des Frames (update + draw) und hält an, außer es kommt
   vorher ein Haltepunkt.
5. Stelle die Geschwindigkeit auf **0.01×** und drücke **Weiter**: Du siehst die blaue Zeile
   durch den Code wandern.

Worauf du achten kannst:

- Die Knöpfe **Update** und **Draw** zeigen, wo deine Funktionen `update` und `draw` anfangen.
  In jedem Frame führt der Prozessor update aus, dann draw.
- `a0` enthält die erste Zahl, die eine Funktion bekommt, und die Zahl, die sie zurückgibt. Setze
  einen Haltepunkt hinter ein `jalr` (einen Funktionsaufruf) und sieh dir `a0` an.
- `sp` (der Stack-Pointer) geht *nach unten*, wenn eine Funktion beginnt (`addi sp, sp, -16`),
  und wieder *nach oben*, wenn sie endet.
- Die **Spielzeit** ist die Zeit, die nach Meinung des Spiels vergangen ist (33 ms pro Frame).
  Die **Echtzeit** ist deine Uhr. Bei 0.01× sind sie sehr verschieden, aber das Spiel verhält
  sich gleich.

## Debugge deine Blöcke, dein C oder deinen Assembler

Wenn das Kit die Cartridge gebaut hat (**Ausführen** in der IDE, oder **Kompilieren** und dann
**Debuggen** im Menü oben), kennt der Debugger auch dein Programm, nicht nur seine Anweisungen.
Unter dem Maschinencode siehst du:

- **Blöcke** (Blöcke-Projekte): deine Blöcke. Während das Spiel angehalten ist, hat der laufende
  Block einen blauen Rand. Klicke auf einen Block (oder wähle ihn in der Liste) und drücke
  **● Haltepunkt am Block**: Das Spiel hält jedes Mal an, wenn dieser Block beginnt.
- **game.c** oder **game.S**: dein Quelltext. Die laufende Zeile ist blau. Drücke eine
  Zeilennummer, um auf dieser Zeile einen Haltepunkt **●** zu setzen. Hat eine Zeile keinen
  eigenen Code (der Compiler hat ihre Arbeit verschoben), kommt der Haltepunkt auf die nächste
  Zeile mit Code, und der Player sagt es dir.
- **Nächster Block** / **Nächste Zeile**: läuft bis zum nächsten Block (oder zur nächsten Zeile)
  deines Programms. Funktionsaufrufe laufen ganz durch.
- **Variablen**: die Variablen deiner Blöcke (`score`, `ball_x`, ...) mit ihren Werten. In der
  Ansicht Fortgeschritten auch die Variablen der laufenden Funktion.
- **Beobachtungen**: Tippe einen Namen ein und drücke **Beobachten**: `score`, `player.x`,
  `heights[2]` oder ein Register wie `a0`.
- **Aufrufstapel**: welche Funktion welche aufgerufen hat. Drücke eine, um ihre Variablen zu
  sehen.
- **Nur anhalten, wenn...**: Gib einem Haltepunkt eine Bedingung wie `score > 10`, und das Spiel
  hält dort nur an, wenn sie wahr ist.

Probier es aus: Setze einen Haltepunkt auf den Block, der den Ball bewegt, beobachte `ball_x` und
drücke ein paarmal **Weiter**. Gib dem Haltepunkt die Bedingung `ball_x < 50`: Jetzt hält er nur
an, wenn der Ball nahe an der linken Wand ist.

Manchmal steht bei einer Variablen *wegoptimiert*: Der Compiler hat dein Programm schneller
gemacht und diesen Wert an dieser Stelle nicht behalten. Der Debugger sagt das, statt zu raten.

Manchmal zeigt der Aufrufstapel eine Funktion, die als **eingefügt in** eine andere markiert ist:
Der Compiler hat diese kleine Funktion in die aufrufende kopiert, darum hat sie keinen eigenen
Rahmen. Der Debugger zeigt trotzdem, wo du in ihr bist und von welcher Zeile sie aufgerufen
wurde; ihre Variablen werden nicht gezeigt (drücke die Funktion, in die sie eingefügt wurde, um
deren Variablen zu sehen).

**Deine Haltepunkte bleiben**, wenn du das Spiel änderst und neu kompilierst. Jeder merkt sich
den Code seiner Zeile: Ist dieser Code verschoben, wandert der Haltepunkt mit; ist der Code weg,
wird der Haltepunkt als *der Code hat sich geändert* aufgelistet und nirgendwo anders gesetzt.
Das Kästchen vor einem Haltepunkt schaltet ihn aus, ohne ihn zu verlieren (sein Punkt im
Quelltext wird zu ○).

## Ansicht Fortgeschritten

**Fortgeschritten** zeigt alle 32 Register hexadezimal, die Maschinenwörter jeder Anweisung,
einen Speicherbetrachter und zwei weitere Knöpfe:

- **Überspringen**: Bei einem Aufruf (`jal`, `jalr`) läuft die ganze aufgerufene Funktion, und
  der Debugger hält auf der nächsten Zeile an.
- **Herausspringen**: läuft, bis die aktuelle Funktion zu ihrem Aufrufer zurückkehrt.

Der Speicherbetrachter nimmt eine Adresse dezimal (`1082130432`) oder hexadezimal
(`0x40800000`) und zeigt bis zu 1024 Bytes hexadezimal und als Text. Mit einer Cartridge des Kits
zeigt Fortgeschritten auch die **Zähler-CSRs** (`cycle`, `time`, `instret`: was `csrr` lesen
würde) und den **Stack**: die Wörter um `sp` herum.

Einsteiger und Fortgeschritten sind zwei Arten, dasselbe anzusehen: Ein Wechsel ändert das Spiel
nicht, und die Haltepunkte bleiben.

## Für Lehrkräfte

- Es ist derselbe Debugger wie der von PRG32-QT (dieselben Anweisungen, dieselben Regeln:
  Haltepunkte werden geprüft, bevor eine Anweisung läuft; **Weiter** verlässt den aktuellen
  Haltepunkt einmal). Überspringen, Herausspringen, Frame-Schritt und die Ansicht Einsteiger
  sind Ergänzungen; siehe `../compatibility.md`.
- Haltepunkte werden im Browser für genau diese Cartridge gespeichert. Eine neu kompilierte
  Cartridge ist eine andere und beginnt ohne.
- Alles läuft im Browser der Schülerin oder des Schülers; nichts wird an den Server geschickt.
- Gute erste Übungen: zählen, wie viele Anweisungen ein Frame braucht (beobachte den
  Anweisungszähler zwischen zwei Halten am selben Haltepunkt); die Anweisung finden, die die
  x-Position eines Sprites ändert; ein Blöcke-Spiel mit seinem erzeugten Assembler vergleichen
  (**Erzeugen** im Editor).
- Das Debuggen von Quelltext und Blöcken braucht eine Cartridge, die das Kit kompiliert hat: Das
  Kit kompiliert mit Debug-Informationen nebenher (die Cartridge selbst ist genau dieselbe,
  `../adr/0015-source-and-block-debugger.md`). Eine aus einer Datei geöffnete `.prg32` hat nur den
  Maschinencode-Debugger.
- Eine gute Übung mit Blöcken: herausfinden, welcher Block `score` ändert, mit einem Haltepunkt
  mit der Bedingung `score > 0`.
