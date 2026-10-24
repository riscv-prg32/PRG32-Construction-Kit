# Lezione 9: il tuo primo gioco in PRG32 Python

Tempo: circa 40 minuti. Ti basta il kit (va bene anche come ospite). Il linguaggio è descritto in
[PRG32 Python](../python_language.md).

## 1. Crea un progetto Python

1. In **Progetti**, premi **Nuovo progetto**.
2. Scegli **Python (PRG32 Python)**, chiamalo `Catcher` e premi **Crea**.
3. L'IDE apre `game.py`: un piccolo gioco che funziona già. Premi **Esegui** (Shift+F10). Fai clic
   sullo schermo e muovi il quadrato giallo con le frecce.

## 2. Leggi le tre funzioni

- `init()` viene eseguita una volta, quando il gioco inizia.
- `update()` viene eseguita a ogni fotogramma: legge i pulsanti e muove le cose.
- `draw()` viene eseguita a ogni fotogramma dopo `update()`: dipinge lo schermo.

Passa il mouse su `prg32.rect` per leggere che cosa fa. Scrivi `prg32.` su una riga nuova e premi
**Ctrl+Space** per vedere tutto quello che la PRG32 offre.

## 3. Aggiungi una stella che cade

Aggiungi due variabili in alto, sotto `score`:

```python
star_x: int = 100
star_y: int = 0
```

In `update()`, la riga `global` nomina ogni variabile esterna che `update()` cambia. Falle
nominare anche la stella, poi fai scendere la stella:

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

In `draw()`, disegnala: `prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`. Premi **Esegui**.

## 4. Prendila

Sempre in `update()`:

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

In `draw()`, mostra il punteggio: `prg32.number(score, 8, 24, prg32.YELLOW)`.

## 5. Sbaglia apposta

Scrivi `star_y = star_y / 2` e aspetta un attimo: l'editor sottolinea `/` e dice che i numeri
PRG32 sono interi. Cambialo in `//`. Ora scrivi `while True:` su una riga nuova: l'editor spiega
perché i cicli devono usare `for i in range(...)`. Cancellalo di nuovo.

## 6. Guarda il C e l'assembly

Premi **Genera** (Ctrl+Shift+G). In **Generati (sola lettura)**, apri `game.c` e `game.S`.
Trova il tuo `star_y += 2`: il commento sopra dice `Step "change star_y by 2"`, e la riga C è
`star_y += 2;`. Nell'assembly, lo stesso passo è un caricamento, un `addi` e un salvataggio,
ciascuno spiegato.

## 7. Fai il debug di una riga

Apri la scheda **Debug** e premi **Esegui**. In **game.py**, premi il numero di riga di
`score += 1`. Prendi una stella: il gioco si ferma su quella riga. Guarda le **Variabili**, poi
premi **Riga Python successiva**. Premi **Continua** per giocare ancora.

## Per gli insegnanti

- Il kit non esegue mai il Python dello studente: viene letto, controllato con le regole di
  PRG32 Python e tradotto nella stessa IR dei blocchi, poi in C e assembly con le spiegazioni.
- Lo stesso game.py dà sempre C, assembly e cartuccia identici byte per byte, in ogni lingua
  dell'interfaccia.
- Un progetto Python resta un progetto Python: un salvataggio non può trasformarlo in blocchi, C o
  assembly. Per confrontare i linguaggi, crea un progetto C dalla stessa idea, oppure apri il C
  generato.
