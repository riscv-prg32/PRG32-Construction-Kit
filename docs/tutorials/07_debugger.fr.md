# Leçon 7 : regarde dans le processeur avec le débogueur

Ton jeu est une liste d'instructions RISC-V. Le processeur les exécute une par une, très vite :
des dizaines de milliers à chaque image. Le **débogueur** te permet de l'arrêter et d'exécuter
une instruction à la fois, pour voir ce qui se passe vraiment.

Il te faut une cartouche construite par le kit : dans l'IDE, appuie sur **Exécuter** et ouvre
l'onglet **Débogage** sous l'éditeur, ou appuie sur **Compiler** puis sur **Débogage** dans le
menu du haut (le Lecteur avec son débogueur, sous l'écran). Sur cette page, tu peux aussi ouvrir
n'importe quel fichier `.prg32`.

## Pour les élèves

1. Active le **Mode débogage**. Désormais, avant chaque instruction, le processeur vérifie si tu
   lui as demandé de s'arrêter là.
2. Appuie sur **Pas**. La ligne bleue est la prochaine instruction ; après chaque pas, elle
   descend. Regarde les **Registres** : celui qui vient de changer devient jaune.
3. Clique dans l'espace gris à gauche d'une adresse. Un **●** rouge apparaît : c'est un **point
   d'arrêt**. Appuie sur **Continuer** : le jeu tourne et s'arrête juste avant cette
   instruction. Appuie encore sur **Continuer** : il exécute une image de plus et s'arrête de
   nouveau là.
4. **Pas d'image** exécute jusqu'à la fin de l'image (update + draw) et s'arrête, sauf si un
   point d'arrêt arrive avant.
5. Mets la vitesse à **0.01×** et appuie sur **Continuer** : tu vois la ligne bleue avancer dans
   le code.

À regarder :

- Les boutons **Update** et **Draw** montrent où commencent tes fonctions `update` et `draw`. À
  chaque image, le processeur exécute update, puis draw.
- `a0` contient le premier nombre qu'une fonction reçoit, et le nombre qu'elle renvoie. Mets un
  point d'arrêt après un `jalr` (un appel de fonction) et regarde `a0`.
- `sp` (le pointeur de pile) *descend* quand une fonction commence (`addi sp, sp, -16`) et
  *remonte* quand elle se termine.
- Le **temps de jeu** est le temps que le jeu croit écoulé (33 ms par image). Le **temps réel**
  est ton horloge. À 0.01× ils sont très différents, mais le jeu se comporte de la même façon.

## Débogue tes blocs, ton C ou ton assembleur

Quand c'est le kit qui a construit la cartouche (**Exécuter** dans l'IDE, ou **Compiler** puis
**Débogage** dans le menu du haut), le débogueur connaît aussi ton programme, pas seulement ses
instructions. Sous le code machine, tu vois :

- **Blocs** (projets en blocs) : tes blocs. Quand le jeu est arrêté, le bloc en cours a un
  contour bleu. Clique sur un bloc (ou choisis-le dans la liste) et appuie sur **● Point d'arrêt
  sur le bloc** : le jeu s'arrête chaque fois que ce bloc commence.
- **game.c** ou **game.S** : ton code. La ligne en cours est bleue. Appuie sur un numéro de ligne
  pour mettre un point d'arrêt **●** sur cette ligne. Si une ligne n'a pas de code à elle (le
  compilateur a déplacé son travail), le point d'arrêt passe à la ligne suivante qui en a, et le
  Lecteur te le dit.
- **Bloc suivant** / **Ligne suivante** : exécute jusqu'au prochain bloc (ou ligne) de ton
  programme. Les appels de fonction s'exécutent en entier.
- **Variables** : les variables de tes blocs (`score`, `ball_x`, ...) avec leurs valeurs. En vue
  Avancée, aussi les variables de la fonction en cours.
- **Surveillances** : écris un nom et appuie sur **Surveiller** : `score`, `player.x`,
  `heights[2]` ou un registre comme `a0`.
- **Pile d'appels** : quelle fonction a appelé laquelle. Appuie sur l'une d'elles pour voir ses
  variables.
- **S'arrêter seulement si...** : donne à un point d'arrêt une condition comme `score > 10`, et
  le jeu ne s'arrête là que lorsqu'elle est vraie.

Essaie : mets un point d'arrêt sur le bloc qui déplace la balle, surveille `ball_x`, puis appuie
plusieurs fois sur **Continuer**. Donne au point d'arrêt la condition `ball_x < 50` : maintenant
il ne s'arrête que lorsque la balle est près du mur de gauche.

Parfois une variable indique *supprimée par l'optimisation* : le compilateur a rendu ton
programme plus rapide et n'a pas gardé cette valeur à cet endroit. Le débogueur le dit au lieu
de deviner.

Parfois la pile d'appels montre une fonction marquée **copiée dans** une autre : le compilateur
a copié cette petite fonction dans celle qui l'appelle, donc elle n'a pas de cadre à elle. Le
débogueur montre quand même où tu es à l'intérieur et la ligne d'où elle a été appelée ; ses
variables ne sont pas montrées (appuie sur la fonction dans laquelle elle a été copiée pour voir
les siennes).

**Tes points d'arrêt restent** quand tu modifies le jeu et le recompiles. Chacun se souvient du
code de sa ligne : si ce code a bougé, le point d'arrêt bouge avec lui ; si le code a disparu, le
point d'arrêt est listé comme *le code a changé* et n'est mis nulle part ailleurs. La case devant
un point d'arrêt le désactive sans le perdre (son point dans le code devient ○).

## Vue avancée

**Avancée** montre les 32 registres en hexadécimal, les mots machine de chaque instruction, un
visualiseur de mémoire et deux boutons de plus :

- **Passer par-dessus** : sur un appel (`jal`, `jalr`), exécute toute la fonction appelée et
  s'arrête à la ligne suivante.
- **Sortir de la fonction** : exécute jusqu'à ce que la fonction en cours revienne à son
  appelant.

Le visualiseur de mémoire prend une adresse décimale (`1082130432`) ou hexadécimale
(`0x40800000`) et montre jusqu'à 1024 octets en hexadécimal et en texte. Avec une cartouche du
kit, la vue Avancée montre aussi les **CSR compteurs** (`cycle`, `time`, `instret` : ce que
lirait `csrr`) et la **pile** : les mots autour de `sp`.

Débutant et Avancée sont deux façons de regarder la même chose : changer de vue ne change pas le
jeu, et les points d'arrêt restent.

## Pour les enseignants

- C'est le même débogueur que celui de PRG32-QT (mêmes instructions, mêmes règles : les points
  d'arrêt sont vérifiés avant qu'une instruction s'exécute ; **Continuer** quitte une fois le
  point d'arrêt courant). Passer par-dessus, Sortir de la fonction, Pas d'image et la vue
  Débutant sont des ajouts ; voir `../compatibility.md`.
- Les points d'arrêt sont mémorisés dans le navigateur pour cette cartouche précise. Une
  cartouche recompilée est une autre cartouche et commence sans point d'arrêt.
- Tout s'exécute dans le navigateur de l'élève ; rien n'est envoyé au serveur.
- Bons premiers exercices : compter combien d'instructions il faut pour une image (regarde le
  compteur d'instructions entre deux arrêts au même point d'arrêt) ; trouver l'instruction qui
  change la position x d'un sprite ; comparer un jeu en blocs avec son assembleur généré
  (**Générer** dans l'éditeur).
- Le débogage du code et des blocs demande une cartouche compilée par le kit : le kit compile
  avec les informations de débogage à part (la cartouche elle-même est exactement la même,
  `../adr/0015-source-and-block-debugger.md`). Un `.prg32` ouvert depuis un fichier n'a que le
  débogueur de code machine.
- Un bon exercice avec les blocs : trouver quel bloc change `score`, avec un point d'arrêt qui a
  la condition `score > 0`.
