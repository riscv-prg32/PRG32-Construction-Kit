# Leçon 8 : effets sonores et musique avec AudioStudio

Durée : environ 30 minutes. Il te faut un projet en blocs (le jeu d'attrape de la leçon 2 est
parfait).

## 1. Ouvre AudioStudio

Ouvre ton projet et appuie sur **AudioStudio**. L'onglet **Voix** montre les 8 voix de la
console PRG32. Appuie sur **Essaie** : tu entends la voix 0. Déplace le curseur de l'**attaque**
(Attack) vers la droite et réessaie : la note arrive maintenant en douceur. Regarde le dessin de
l'enveloppe changer.

## 2. Crée un effet sonore

1. Ouvre **Effets sonores** et appuie sur **Nouveau**.
2. Appelle-le `Catch`.
3. Mets **Note** à 76 et **Durée** à 120 ms. Choisis le son **pulse**.
4. Mets le **maintien** (Sustain) à 0 et la **chute** (Decay) à 60 : un « blip » court. Appuie sur
   **Essaie**.

## 3. Écris une petite mélodie

1. Ouvre **Musiques** et appuie sur **Nouveau**. Appelle-la `Theme`.
2. Clique sur le premier pas de la voix 0 et tape `C4`. Appuie sur la flèche droite et tape
   `E4`, puis `G4`, puis `C5`.
3. Mets `off` après la dernière note pour qu'elle s'arrête.
4. Coche **Boucle** et appuie sur **Jouer**. Appuie sur **Échap** pour l'arrêter.
5. Ajoute une basse sur la voix 1 (`C3` au pas 1, `G2` au pas 5). Utilise **Muet** sur la voix 0
   pour n'entendre que la basse.

AudioStudio enregistre tout seul. La carte **Ce que dit le code** montre les lignes C que vont
devenir tes blocs.

## 4. Utilise-les dans le jeu

Reviens dans l'éditeur de blocs et ouvre la catégorie **Son** :

- mets **jouer la musique Theme** dans *quand le jeu démarre* ;
- mets **jouer l'effet sonore Catch** là où le joueur attrape quelque chose.

Appuie sur **Exécuter** (Shift+F10) : tu entends les mêmes sons que dans AudioStudio. Regarde le
C généré : `prg32_audio_play_track(0);` et `prg32_audio_note(7, 8, 76, 255, 120);`. Peux-tu dire
ce que veut dire chaque nombre ? (Indice : voix, instrument, note, volume, millisecondes.)

## 5. Questions pour la classe

- Pourquoi un effet sonore a-t-il sa propre voix ? Que se passe-t-il si la musique utilise aussi
  cette voix ?
- Change le tempo de la musique de 120 à 180. Qu'est-ce qui change dans le C généré, et qu'est-ce
  qui ne change pas ?
- Renomme l'effet sonore. Que dit le générateur de code, et pourquoi ne devine-t-il pas ?
