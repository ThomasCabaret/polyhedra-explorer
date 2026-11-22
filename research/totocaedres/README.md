# Totocaèdres

- [Note de recherche LaTeX](docs/finite_search_bounds.tex)
- [Résultats et certificats](results/README.md)
- [Campagne de découverte par genre](campaign/README.md)

Noyau de recherche pour les surfaces polyédriques fermées dont toutes les
faces sont mutuellement en contact. Le dépôt sépare volontairement trois
étages :

1. une carte combinatoire orientable, vérifiée indépendamment de la géométrie ;
2. une énumération exhaustive **sous bornes publiées** ;
3. une tentative de réalisation 3D, suivie d'un certificat numérique produit
   par un code distinct du solveur.

Le modèle accepte plusieurs composantes de bord par face, plusieurs arêtes
entre deux faces et les contacts ponctuels induits par les sommets. Le chemin
rapide exhaustif actuel traite les cartes trivalentes à graphe dual complet :
le tétraèdre (`F=4, g=0`) et toutes les triangulations orientables enracinées de
`K7` (`F=7, g=1`). L'énumérateur générique couvre des instances bornées plus
petites avec multiplicités et trous ; il refuse les budgets susceptibles de
faire exploser silencieusement la recherche.

## Installation et commandes

Exécutez les commandes depuis ce dossier (research/totocaedres).

```powershell
python -m pip install -e .
python -m totocaedres plan --max-genus 3 --max-faces 10 --max-extra-edges 4 --max-holes 2
python -m totocaedres enumerate-triangular --faces 7 --limit 1 --output output/k7.json
python -m totocaedres validate output/k7.json
python -m totocaedres demo --output-dir output/demo
python -m totocaedres campaign-controls --output output/validation-campaign.json
python -m totocaedres export-viewer results/validation-campaign.json results/discovery/9b4c587e1cb3c920ac499cd6.json --output ../../src/generated-models.js
python -m pytest
```

`plan` liste les signatures `(g,F,M,D,H)` compatibles avec les identités
nécessaires. Cela ne constitue jamais une preuve de réalisabilité. Les fichiers
JSON de carte contiennent toutes les permutations de brins nécessaires à une
relecture indépendante.

Le solveur exploite une jacobienne creuse ; `--restarts` et `--max-nfev`
restent des budgets explicites pour les cartes non triviales.

La campagne de contrôles emploie un second moteur : elle calcule les
automorphismes de la carte, découvre des actions orthogonales `C2`, `C4` ou
`V4`, échantillonne les plans invariants et certifie rationnellement les
candidats. Les noms et coordonnées connus restent dans un catalogue de tests et
ne sont jamais consultés par la recherche. La revue des pièces jointes et les
choix d'intégration sont consignés dans
[`docs/revue_note_algorithmique.md`](docs/revue_note_algorithmique.md).

Le [visualiseur à la racine du dépôt](../../README.md) affiche les contrôles
et la réalisation de Szilassi retrouvée par la campagne. La
commande `export-viewer` convertit les coordonnées rationnelles et les cycles
de faces d'une campagne en module JavaScript, sans recopier de modèle à la
main. Lancez ensuite `serve.bat` depuis la racine du dépôt et ouvrez
`http://127.0.0.1:8000/`.

Pour compiler la note depuis ce dossier :

```powershell
tectonic docs/finite_search_bounds.tex
```

## Campagne continue hors ligne

La campagne de découverte est reprenable et n'a pas de condition d'arrêt
naturelle. Elle parcourt en round-robin les signatures bornées des genres 0 à
3, augmente progressivement le nombre de tirages, conserve chaque carte avant
de lancer la géométrie et écrit un état atomique consultable à tout moment :

```powershell
.\start_campaign.bat
.\status_campaign.bat
.\stop_campaign.bat
```

Les bornes se règlent dans `campaign/config.json`; les résultats et journaux
sont écrits dans `campaign/runtime/`. Les étages `K4` et `K7` sont exhaustifs
dans leur scope. Pour les genres 2 et 3, la campagne actuelle est une
exploration aléatoire bornée de systèmes de rotations, pas encore une
énumération exhaustive à isomorphisme près.

## Périmètre de la version 0.2

- cartes fermées, connexes, orientables et réduites (degré des sommets >= 3) ;
- faces abstraites de genre zéro avec un ou plusieurs contours ;
- contacts par segment dérivés des composantes connexes d'arêtes partagées ;
- contacts ponctuels dérivés des paires de faces non consécutives autour d'un
  sommet ;
- déduplication à isomorphisme près pour le chemin complet trivalent `K_n` ;
- solveur de planéité 3D sans trous, multi-démarrages, puis contrôle numérique
  indépendant (planéité, longueurs, volume, intersections de triangles
  disjoints).
- recherche générique par plans pour les cartes trivalentes, avec symétries
  déduites de la carte et certificat rationnel exact pour les faces-disques.

Ne sont pas encore des preuves exactes : la réalisabilité 3D, l'absence
d'intersection dans les cas dégénérés et les coordonnées issues du solveur.
Le certificat les qualifie explicitement de numériques. Les mathématiques et
les limites de complétude sont détaillées dans
[`docs/mathematiques.md`](docs/mathematiques.md). La note de recherche en
anglais démontre la finitude à nombre de faces fixé, même lorsque plusieurs
plans partagent une droite. Une borne absolue sur le genre ou sur le nombre
de faces reste à établir. [`docs/finite_search_bounds.tex`](docs/finite_search_bounds.tex).
