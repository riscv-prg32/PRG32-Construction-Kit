# Lección 5: una clase de laboratorio para el profesor

Objetivo: dirigir una actividad de clase de 45 minutos.

## Preparación

1. Inicia PRG32-Construction-Kit. Con Docker (`docker compose up -d --build`)
   la compilación de cartuchos funciona desde el principio. Compruébala antes de la clase con
   `docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2`
   (consulta `../install_cartridge_build.md`).
2. Opcional: inicia el Cartridge Store.
3. Opcional: conecta un dispositivo PRG32 o prepara QEMU.
4. Comprueba que los alumnos pueden abrir la aplicación web.

## 0-5 minutos: demostración

Muestra el proyecto inicial. Mueve el cuadrado del jugador en el simulador.

## 5-20 minutos: los alumnos construyen

Los alumnos cambian:

- el color del jugador;
- la velocidad del jugador;
- la posición inicial;
- el texto del título.

## 20-30 minutos: debate sobre el C generado

Los alumnos hacen clic en **Generar** y abren `game.c` en **Generados (solo lectura)** para
encontrar la instrucción C que produce un bloque. Los alumnos mayores abren `game.S` al lado y
encuentran el mismo bloque en el ensamblador: su comentario muestra la línea de C y cada
instrucción dice lo que hace (consulta `../generated_code.md`). `game.py` muestra los mismos
bloques en PRG32 Python.

## 30-40 minutos: sprites y artefactos

Los alumnos dibujan un sprite, lo convierten a C y descargan el artefacto.
Si hay una placa PRG32 o QEMU, los alumnos hacen clic en **Compilar**, descargan desde la
pestaña **Compilación** y cargan su propio cartucho PRG32.

## 40-45 minutos: reflexión

Pregunta:

- ¿Qué bloque cambió una variable?
- ¿En qué instrucción de C se convirtió?
- ¿Qué instrucciones RISC-V hacen el mismo trabajo?
- ¿Por qué ayuda el simulador antes de usar el hardware?
- ¿Qué hay dentro de un cartucho `.prg32` comparado con el C generado?

## Después: una unidad sobre juegos clásicos

Los cinco juegos completos de `examples/games/` tienen cada uno una lección de 90-120 minutos y
diapositivas (`docs/tutorials/games/`, diapositivas en `/docs/presentations/<game>.html`). Pong
presenta el bucle de juego y las colisiones; Breakout las listas; Space Invaders las imágenes y
los grupos de objetos; Asteroids la física de coma fija; Snake las baldosas y los búferes
circulares. Cada presentación termina con ejercicios y una pregunta de comprobación.
