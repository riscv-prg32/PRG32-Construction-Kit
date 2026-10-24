# Leçon 4 : préparer et publier un paquet de cartouches

Objectif : créer un paquet pour le Cartridge Store à partir d'un projet en blocs.

## 1. Génère

Ouvre un projet et clique sur **Générer**. Vérifie que le C généré a du sens.

## 2. Prépare la cartouche

Clique sur **Compiler**.

Si la chaîne de compilation PRG32 est installée, le résultat est un paquet publiable qui contient des fichiers `.prg32`. Sinon, le kit crée un paquet pédagogique avec seulement le code source ; l'image Docker contient déjà la chaîne d'outils (voir `../install_cartridge_build.md`).

Pour essayer une seule cartouche avant de publier, appuie sur **Exécuter** (le simulateur à droite) ou télécharges-en une depuis l'onglet **Compilation**.
Publie le paquet fait par **Compiler**, pour que le Store reçoive toutes les architectures.

## 3. Configure un profil de Store

1. Ouvre **Publier**.
2. Ajoute un profil avec l'adresse du Cartridge Store.
3. Ajoute un jeton bearer si ton Store en demande un.

## 4. Publie

1. Trouve le paquet dans la liste.
2. Clique sur **Vérifier** : la page montre exactement ce qui sera envoyé (Store, cartouche,
   versions, empreintes des fichiers).
3. Coche la case, clique sur **Confirmer** et lis le panneau de réponse.

Publier demande le rôle d'éditeur ; sans lui, demande à ton enseignant de publier pour toi.

Un vrai Cartridge Store peut répondre par une soumission en attente, qu'un éditeur doit vérifier.
