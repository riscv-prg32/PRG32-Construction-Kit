# Lezione 2: un gioco di presa

Obiettivo: muovere il giocatore a sinistra e a destra e tenerlo dentro lo schermo.

## 1. Parti dalla lezione 1

Apri il tuo progetto o creane uno nuovo.

## 2. Aggiungi il movimento

In `a ogni fotogramma aggiorna`, aggiungi:

```text
se il pulsante sinistra è premuto
  cambia player_x di -3

se il pulsante destra è premuto
  cambia player_x di 3

tieni player_x tra 0 e 304
```

## 3. Prova il movimento

1. Fai clic su **Esegui** (Shift+F10), poi sullo schermo del gioco.
2. Usa le frecce sinistra e destra.
3. Controlla che il quadrato non possa uscire dallo schermo.

## 4. Guarda il C

Fai clic su **Genera** e trova:

```c
uint32_t input = prg32_input_read();
if (input & PRG32_BTN_LEFT) {
    player_x += -3;
}
```

Discutete perché il blocco parla di pulsanti, mentre il C usa una maschera di bit.
