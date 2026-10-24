# Leçon 2 : un jeu d'attrape

Objectif : déplacer le joueur à gauche et à droite et le garder dans l'écran.

## 1. Pars de la leçon 1

Ouvre ton projet ou crée-en un nouveau.

## 2. Ajoute le mouvement

Dans `à chaque image mettre à jour`, ajoute :

```text
si le bouton gauche est maintenu
  changer player_x de -3

si le bouton droite est maintenu
  changer player_x de 3

garder player_x entre 0 et 304
```

## 3. Teste le mouvement

1. Clique sur **Exécuter** (Shift+F10), puis sur l'écran du jeu.
2. Utilise les flèches gauche et droite.
3. Vérifie que le carré ne peut pas sortir de l'écran.

## 4. Regarde le C

Clique sur **Générer** et trouve :

```c
uint32_t input = prg32_input_read();
if (input & PRG32_BTN_LEFT) {
    player_x += -3;
}
```

Discutez : pourquoi le bloc parle de boutons alors que le C utilise un masque de bits ?
