# How-To Recipes

## How to make a moving player

1. Add `when game starts`.
2. Add `set player_x to 150` and `set player_y to 180`.
3. Add `every frame update`.
4. Add `if button LEFT pressed`, then `change player_x by -3`.
5. Add `if button RIGHT pressed`, then `change player_x by 3`.
6. Add `keep player_x between 0 and 304`.
7. Add `every frame draw`.
8. Add `clear screen BLACK` and `draw rectangle x player_x y player_y w 16 h 16 color YELLOW`.

## How to inspect generated C

1. Open the project editor.
2. Click **Save**.
3. Click **Generate C**.
4. Read the C panel. Match each block to one generated C statement.

## How to create an artifact

Artifacts are created by:

- generating C from a project;
- preparing a cartridge bundle;
- converting a sprite to C;
- uploading a file on the Artifacts page.

## How to move data to another machine

1. Stop the app.
2. Copy the `data/` directory.
3. Start the app on the new machine with `PRG32_KIT_DATA` pointing at that copy.

## How to use with a separate Cartridge Store

1. Start Cartridge Store.
2. Start PRG32-Construction-Kit.
3. Open **Publish**.
4. Create a profile pointing at the store URL.
5. Prepare a cartridge bundle from a project.
6. Publish the bundle.
