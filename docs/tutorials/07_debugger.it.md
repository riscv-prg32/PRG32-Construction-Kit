# Lezione 7: guarda dentro il processore con il debugger

Il tuo gioco è un elenco di istruzioni RISC-V. Il processore le esegue una alla volta, molto
velocemente: decine di migliaia a ogni fotogramma. Il **debugger** ti permette di fermarlo ed
eseguire un'istruzione alla volta, per vedere che cosa succede davvero.

Ti serve una cartuccia costruita dal kit: nell'IDE premi **Esegui** e apri la scheda **Debug**
sotto l'editor, oppure premi **Compila** e poi **Debug** nel menu in alto (il Lettore con il suo
debugger, sotto lo schermo). In quella pagina puoi anche aprire qualsiasi file `.prg32`.

## Per gli studenti

1. Accendi la **Modalità debug**. Ora il processore controlla, prima di ogni istruzione, se gli
   hai chiesto di fermarsi lì.
2. Premi **Passo**. La riga blu è la prossima istruzione; dopo ogni passo scende. Guarda i
   **Registri**: quello appena cambiato diventa giallo.
3. Fai clic sullo spazio grigio a sinistra di un indirizzo. Appare un **●** rosso: è un **punto
   di interruzione**. Premi **Continua**: il gioco va avanti e si ferma proprio prima di
   quell'istruzione. Premi di nuovo **Continua**: esegue un altro fotogramma e si ferma ancora lì.
4. **Passo di fotogramma** esegue fino alla fine del fotogramma (update + draw) e si ferma, a
   meno che prima non arrivi un punto di interruzione.
5. Metti la velocità a **0.01×** e premi **Continua**: puoi vedere la riga blu camminare nel
   codice.

Cose da cercare:

- I pulsanti **Update** e **Draw** mostrano dove iniziano le tue funzioni `update` e `draw`. A
  ogni fotogramma il processore esegue update, poi draw.
- `a0` contiene il primo numero che una funzione riceve e il numero che restituisce. Metti un
  punto di interruzione dopo un `jalr` (una chiamata di funzione) e guarda `a0`.
- `sp` (lo stack pointer) *scende* quando una funzione inizia (`addi sp, sp, -16`) e torna *su*
  quando finisce.
- Il **tempo di gioco** è il tempo che il gioco crede sia passato (33 ms a fotogramma). Il
  **tempo reale** è il tuo orologio. A 0.01× sono molto diversi, ma il gioco si comporta allo
  stesso modo.

## Fai il debug dei blocchi, del C o dell'assembly

Quando la cartuccia l'ha costruita il kit (**Esegui** nell'IDE, oppure **Compila** e poi
**Debug** nel menu in alto), il debugger conosce anche il tuo programma, non solo le sue
istruzioni. Sotto il codice macchina vedi:

- **Blocchi** (progetti a blocchi): i tuoi blocchi. Mentre il gioco è fermo, il blocco in
  esecuzione ha un contorno blu. Fai clic su un blocco (o sceglilo nell'elenco) e premi
  **● Punto di interruzione sul blocco**: il gioco si ferma ogni volta che quel blocco inizia.
- **game.c** o **game.S**: il tuo codice. La riga in esecuzione è blu. Premi il numero di una riga
  per mettere un punto di interruzione **●** su quella riga. Se una riga non ha codice suo (il
  compilatore ha spostato il suo lavoro), il punto di interruzione va alla riga successiva che ne
  ha, e il Lettore te lo dice.
- **Blocco successivo** / **Riga successiva**: esegue fino al prossimo blocco (o riga) del tuo
  programma. Le chiamate di funzione vengono eseguite intere.
- **Variabili**: le variabili dei tuoi blocchi (`score`, `ball_x`, ...) con i loro valori. Nella
  vista Avanzata anche le variabili della funzione in esecuzione.
- **Osservati**: scrivi un nome e premi **Osserva**: `score`, `player.x`, `heights[2]` oppure un
  registro come `a0`.
- **Pila delle chiamate**: quale funzione ha chiamato quale. Premine una per vedere le sue
  variabili.
- **Fermati solo se...**: dai a un punto di interruzione una condizione come `score > 10` e il
  gioco si ferma lì solo quando è vera.

Prova: metti un punto di interruzione sul blocco che muove la palla, osserva `ball_x`, poi premi
**Continua** qualche volta. Dai al punto di interruzione la condizione `ball_x < 50`: ora si
ferma solo quando la palla è vicina alla parete sinistra.

A volte una variabile dice *eliminata dall'ottimizzazione*: il compilatore ha reso il programma
più veloce e non ha tenuto quel valore in quel punto. Il debugger lo dice invece di tirare a
indovinare.

A volte la pila delle chiamate mostra una funzione segnata **copiata in** un'altra: il
compilatore ha copiato quella piccola funzione dentro quella che la chiama, quindi non ha un
riquadro suo. Il debugger mostra comunque dove sei al suo interno e la riga da cui è stata
chiamata; le sue variabili non vengono mostrate (premi la funzione in cui è stata copiata per
vedere quelle).

**I tuoi punti di interruzione restano** quando cambi il gioco e lo compili di nuovo. Ognuno
ricorda il codice della sua riga: se quel codice si è spostato, il punto di interruzione si
sposta con lui; se il codice non c'è più, il punto di interruzione è elencato come *il codice è
cambiato* e non viene messo da nessun'altra parte. La casella davanti a un punto di interruzione
lo spegne senza perderlo (il suo pallino nel codice diventa ○).

## Vista avanzata

**Avanzata** mostra tutti i 32 registri in esadecimale, le parole macchina di ogni istruzione,
un visualizzatore della memoria e due pulsanti in più:

- **Passa oltre**: su una chiamata (`jal`, `jalr`) esegue tutta la funzione chiamata e si ferma
  alla riga successiva.
- **Esci dalla funzione**: esegue finché la funzione corrente non torna a chi l'ha chiamata.

Il visualizzatore della memoria accetta un indirizzo decimale (`1082130432`) o esadecimale
(`0x40800000`) e mostra fino a 1024 byte in esadecimale e come testo. Con una cartuccia del kit,
la vista Avanzata mostra anche i **CSR contatori** (`cycle`, `time`, `instret`: quello che
leggerebbe `csrr`) e lo **stack**: le parole intorno a `sp`.

Principiante e Avanzata sono due modi di guardare la stessa cosa: cambiare vista non cambia il
gioco, e i punti di interruzione restano.

## Per gli insegnanti

- È lo stesso debugger di PRG32-QT (stesse istruzioni, stesse regole: i punti di interruzione si
  controllano prima che un'istruzione venga eseguita; **Continua** lascia una volta il punto di
  interruzione corrente). Passa oltre, Esci dalla funzione, Passo di fotogramma e la vista
  Principiante sono aggiunte; vedi `../compatibility.md`.
- I punti di interruzione vengono ricordati nel browser per quella precisa cartuccia. Una
  cartuccia ricompilata è un'altra cartuccia e parte senza.
- Tutto viene eseguito nel browser dello studente; niente viene mandato al server.
- Buoni primi esercizi: contare quante istruzioni servono per un fotogramma (guarda il contatore
  di istruzioni tra due fermate allo stesso punto di interruzione); trovare l'istruzione che
  cambia la posizione x di uno sprite; confrontare un gioco a blocchi con il suo assembly
  generato (**Genera** nell'editor).
- Il debug del codice e dei blocchi ha bisogno di una cartuccia compilata dal kit: il kit compila
  con le informazioni di debug a parte (la cartuccia è esattamente la stessa,
  `../adr/0015-source-and-block-debugger.md`). Un `.prg32` aperto da un file ha solo il debugger
  del codice macchina.
- Un buon esercizio con i blocchi: trovare quale blocco cambia `score`, usando un punto di
  interruzione con la condizione `score > 0`.
