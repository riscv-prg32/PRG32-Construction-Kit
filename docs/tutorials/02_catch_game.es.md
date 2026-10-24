# Lección 2: un juego de atrapar

Objetivo: mover al jugador a izquierda y derecha y mantenerlo dentro de la pantalla.

## 1. Empieza desde la lección 1

Abre tu proyecto o crea uno nuevo.

## 2. Añade el movimiento

En `en cada fotograma actualizar`, añade:

```text
si el botón izquierda está pulsado
  cambiar player_x en -3

si el botón derecha está pulsado
  cambiar player_x en 3

mantener player_x entre 0 y 304
```

## 3. Prueba el movimiento

1. Haz clic en **Ejecutar** (Shift+F10) y luego en la pantalla del juego.
2. Usa las flechas izquierda y derecha.
3. Comprueba que el cuadrado no puede salir de la pantalla.

## 4. Mira el C

Haz clic en **Generar** y busca:

```c
uint32_t input = prg32_input_read();
if (input & PRG32_BTN_LEFT) {
    player_x += -3;
}
```

Comentad por qué el bloque habla de botones pero el C usa una máscara de bits.
