# Leçon 9 : ton premier jeu en PRG32 Python

Durée : environ 40 minutes. Il ne te faut que le kit (même en invité). Le langage est décrit dans
[PRG32 Python](../python_language.md).

## 1. Crée un projet Python

1. Dans **Projets**, appuie sur **Nouveau projet**.
2. Choisis **Python (PRG32 Python)**, appelle-le `Catcher` et appuie sur **Créer**.
3. L'IDE ouvre `game.py` : un petit jeu qui marche déjà. Appuie sur **Exécuter** (Shift+F10).
   Clique sur l'écran et déplace le carré jaune avec les flèches.

## 2. Lis les trois fonctions

- `init()` s'exécute une fois, quand le jeu démarre.
- `update()` s'exécute à chaque image : elle lit les boutons et fait bouger les choses.
- `draw()` s'exécute à chaque image après `update()` : elle peint l'écran.

Passe la souris sur `prg32.rect` pour lire ce que cela fait. Tape `prg32.` sur une nouvelle ligne
et appuie sur **Ctrl+Space** pour voir tout ce que propose la PRG32.

## 3. Ajoute une étoile qui tombe

Ajoute deux variables en haut, sous `score` :

```python
star_x: int = 100
star_y: int = 0
```

Dans `update()`, la ligne `global` nomme chaque variable extérieure que `update()` modifie.
Fais-lui nommer aussi l'étoile, puis fais descendre l'étoile :

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

Dans `draw()`, dessine-la : `prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`. Appuie sur
**Exécuter**.

## 4. Attrape-la

Toujours dans `update()` :

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

Dans `draw()`, affiche le score : `prg32.number(score, 8, 24, prg32.YELLOW)`.

## 5. Fais une erreur exprès

Écris `star_y = star_y / 2` et attends un instant : l'éditeur souligne `/` et dit que les nombres
de la PRG32 sont entiers. Remplace-le par `//`. Maintenant écris `while True:` sur une nouvelle
ligne : l'éditeur explique pourquoi les boucles doivent utiliser `for i in range(...)`. Efface-le.

## 6. Regarde le C et l'assembleur

Appuie sur **Générer** (Ctrl+Shift+G). Dans **Générés (lecture seule)**, ouvre `game.c` et
`game.S`. Trouve ton `star_y += 2` : le commentaire au-dessus dit `Step "change star_y by 2"`, et
la ligne C est `star_y += 2;`. Dans l'assembleur, la même étape est un chargement, un `addi` et un
enregistrement, chacun expliqué.

## 7. Débogue une ligne

Ouvre l'onglet **Débogage** et appuie sur **Exécuter**. Dans **game.py**, appuie sur le numéro de
ligne de `score += 1`. Attrape une étoile : le jeu s'arrête sur cette ligne. Regarde les
**Variables**, puis appuie sur **Ligne Python suivante**. Appuie sur **Continuer** pour rejouer.

## Pour les enseignants

- Le kit n'exécute jamais le Python de l'élève : il est lu, vérifié selon les règles de PRG32
  Python et traduit dans la même IR que les blocs, puis en C et en assembleur avec des
  explications.
- Le même game.py donne toujours un C, un assembleur et une cartouche identiques octet par
  octet, dans toutes les langues de l'interface.
- Un projet Python reste un projet Python : un enregistrement ne peut pas le transformer en
  blocs, en C ou en assembleur. Pour comparer les langages, fais un projet C à partir de la même
  idée, ou ouvre le C généré.
