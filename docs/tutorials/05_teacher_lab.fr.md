# Leçon 5 : une séance de laboratoire pour l'enseignant

Objectif : mener une activité en classe de 45 minutes.

## Préparation

1. Démarre PRG32-Construction-Kit. Avec Docker (`docker compose up -d --build`),
   la compilation des cartouches marche tout de suite. Vérifie-la avant le cours avec
   `docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2`
   (voir `../install_cartridge_build.md`).
2. Facultatif : démarre le Cartridge Store.
3. Facultatif : branche un appareil PRG32 ou prépare QEMU.
4. Vérifie que les élèves peuvent ouvrir l'application web.

## 0-5 minutes : démonstration

Montre le projet de départ. Déplace le carré du joueur dans le simulateur.

## 5-20 minutes : les élèves construisent

Les élèves modifient :

- la couleur du joueur ;
- la vitesse du joueur ;
- la position de départ ;
- le texte du titre.

## 20-30 minutes : discussion sur le C généré

Les élèves cliquent sur **Générer** et ouvrent `game.c` dans **Générés (lecture seule)** pour
trouver l'instruction C produite par un bloc. Les plus grands ouvrent `game.S` à côté et
retrouvent le même bloc dans l'assembleur : son commentaire montre la ligne C, et chaque
instruction dit ce qu'elle fait (voir `../generated_code.md`). `game.py` montre les mêmes blocs
en PRG32 Python.

## 30-40 minutes : sprites et artefacts

Les élèves dessinent un sprite, le convertissent en C et téléchargent l'artefact.
S'il y a une carte PRG32 ou QEMU, les élèves cliquent sur **Compiler**, téléchargent depuis
l'onglet **Compilation** et chargent leur propre cartouche PRG32.

## 40-45 minutes : bilan

Demande :

- Quel bloc a changé une variable ?
- En quelle instruction C est-il devenu ?
- Quelles instructions RISC-V font le même travail ?
- Pourquoi le simulateur aide-t-il avant le matériel ?
- Qu'y a-t-il dans une cartouche `.prg32` par rapport au C généré ?

## Ensuite : une séquence sur les jeux classiques

Les cinq jeux complets de `examples/games/` ont chacun une leçon de 90 à 120 minutes et des
diapositives (`docs/tutorials/games/`, diapositives dans `/docs/presentations/<game>.html`).
Pong introduit la boucle de jeu et les collisions ; Breakout les listes ; Space Invaders les
images et les réserves d'objets ; Asteroids la physique en virgule fixe ; Snake les tuiles et
les tampons circulaires. Chaque présentation se termine par des exercices et une question de
vérification.
