# Lezione 4: prepara e pubblica un pacchetto di cartucce

Obiettivo: creare un pacchetto per il Cartridge Store da un progetto a blocchi.

## 1. Genera

Apri un progetto e fai clic su **Genera**. Controlla che il C generato abbia senso.

## 2. Prepara la cartuccia

Fai clic su **Compila**.

Se la toolchain di compilazione PRG32 è installata, il risultato è un pacchetto pubblicabile che contiene file `.prg32`. Se non lo è, il kit crea un pacchetto didattico con il solo codice sorgente; l'immagine Docker ha la toolchain già inclusa (vedi `../install_cartridge_build.md`).

Per provare una singola cartuccia prima di pubblicarla, premi **Esegui** (il simulatore a destra) oppure scaricane una dalla scheda **Compilazione**.
Pubblica il pacchetto fatto da **Compila**, così lo Store riceve tutte le architetture.

## 3. Configura un profilo dello Store

1. Apri **Pubblica**.
2. Aggiungi un profilo con l'indirizzo del Cartridge Store.
3. Aggiungi un token bearer se il tuo Store lo richiede.

## 4. Pubblica

1. Trova il pacchetto nell'elenco.
2. Fai clic su **Rivedi**: la pagina mostra esattamente cosa verrà inviato (Store, cartuccia,
   versioni, impronte dei file).
3. Spunta la casella, fai clic su **Conferma** e leggi il pannello della risposta.

Per pubblicare serve il ruolo di publisher; senza, chiedi al tuo insegnante di pubblicare per te.

Un vero Cartridge Store può rispondere con un invio in attesa, che deve essere verificato da un redattore.
