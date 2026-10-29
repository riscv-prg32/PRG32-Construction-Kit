# Lección 8: efectos de sonido y música con AudioStudio

Tiempo: unos 30 minutos. Necesitas un proyecto de bloques (el juego de atrapar de la lección 2
es perfecto).

## 1. Abre AudioStudio

Abre tu proyecto y pulsa **AudioStudio**. La pestaña **Voces** muestra las 8 voces de la consola
PRG32. Pulsa **Pruébalo**: oyes la voz 0. Mueve el deslizador del **ataque** (Attack) hacia la
derecha y prueba otra vez: ahora la nota entra poco a poco. Mira cómo cambia el dibujo de la
envolvente.

## 2. Crea un efecto de sonido

1. Abre **Efectos de sonido** y pulsa **Nuevo**.
2. Llámalo `Catch`.
3. Pon **Nota** en 76 y **Duración** en 120 ms. Elige el sonido **pulse**.
4. Pon el **sostenido** (Sustain) en 0 y la **caída** (Decay) en 60: un "blip" corto. Pulsa
   **Pruébalo**.

## 3. Escribe una melodía pequeña

1. Abre **Bandas sonoras** y pulsa **Nuevo**. Llámala `Theme`.
2. Haz clic en el primer paso de la voz 0 y escribe `C4`. Pulsa la flecha derecha y escribe
   `E4`, luego `G4`, luego `C5`.
3. Pon `off` después de la última nota para que se pare.
4. Marca **Repetir** y pulsa **Tocar**. Pulsa **Esc** para pararla.
5. Añade un bajo en la voz 1 (`C3` en el paso 1, `G2` en el paso 5). Usa **Silencio** en la voz
   0 para oír solo el bajo.

AudioStudio guarda solo. La tarjeta **Lo que dice el código** muestra las líneas de C en que se
convertirán tus bloques.

## 4. Úsalos en el juego

Vuelve al editor de bloques y abre la categoría **Sonido**:

- pon **tocar banda sonora Theme** en *cuando empieza el juego*;
- pon **tocar efecto de sonido Catch** donde el jugador atrapa algo.

Pulsa **Ejecutar** (Shift+F10): oyes los mismos sonidos que en AudioStudio. Mira el C generado:
`prg32_audio_play_track(0);` y `prg32_audio_note(7, 8, 76, 255, 120);`. ¿Sabes qué significa
cada número? (Pista: voz, instrumento, nota, volumen, milisegundos.)

## 5. Preguntas para la clase

- ¿Por qué un efecto de sonido tiene su propia voz? ¿Qué pasa si la música también usa esa voz?
- Cambia el tempo de la banda sonora de 120 a 180. ¿Qué cambia en el C generado y qué no?
- Cambia el nombre del efecto de sonido. ¿Qué dice el generador de código y por qué no adivina?
