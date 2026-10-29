# Lección 10: tu arte en Bloques, Python, C y ensamblador

Tiempo: unos 40 minutos. Solo necesitas el kit (también como invitado). Las reglas están en
[El arte del proyecto en tu juego](../project_art.md).

## 1. Añade Star Catcher

1. En **Proyectos**, busca **Star Catcher (Blocks)** entre los ejemplos (etiqueta *sprites y
   sonido*) y pulsa **Añadir**.
2. Ábrelo y pulsa **Ejecutar** (Shift+F10). Mueve el cohete con las flechas y atrapa la estrella
   que cae.
3. En los archivos del proyecto, abre **Sprites → rocket**. Sprite Lab se abre en una pestaña.

## 2. Cambia el arte, no el código

1. En Sprite Lab, pinta la punta del cohete de otro color y pulsa **Guardar**.
2. Pulsa otra vez **Ejecutar**: el juego dibuja el cohete nuevo. No cambiaste ningún bloque.
3. Mira debajo de **Úsalo en tu juego** en Sprite Lab. Elige **Bloques**, luego **PRG32 Python**,
   **C** y **Ensamblador**: el mismo sprite, usado en cuatro lenguajes.

## 3. Lee los bloques

La categoría **Sprites y baldosas** tiene tres bloques para tu arte:

```text
cuando empieza el juego:    carga el fondo sky
en cada fotograma dibujar:  dibuja el fondo sky
                            dibuja sprite rocket x rocket_x y 160
                            dibuja sprite star x star_x y star_y
```

Carga un fondo una sola vez, dibújalo primero en cada fotograma y después dibuja los sprites
encima. Pulsa **Generar** y abre `game.c`: la parte 3 contiene `rocket_draw`, `star_draw`,
`sky_load` y `sky_draw`, hechos a partir del arte.

## 4. El mismo juego en PRG32 Python

Añade **Star Catcher (Python)** y abre `game.py`. El arte se nombra entre comillas:

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

Cambia `"star"` por `"stars"` y guarda. El panel Problemas dice, en esa línea, que el proyecto no
tiene un sprite con ese nombre. Déjalo como estaba.

## 5. El mismo juego en C

Añade **Star Catcher (C)**. Al principio de `game.c` hay una línea para todo el arte:

```c
#include "prg32_assets.h"
```

Abre **Arte del proyecto → prg32_assets.h** en los archivos del proyecto: es de solo lectura y
muestra el código que el kit escribe en lugar de esa línea cuando se compila el juego. Busca
`rocket_draw`, `ROCKET_WIDTH`, `sky_load`, `sfx_coin` y `TRACK_THEME`, y luego dónde los usa
`game.c`.

## 6. El mismo juego en ensamblador

Añade **Star Catcher (Assembly)**. Su línea es `#include "prg32_assets.S"`, y su arte se llama
como una función del firmware:

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

Ejecuta los cuatro juegos: dibujan exactamente la misma imagen.

## 7. Pruébalo tú

- Dibuja en Sprite Lab un sprite nuevo llamado `comet` y guárdalo. Dibújalo en cada juego: un
  bloque, una línea `prg32.sprite("comet", ...)`, `comet_draw(x, y);` en C, `call comet_draw` en
  ensamblador.
- En **Fondos**, añade a `sky` una segunda capa con nubes. `dibuja el fondo sky` la dibuja
  delante, con la baldosa 0 transparente.
- En AudioStudio, cambia el sonido **Coin**. Cada juego toca el sonido nuevo.
