# Leçon 10 : tes images en Blocs, Python, C et assembleur

Durée : environ 40 minutes. Il te faut seulement le kit (même en invité). Les règles sont dans
[Les images et les sons du projet dans ton jeu](../project_art.md).

## 1. Ajoute Star Catcher

1. Dans **Projets**, trouve **Star Catcher (Blocks)** parmi les exemples (badge *sprites et sons*)
   et appuie sur **Ajouter**.
2. Ouvre-le et appuie sur **Exécuter** (Shift+F10). Déplace la fusée avec les flèches et attrape
   l'étoile qui tombe.
3. Dans les fichiers du projet, ouvre **Sprites → rocket**. Sprite Lab s'ouvre dans un onglet.

## 2. Change les images, pas le code

1. Dans Sprite Lab, peins le nez de la fusée d'une autre couleur et appuie sur **Enregistrer**.
2. Appuie de nouveau sur **Exécuter** : le jeu dessine la nouvelle fusée. Tu n'as changé aucun
   bloc.
3. Regarde sous **Utilise-le dans ton jeu** dans Sprite Lab. Choisis **Blocs**, puis **PRG32
   Python**, **C** et **Assembleur** : le même sprite, utilisé dans quatre langages.

## 3. Lis les blocs

La catégorie **Sprites et tuiles** a trois blocs pour tes images :

```text
quand le jeu démarre :       charge le décor sky
à chaque image dessiner :    dessine le décor sky
                             dessine le sprite rocket x rocket_x y 160
                             dessine le sprite star x star_x y star_y
```

Charge un décor une seule fois, dessine-le en premier à chaque image, puis dessine les sprites
par-dessus. Appuie sur **Générer** et ouvre `game.c` : la partie 3 contient `rocket_draw`,
`star_draw`, `sky_load` et `sky_draw`, faits à partir des images.

## 4. Le même jeu en PRG32 Python

Ajoute **Star Catcher (Python)** et ouvre `game.py`. Les images sont nommées entre guillemets :

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

Remplace `"star"` par `"stars"` et enregistre. Le panneau Problèmes dit, sur cette ligne, que le
projet n'a pas de sprite de ce nom. Remets-le comme avant.

## 5. Le même jeu en C

Ajoute **Star Catcher (C)**. En haut de `game.c`, une seule ligne suffit pour toutes les images :

```c
#include "prg32_assets.h"
```

Ouvre **Images et sons du projet → prg32_assets.h** dans les fichiers du projet : il est en
lecture seule et montre le code que le kit écrit à la place de cette ligne quand le jeu est
compilé. Trouve `rocket_draw`, `ROCKET_WIDTH`, `sky_load`, `sfx_coin` et `TRACK_THEME`, puis
trouve où `game.c` les utilise.

## 6. Le même jeu en assembleur

Ajoute **Star Catcher (Assembly)**. Sa ligne est `#include "prg32_assets.S"`, et ses images
s'appellent comme une fonction du firmware :

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

Exécute les quatre jeux : ils dessinent exactement la même image.

## 7. À toi

- Dessine dans Sprite Lab un nouveau sprite appelé `comet` et enregistre-le. Dessine-le dans
  chaque jeu : un bloc, une ligne `prg32.sprite("comet", ...)`, `comet_draw(x, y);` en C,
  `call comet_draw` en assembleur.
- Dans **Décors**, ajoute à `sky` une deuxième couche avec des nuages. `dessine le décor sky` la
  dessine devant, avec la tuile 0 transparente.
- Dans AudioStudio, change le son **Coin**. Chaque jeu joue le nouveau son.
