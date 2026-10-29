# Lección 4: prepara y publica un paquete de cartuchos

Objetivo: crear un paquete para el Cartridge Store a partir de un proyecto de bloques.

## 1. Genera

Abre un proyecto y haz clic en **Generar**. Comprueba que el C generado tiene sentido.

## 2. Prepara el cartucho

Haz clic en **Compilar**.

Si la cadena de herramientas de compilación PRG32 está instalada, el resultado es un paquete publicable con archivos `.prg32`. Si no lo está, el kit crea un paquete didáctico solo con el código fuente; la imagen de Docker ya incluye las herramientas (consulta `../install_cartridge_build.md`).

Para probar un solo cartucho antes de publicarlo, pulsa **Ejecutar** (el simulador de la derecha) o descarga uno de la pestaña **Compilación**.
Publica el paquete hecho con **Compilar**, para que el Store reciba todas las arquitecturas.

## 3. Configura un perfil del Store

1. Abre **Publicar**.
2. Añade un perfil con la dirección del Cartridge Store.
3. Añade un token bearer si tu Store lo pide.

## 4. Publica

1. Busca el paquete en la lista.
2. Haz clic en **Revisar**: la página muestra exactamente qué se enviará (Store, cartucho,
   versiones, huellas de los archivos).
3. Marca la casilla, haz clic en **Confirmar** y lee el panel de respuesta.

Publicar necesita el rol de publicador; sin él, pide a tu profesor que publique por ti.

Un Cartridge Store real puede responder con un envío pendiente que debe verificar un editor.
