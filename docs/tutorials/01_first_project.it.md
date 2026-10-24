# Lezione 1: il primo progetto a blocchi

Obiettivo: creare un piccolo gioco PRG32 che disegna un quadrato per il giocatore.

## 1. Crea il progetto

1. Apri la pagina iniziale.
2. Fai clic su **Nuovo progetto**.
3. Lascia selezionato **Blocchi**. (La finestra offre anche **C**, **Assembly (RISC-V)** e
   **Python (PRG32 Python)**: partono da un piccolo gioco che funziona già, scritto come codice e
   spiegato riga per riga.)
4. Chiamalo `First Square`.
5. Fai clic su **Crea**.

## 2. Prepara lo stato iniziale

Nell'area dei blocchi:

1. Trascina `quando il gioco inizia`.
2. Aggiungi `imposta player_x a 150`.
3. Aggiungi `imposta player_y a 180`.

## 3. Disegna il quadrato

1. Trascina `a ogni fotogramma disegna`.
2. Aggiungi `pulisci lo schermo nero`.
3. Aggiungi `disegna rettangolo x player_x y player_y l 16 a 16 colore giallo`.

## 4. Eseguilo

Fai clic su **Esegui** (Shift+F10). Il kit costruisce il gioco e lo avvia nel simulatore a
destra: dovresti vedere un quadrato giallo sullo schermo della PRG32.

## 5. Salva ed esporta

1. Fai clic su **Salva** (Ctrl+S).
2. Apri il menu **Progetto** e scegli **Esporta come JSON**.

Il file scaricato è un gioco PRG32 a blocchi salvato come JSON.

## 6. Prendi una cartuccia per la tua PRG32

Fai clic su **Compila** (serve un account), poi sul link **Scarica .prg32 per esp32c6** nella
scheda **Compilazione**. Il kit compila i tuoi blocchi e il browser salva un file come
`first-square-esp32c6.prg32`. Quel file è la tua cartuccia PRG32: copialo in uno slot per
cartucce della scheda. Il link **Scarica .prg32 per qemu** accanto è lo stesso gioco per
l'emulatore QEMU.
