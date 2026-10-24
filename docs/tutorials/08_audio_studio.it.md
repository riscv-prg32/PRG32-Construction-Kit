# Lezione 8: effetti sonori e musica con AudioStudio

Tempo: circa 30 minuti. Ti serve un progetto a blocchi (il gioco di presa della lezione 2 va
benissimo).

## 1. Apri AudioStudio

Apri il tuo progetto e premi **AudioStudio**. La scheda **Voci** mostra le 8 voci della console
PRG32. Premi **Provalo**: senti la voce 0. Sposta il cursore dell'**attacco** (Attack) verso
destra e riprova: ora la nota entra piano. Guarda cambiare il disegno dell'inviluppo.

## 2. Crea un effetto sonoro

1. Apri **Effetti sonori** e premi **Nuovo**.
2. Chiamalo `Catch`.
3. Metti **Nota** a 76 e **Durata** a 120 ms. Scegli il suono **pulse**.
4. Metti il **sostegno** (Sustain) a 0 e il **decadimento** (Decay) a 60: un breve "blip". Premi
   **Provalo**.

## 3. Scrivi una piccola melodia

1. Apri **Colonne sonore** e premi **Nuovo**. Chiamala `Theme`.
2. Fai clic sul primo passo della voce 0 e scrivi `C4`. Premi la freccia a destra e scrivi `E4`,
   poi `G4`, poi `C5`.
3. Metti `off` dopo l'ultima nota, così si ferma.
4. Spunta **Ripeti** e premi **Suona**. Premi **Esc** per fermarla.
5. Aggiungi un basso sulla voce 1 (`C3` al passo 1, `G2` al passo 5). Usa **Muto** sulla voce 0
   per sentire solo il basso.

AudioStudio salva da solo. La scheda **Che cosa dice il codice** mostra le righe C in cui
diventeranno i tuoi blocchi.

## 4. Usali nel gioco

Torna nell'editor a blocchi e apri la categoria **Suono**:

- metti **suona colonna sonora Theme** in *quando il gioco inizia*;
- metti **suona effetto sonoro Catch** dove il giocatore prende qualcosa.

Premi **Esegui** (Shift+F10): senti gli stessi suoni di AudioStudio. Guarda il C generato:
`prg32_audio_play_track(0);` e `prg32_audio_note(7, 8, 76, 255, 120);`. Sai dire che cosa
significa ogni numero? (Aiuto: voce, strumento, nota, volume, millisecondi.)

## 5. Domande per la classe

- Perché un effetto sonoro ha la sua voce? Che cosa succede se anche la musica usa quella voce?
- Cambia il tempo della colonna sonora da 120 a 180. Che cosa cambia nel C generato, e che cosa
  no?
- Rinomina l'effetto sonoro. Che cosa dice il generatore di codice, e perché non tira a indovinare?
