# Lección 1: el primer proyecto de bloques

Objetivo: crear un pequeño juego PRG32 que dibuja un cuadrado para el jugador.

## 1. Crea el proyecto

1. Abre la página de inicio.
2. Haz clic en **Nuevo proyecto**.
3. Deja seleccionado **Bloques**. (El cuadro también ofrece **C**, **Ensamblador (RISC-V)** y
   **Python (PRG32 Python)**: empiezan con un pequeño juego que ya funciona, escrito como código y
   explicado línea a línea.)
4. Llámalo `First Square`.
5. Haz clic en **Crear**.

## 2. Prepara el estado inicial

En el área de bloques:

1. Arrastra `cuando empieza el juego`.
2. Añade `fijar player_x a 150`.
3. Añade `fijar player_y a 180`.

## 3. Dibuja el cuadrado

1. Arrastra `en cada fotograma dibujar`.
2. Añade `borrar la pantalla negro`.
3. Añade `dibujar rectángulo x player_x y player_y an 16 al 16 color amarillo`.

## 4. Ejecútalo

Haz clic en **Ejecutar** (Shift+F10). El kit construye tu juego y lo inicia en el simulador de
la derecha: deberías ver un cuadrado amarillo en la pantalla de la PRG32.

## 5. Guarda y exporta

1. Haz clic en **Guardar** (Ctrl+S).
2. Abre el menú **Proyecto** y elige **Exportar como JSON**.

El archivo descargado es un juego PRG32 de bloques guardado como JSON.

## 6. Consigue un cartucho para tu PRG32

Haz clic en **Compilar** (necesita una cuenta) y luego en el enlace **Descargar .prg32 para
esp32c6** de la pestaña **Compilación**. El kit compila tus bloques y el navegador guarda un
archivo como `first-square-esp32c6.prg32`. Ese archivo es tu cartucho PRG32: cópialo en una
ranura de cartucho de la placa. El enlace **Descargar .prg32 para qemu** de al lado es el mismo
juego para el emulador QEMU.
