# Lezione 10: la tua grafica in Blocchi, Python, C e assembly

Tempo: circa 40 minuti. Ti basta il kit (va bene anche come ospite). Le regole sono in
[La grafica del progetto nel tuo gioco](../project_art.md).

## 1. Aggiungi Star Catcher

1. In **Progetti**, trova **Star Catcher (Blocks)** tra gli esempi (etichetta *sprite e suoni*) e
   premi **Aggiungi**.
2. Aprilo e premi **Esegui** (Shift+F10). Muovi il razzo con le frecce e prendi la stella che
   cade.
3. Nei file del progetto apri **Sprite → rocket**. Sprite Lab si apre in una scheda.

## 2. Cambia la grafica, non il codice

1. In Sprite Lab colora la punta del razzo con un altro colore e premi **Salva**.
2. Premi di nuovo **Esegui**: il gioco disegna il nuovo razzo. Non hai cambiato nessun blocco.
3. Guarda sotto **Usalo nel tuo gioco** in Sprite Lab. Scegli **Blocchi**, poi **PRG32 Python**,
   **C** e **Assembly**: lo stesso sprite, usato in quattro linguaggi.

## 3. Leggi i blocchi

La categoria **Sprite e tile** ha tre blocchi per la tua grafica:

```text
quando il gioco inizia:     carica sfondo sky
a ogni fotogramma disegna:  disegna sfondo sky
                            disegna sprite rocket x rocket_x y 160
                            disegna sprite star x star_x y star_y
```

Carica uno sfondo una volta sola, disegnalo per primo a ogni fotogramma, poi disegna gli sprite
sopra. Premi **Genera** e apri `game.c`: la parte 3 contiene `rocket_draw`, `star_draw`,
`sky_load` e `sky_draw`, fatti dalla grafica.

## 4. Lo stesso gioco in PRG32 Python

Aggiungi **Star Catcher (Python)** e apri `game.py`. La grafica è nominata tra virgolette:

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

Cambia `"star"` in `"stars"` e salva. Il pannello Problemi dice, su quella riga, che il progetto
non ha uno sprite con quel nome. Rimetti com'era.

## 5. Lo stesso gioco in C

Aggiungi **Star Catcher (C)**. In cima a `game.c` c'è una riga per tutta la grafica:

```c
#include "prg32_assets.h"
```

Apri **Grafica e suoni del progetto → prg32_assets.h** nei file del progetto: è di sola lettura e
mostra il codice che il kit scrive al posto di quella riga quando il gioco viene compilato. Trova
`rocket_draw`, `ROCKET_WIDTH`, `sky_load`, `sfx_coin` e `TRACK_THEME`, poi trova dove `game.c` li
usa.

## 6. Lo stesso gioco in assembly

Aggiungi **Star Catcher (Assembly)**. La sua riga è `#include "prg32_assets.S"`, e la sua grafica
si chiama come una funzione del firmware:

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

Esegui tutti e quattro i giochi: disegnano esattamente la stessa immagine.

## 7. Prova da solo

- Disegna in Sprite Lab un nuovo sprite chiamato `comet` e salvalo. Disegnalo in ogni gioco: un
  blocco, una riga `prg32.sprite("comet", ...)`, `comet_draw(x, y);` in C, `call comet_draw` in
  assembly.
- In **Sfondi** aggiungi a `sky` un secondo strato con delle nuvole. `disegna sfondo sky` lo
  disegna davanti, con la tile 0 trasparente.
- In AudioStudio cambia il suono **Coin**. Ogni gioco suona il nuovo suono.
