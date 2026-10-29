# Lezione 5: una lezione di laboratorio per l'insegnante

Obiettivo: condurre un'attività in classe di 45 minuti.

## Preparazione

1. Avvia PRG32-Construction-Kit. Con Docker (`docker compose up -d --build`)
   la compilazione delle cartucce funziona subito. Controllala prima della lezione con
   `docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2`
   (vedi `../install_cartridge_build.md`).
2. Facoltativo: avvia il Cartridge Store.
3. Facoltativo: collega un dispositivo PRG32 o prepara QEMU.
4. Controlla che gli studenti riescano ad aprire l'applicazione web.

## 0-5 minuti: dimostrazione

Mostra il progetto di partenza. Muovi il quadrato del giocatore nel simulatore.

## 5-20 minuti: gli studenti costruiscono

Gli studenti cambiano:

- il colore del giocatore;
- la velocità del giocatore;
- la posizione iniziale;
- il testo del titolo.

## 20-30 minuti: discussione sul C generato

Gli studenti fanno clic su **Genera** e aprono `game.c` in **Generati (sola lettura)** per
trovare l'istruzione C prodotta da un blocco. Gli studenti più grandi aprono `game.S` accanto e
trovano lo stesso blocco nell'assembly: il suo commento mostra la riga C e ogni istruzione dice
cosa fa (vedi `../generated_code.md`). `game.py` mostra gli stessi blocchi in PRG32 Python.

## 30-40 minuti: sprite e artefatti

Gli studenti disegnano uno sprite, lo convertono in C e scaricano l'artefatto.
Se c'è una scheda PRG32 o QEMU, gli studenti fanno clic su **Compila**, scaricano dalla scheda
**Compilazione** e caricano la loro cartuccia PRG32.

## 40-45 minuti: riflessione

Chiedi:

- Quale blocco ha cambiato una variabile?
- In quale istruzione C è diventato?
- Quali istruzioni RISC-V fanno lo stesso lavoro?
- Perché il simulatore aiuta prima di passare all'hardware?
- Che cosa c'è dentro una cartuccia `.prg32` rispetto al C generato?

## Poi: un'unità sui giochi classici

I cinque giochi completi in `examples/games/` hanno ciascuno una lezione di 90-120 minuti e
delle slide (`docs/tutorials/games/`, slide in `/docs/presentations/<game>.html`). Pong
introduce il ciclo di gioco e le collisioni; Breakout le liste; Space Invaders le immagini e i
gruppi di oggetti; Asteroids la fisica a virgola fissa; Snake le tile e i buffer circolari. Ogni
presentazione finisce con esercizi e una domanda di verifica.
