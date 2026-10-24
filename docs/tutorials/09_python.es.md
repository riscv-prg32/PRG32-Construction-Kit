# Lección 9: tu primer juego en PRG32 Python

Tiempo: unos 40 minutos. Solo necesitas el kit (también vale como invitado). El lenguaje se
describe en [PRG32 Python](../python_language.md).

## 1. Crea un proyecto Python

1. En **Proyectos**, pulsa **Nuevo proyecto**.
2. Elige **Python (PRG32 Python)**, llámalo `Catcher` y pulsa **Crear**.
3. El IDE abre `game.py`: un juego pequeño que ya funciona. Pulsa **Ejecutar** (Shift+F10). Haz
   clic en la pantalla y mueve el cuadrado amarillo con las flechas.

## 2. Lee las tres funciones

- `init()` se ejecuta una vez, cuando empieza el juego.
- `update()` se ejecuta en cada fotograma: lee los botones y mueve las cosas.
- `draw()` se ejecuta en cada fotograma después de `update()`: pinta la pantalla.

Pasa el ratón por encima de `prg32.rect` para leer lo que hace. Escribe `prg32.` en una línea
nueva y pulsa **Ctrl+Space** para ver todo lo que ofrece la PRG32.

## 3. Añade una estrella que cae

Añade dos variables arriba, debajo de `score`:

```python
star_x: int = 100
star_y: int = 0
```

En `update()`, la línea `global` nombra cada variable de fuera que `update()` cambia. Haz que
nombre también a la estrella y luego haz que baje:

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

En `draw()`, dibújala: `prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`. Pulsa **Ejecutar**.

## 4. Atrápala

Todavía en `update()`:

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

En `draw()`, muestra la puntuación: `prg32.number(score, 8, 24, prg32.YELLOW)`.

## 5. Equivócate a propósito

Escribe `star_y = star_y / 2` y espera un momento: el editor subraya `/` y dice que los números
de PRG32 son enteros. Cámbialo por `//`. Ahora escribe `while True:` en una línea nueva: el editor
explica por qué los bucles deben usar `for i in range(...)`. Bórralo otra vez.

## 6. Mira el C y el ensamblador

Pulsa **Generar** (Ctrl+Shift+G). En **Generados (solo lectura)**, abre `game.c` y `game.S`.
Busca tu `star_y += 2`: el comentario de encima dice `Step "change star_y by 2"`, y la línea de C
es `star_y += 2;`. En el ensamblador, el mismo paso es una carga, un `addi` y un guardado, cada
uno explicado.

## 7. Depura una línea

Abre la pestaña **Depurar** y pulsa **Ejecutar**. En **game.py**, pulsa el número de línea de
`score += 1`. Atrapa una estrella: el juego se para en esa línea. Mira las **Variables** y pulsa
**Siguiente línea de Python**. Pulsa **Continuar** para seguir jugando.

## Para los profesores

- El kit nunca ejecuta el Python del alumno: se lee, se comprueba con las reglas de PRG32 Python
  y se traduce a la misma IR que los bloques, y después a C y ensamblador con explicaciones.
- El mismo game.py siempre da C, ensamblador y cartucho idénticos byte a byte, en cualquier
  idioma de la interfaz.
- Un proyecto Python sigue siendo un proyecto Python: un guardado no puede convertirlo en
  bloques, C o ensamblador. Para comparar lenguajes, crea un proyecto C a partir de la misma
  idea, o abre el C generado.
