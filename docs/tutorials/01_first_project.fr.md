# Leçon 1 : le premier projet en blocs

Objectif : créer un petit jeu PRG32 qui dessine un carré pour le joueur.

## 1. Crée le projet

1. Ouvre la page d'accueil.
2. Clique sur **Nouveau projet**.
3. Laisse **Blocs** sélectionné. (La fenêtre propose aussi **C**, **Assembleur (RISC-V)** et
   **Python (PRG32 Python)** : ils partent d'un petit jeu qui fonctionne déjà, écrit en code et
   expliqué ligne par ligne.)
4. Appelle-le `First Square`.
5. Clique sur **Créer**.

## 2. Prépare l'état de départ

Dans la zone des blocs :

1. Fais glisser `quand le jeu démarre`.
2. Ajoute `mettre player_x à 150`.
3. Ajoute `mettre player_y à 180`.

## 3. Dessine le carré

1. Fais glisser `à chaque image dessiner`.
2. Ajoute `effacer l'écran noir`.
3. Ajoute `dessiner un rectangle x player_x y player_y l 16 h 16 couleur jaune`.

## 4. Lance-le

Clique sur **Exécuter** (Shift+F10). Le kit construit ton jeu et le lance dans le simulateur à
droite : tu dois voir un carré jaune sur l'écran de la PRG32.

## 5. Enregistre et exporte

1. Clique sur **Enregistrer** (Ctrl+S).
2. Ouvre le menu **Projet** et choisis **Exporter en JSON**.

Le fichier téléchargé est un jeu PRG32 en blocs enregistré en JSON.

## 6. Obtiens une cartouche pour ta PRG32

Clique sur **Compiler** (il faut un compte), puis sur le lien **Télécharger le .prg32 esp32c6**
dans l'onglet **Compilation**. Le kit compile tes blocs et ton navigateur enregistre un fichier
comme `first-square-esp32c6.prg32`. Ce fichier est ta cartouche PRG32 : copie-le dans un
emplacement de cartouche de la carte. Le lien **Télécharger le .prg32 qemu** à côté est le même
jeu pour l'émulateur QEMU.
