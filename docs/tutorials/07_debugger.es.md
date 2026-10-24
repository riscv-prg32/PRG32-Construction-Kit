# Lección 7: mira dentro del procesador con el depurador

Tu juego es una lista de instrucciones RISC-V. El procesador las ejecuta una a una, muy deprisa:
decenas de miles en cada fotograma. El **depurador** te permite pararlo y ejecutar una
instrucción cada vez, para ver lo que pasa de verdad.

Necesitas un cartucho construido por el kit: en el IDE pulsa **Ejecutar** y abre la pestaña
**Depurar** debajo del editor, o pulsa **Compilar** y luego **Depurar** en el menú superior (el
Reproductor con su depurador, debajo de la pantalla). En esa página también puedes abrir
cualquier archivo `.prg32`.

## Para los alumnos

1. Activa el **Modo depuración**. Ahora el procesador comprueba, antes de cada instrucción, si
   le pediste que se parara ahí.
2. Pulsa **Paso**. La fila azul es la siguiente instrucción; después de cada paso baja. Mira los
   **Registros**: el que acaba de cambiar se pone amarillo.
3. Haz clic en el espacio gris a la izquierda de una dirección. Aparece un **●** rojo: es un
   **punto de interrupción**. Pulsa **Continuar**: el juego sigue y se para justo antes de esa
   instrucción. Pulsa **Continuar** otra vez: ejecuta otro fotograma y vuelve a pararse ahí.
4. **Paso de fotograma** ejecuta hasta el final del fotograma (update + draw) y se para, salvo
   que antes llegue un punto de interrupción.
5. Pon la velocidad en **0.01×** y pulsa **Continuar**: puedes ver la fila azul recorrer el
   código.

Cosas que buscar:

- Los botones **Update** y **Draw** muestran dónde empiezan tus funciones `update` y `draw`. En
  cada fotograma el procesador ejecuta update y luego draw.
- `a0` guarda el primer número que recibe una función y el número que devuelve. Pon un punto de
  interrupción después de un `jalr` (una llamada a función) y mira `a0`.
- `sp` (el puntero de pila) *baja* cuando empieza una función (`addi sp, sp, -16`) y vuelve a
  *subir* cuando termina.
- El **tiempo de juego** es el tiempo que el juego cree que ha pasado (33 ms por fotograma). El
  **tiempo real** es tu reloj. A 0.01× son muy distintos, pero el juego se comporta igual.

## Depura tus bloques, tu C o tu ensamblador

Cuando el cartucho lo construyó el kit (**Ejecutar** en el IDE, o **Compilar** y luego
**Depurar** en el menú superior), el depurador también conoce tu programa, no solo sus
instrucciones. Debajo del código máquina ves:

- **Bloques** (proyectos de bloques): tus bloques. Mientras el juego está parado, el bloque que
  se ejecuta tiene un borde azul. Haz clic en un bloque (o elígelo en la lista) y pulsa
  **● Punto de interrupción en el bloque**: el juego se para cada vez que empieza ese bloque.
- **game.c** o **game.S**: tu código. La línea que se ejecuta es azul. Pulsa un número de línea
  para poner un punto de interrupción **●** en esa línea. Si una línea no tiene código propio (el
  compilador movió su trabajo), el punto de interrupción pasa a la siguiente línea que tenga, y
  el Reproductor te lo dice.
- **Siguiente bloque** / **Siguiente línea**: ejecuta hasta el siguiente bloque (o línea) de tu
  programa. Las llamadas a funciones se ejecutan enteras.
- **Variables**: las variables de tus bloques (`score`, `ball_x`, ...) con sus valores. En la
  vista Avanzada también las variables de la función que se ejecuta.
- **Vigilancias**: escribe un nombre y pulsa **Vigilar**: `score`, `player.x`, `heights[2]` o un
  registro como `a0`.
- **Pila de llamadas**: qué función llamó a cuál. Pulsa una para ver sus variables.
- **Parar solo si...**: da a un punto de interrupción una condición como `score > 10` y el juego
  se para ahí solo cuando sea cierta.

Pruébalo: pon un punto de interrupción en el bloque que mueve la pelota, vigila `ball_x` y pulsa
**Continuar** unas cuantas veces. Dale al punto de interrupción la condición `ball_x < 50`: ahora
solo se para cuando la pelota está cerca de la pared izquierda.

A veces una variable dice *eliminada por la optimización*: el compilador hizo tu programa más
rápido y no guardó ese valor en ese punto. El depurador lo dice en lugar de adivinar.

A veces la pila de llamadas muestra una función marcada como **copiada en** otra: el compilador
copió esa pequeña función dentro de la que la llama, así que no tiene marco propio. El depurador
sigue mostrando dónde estás dentro de ella y la línea desde la que se llamó; sus variables no se
muestran (pulsa la función en la que se copió para ver las de esa).

**Tus puntos de interrupción se quedan** cuando cambias el juego y lo compilas de nuevo. Cada
uno recuerda el código de su línea: si ese código se movió, el punto de interrupción se mueve con
él; si el código ya no está, el punto de interrupción aparece como *el código ha cambiado* y no
se pone en ningún otro sitio. La casilla delante de un punto de interrupción lo apaga sin
perderlo (su punto en el código se vuelve ○).

## Vista avanzada

**Avanzada** muestra los 32 registros en hexadecimal, las palabras de máquina de cada
instrucción, un visor de memoria y dos botones más:

- **Pasar por encima**: en una llamada (`jal`, `jalr`), ejecuta toda la función llamada y se para
  en la línea siguiente.
- **Salir de la función**: ejecuta hasta que la función actual vuelve a quien la llamó.

El visor de memoria acepta una dirección decimal (`1082130432`) o hexadecimal (`0x40800000`) y
muestra hasta 1024 bytes en hexadecimal y como texto. Con un cartucho del kit, la vista Avanzada
también muestra los **CSR contadores** (`cycle`, `time`, `instret`: lo que leería `csrr`) y la
**pila**: las palabras alrededor de `sp`.

Principiante y Avanzada son dos formas de mirar lo mismo: cambiar de vista no cambia el juego, y
los puntos de interrupción se quedan.

## Para los profesores

- Es el mismo depurador que el de PRG32-QT (mismas instrucciones, mismas reglas: los puntos de
  interrupción se comprueban antes de ejecutar una instrucción; **Continuar** deja una vez el
  punto de interrupción actual). Pasar por encima, Salir de la función, Paso de fotograma y la
  vista Principiante son añadidos; consulta `../compatibility.md`.
- Los puntos de interrupción se recuerdan en el navegador para ese cartucho exacto. Un cartucho
  recompilado es otro y empieza sin ninguno.
- Todo se ejecuta en el navegador del alumno; no se envía nada al servidor.
- Buenos primeros ejercicios: contar cuántas instrucciones necesita un fotograma (mira el
  contador de instrucciones entre dos paradas en el mismo punto de interrupción); encontrar la
  instrucción que cambia la posición x de un sprite; comparar un juego de bloques con su
  ensamblador generado (**Generar** en el editor).
- La depuración del código y de los bloques necesita un cartucho compilado por el kit: el kit
  compila con la información de depuración aparte (el cartucho es exactamente el mismo,
  `../adr/0015-source-and-block-debugger.md`). Un `.prg32` abierto desde un archivo solo tiene el
  depurador de código máquina.
- Un buen ejercicio con bloques: encontrar qué bloque cambia `score`, usando un punto de
  interrupción con la condición `score > 0`.
