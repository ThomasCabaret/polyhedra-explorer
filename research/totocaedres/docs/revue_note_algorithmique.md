# Revue critique des contrôles positifs

## Verdict

La note algorithmique et son archive sont cohérentes avec le cadrage initial,
mais elles répondent à une question plus étroite. Elles contiennent de bons
**contrôles positifs géométriques** et non un moteur topologique exhaustif. Le
noyau Totocaèdres conserve donc l'énumération indépendante des cartes, adopte
immédiatement la certification rationnelle des intersections et conserve le
scanner d'arrangements comme prochain backend géométrique complémentaire.

## Ce qui est meilleur dans les pièces jointes

- Le vérificateur rationnel de genre 3 compare exactement, pour chaque paire de
  faces, l'intersection réelle des deux polygones à l'union prescrite d'arêtes
  et de sommets. C'est nettement plus fort que le premier certificat flottant.
- Une frontière obtenue comme union de cellules bornées d'un arrangement est
  plongée par construction. Le scanner local de liens et la connexité des
  facettes actives dans chaque plan forment un filtre efficace.
- Les limites sont annoncées correctement : voisinage d'une solution connue
  pour Szilassi, cartes et symétries publiées pour le genre 3, aucun argument
  d'inexistence tiré d'un échec aléatoire.

L'archive a été exécutée sans modification fonctionnelle : le vérificateur
rationnel accepte les deux cartes de genre 3 ; le scanner complet des 100
arrangements parcourt `104857500` unions et reproduit exactement `95` succès
de genre 1. Un contrôle de 10 000 tirages symétriques par carte de genre 3 a
également produit des candidats sans croisements et sans segments parasites.

## Ce qui est moins général ou doit être renforcé

- Le moteur de genre 3 encode deux tableaux de faces et deux actions de
  symétrie. Il valide et ré-échantillonne ces cartes, mais ne peut pas découvrir
  une nouvelle carte topologique.
- Le scanner Szilassi énumère exactement les unions de cellules pour chaque
  arrangement fourni, mais les arrangements eux-mêmes viennent de
  perturbations du modèle connu. L'exhaustivité est donc locale à l'entrée.
- Le filtre flottant `extra_contact_segments` teste les intervalles ouverts,
  pas tous les points de coupure ; un contact ponctuel parasite peut lui
  échapper. Le contrôle rationnel final teste bien les deux.
- Le vérificateur rationnel joint ne vérifie pas explicitement que deux sommets
  combinatoirement distincts ont des coordonnées différentes. Cette condition
  a été ajoutée.
- Les plans parallèles ou coplanaires, les faces percées et les sommets de
  valence supérieure à trois demandent encore des branches exactes dédiées.

## Intégration retenue

1. Les cartes de contrôle sont des données externes dans
   `benchmarks/positive_controls.json`. Aucun identifiant n'est lu par le
   moteur de recherche.
2. Les automorphismes de faces sont calculés par le programme. Les sous-groupes
   `C2`, `C4` et `V4` et leurs représentations orthogonales 3D sont essayés à
   partir de la carte seule.
3. Les plans sont tirés dans les familles invariantes, les sommets sont les
   intersections des plans incidents, puis les faces simples et les
   intersections parasites sont filtrées.
4. Tout candidat retenu est rationalisé et repasse dans un vérificateur exact
   indépendant. Les coordonnées publiées ne participent jamais à la recherche.

La campagne actuelle retrouve déjà les trois contrôles par recherche de plans
à symétries déduites. L'intégration ultérieure du scanner d'unions de cellules
servira surtout aux cartes sans réalisation symétrique détectable et aux faces
percées ; elle devra recevoir des arrangements produits indépendamment d'un
modèle connu pour devenir un outil de découverte.

Cette architecture transforme les trois exemples en tests de régression : une
modification du moteur est acceptable si elle continue de les retrouver sous
un budget publié, mais aucune règle ne demande « trouver Szilassi », « trouver
Mizhaev » ou « trouver Röst-Vígh ».
