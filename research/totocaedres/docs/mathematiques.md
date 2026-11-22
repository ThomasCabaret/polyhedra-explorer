# Modèle mathématique et domaine de complétude

## 1. Objet

On cherche la frontière `S` d'un compact connexe de `R³`, d'intérieur non
vide. `S` est une surface polyédrique fermée, connexe, orientable, plongée et
sans bord. Elle est découpée en `F` faces planes connexes. Une face est une
surface planaire de genre zéro avec un contour extérieur et `h_i >= 0`
contours intérieurs disjoints. Deux morceaux coplanaires adjacents qui forment
une même région planaire connexe doivent être fusionnés.

Le graphe de subdivision possède `V` sommets et `E` arêtes. Chaque arête a deux
faces distinctes incidentes. Les ordres cycliques autour des sommets doivent
donner un voisinage en disque. Après suppression des sommets artificiels de
degré deux, tous les sommets ont degré au moins trois.

Pour deux faces `i != j` :

- `s_ij` est le nombre de composantes connexes du sous-graphe formé par leurs
  arêtes communes de longueur positive ;
- `p_ij` est le nombre de sommets où elles se rencontrent sans qu'une arête
  `ij` soit incidente à ce sommet.

Le problème principal impose `s_ij >= 1`. La variante ponctuelle impose
`s_ij + p_ij >= 1` et doit être publiée séparément.

## 2. Représentation par brins

Une carte est décrite par un ensemble de brins `D`, une involution sans point
fixe `alpha` qui apparie les deux côtés de chaque arête, et une permutation
`rho` dont les cycles sont les contours orientés des faces. Plusieurs cycles de
`rho` peuvent porter la même étiquette de face : si la face `i` en porte
`b_i`, alors `h_i=b_i-1`. La permutation

`phi = rho o alpha`

a pour cycles les sommets primaux. Cette représentation encode directement
les ordres cycliques et rend testables la variété locale, les pincements et les
contacts ponctuels. Elle ne suppose pas qu'une face trouée soit une cellule
disque.

## 3. Identités vérifiées

Posons `H = sum h_i`. La caractéristique d'Euler d'une face planaire trouée
est `1-h_i`. L'additivité donne

`V - E + F - H = 2 - 2g`.                                      (1)

Posons ensuite

`D = sum_v (deg(v)-3)`

et, dans le problème principal,

`M = E - F(F-1)/2`.

Comme `sum deg(v)=2E`, on a `3V + D = 2E`. En éliminant `V` entre cette égalité
et (1), puis en remplaçant `E` par `F(F-1)/2+M`, on obtient

`12g = (F-3)(F-4) + 2M + 2D + 6H`.                             (2)

La formule du document source est donc correcte sous ses hypothèses : surface
fermée orientable, subdivision régulière, sommets de degré deux supprimés et
au moins une arête par paire de faces. Elle est seulement nécessaire. En
particulier elle ne contrôle ni la planéité des faces, ni le plongement dans
`R³`, ni l'absence de fusion coplanaire.

Conséquences utiles : `M,D,H >= 0` bornent `F` à genre fixé ; pour
`M=D=H=0`, `g=(F-3)(F-4)/12`. Les seuls premiers cas intégraux sont
`F=4,g=0` et `F=7,g=1`. Ils correspondent aux plongements triangulaires
orientables du graphe dual complet.

Le planificateur applique aussi les conditions élémentaires `V >= 3` et
`D <= (F-3)V`. La seconde vient de `deg(v) <= F` : une même face ne peut pas
occuper deux secteurs autour d'un sommet sans pincement de son domaine.

## 4. Exhaustivité et symétries

Pour le cas trivalent simple, chaque sommet primal est un triangle orienté du
graphe dual `K_F`. L'énumérateur résout une couverture exacte : chaque arc
orienté de `K_F` doit appartenir à exactement un triangle orienté. Les
successeurs ainsi imposés autour de chaque sommet dual doivent former un seul
cycle. Une face orientée est fixée à `(0,1,2)` ; toute carte non étiquetée peut
être enracinée ainsi, donc ce bris de symétrie ne perd aucune classe
d'isomorphisme. Les résultats sont ensuite canonisés sous toutes les
permutations des `F` faces et sous renversement global de l'orientation.

Le générateur générique énumère les permutations de contours pour un
multigraphe dual fixé. Il est exhaustif pour les paramètres fournis, mais son
coût est factoriel. Les commandes doivent donc annoncer : `g`, `F`, `H`, la
matrice de multiplicités ou `M`, la longueur minimale des contours, le nombre
maximal de cartes visitées et la règle de quotient par symétrie.

## 5. Réalisation géométrique

Le solveur associe des coordonnées `x_v` aux sommets et une équation
`n_i.x+c_i=0` à chaque face. Il minimise les résidus d'incidence, normalise les
normales, fixe translation et échelle, et pénalise les arêtes trop courtes et
les sommets confondus. Les contraintes combinatoires (arêtes et contacts) ne
sont jamais redécouvertes numériquement : elles viennent de la carte validée.

Le vérificateur est séparé du solveur. Il recalcule les plans par SVD,
triangule les contours simples, mesure les marges de planéité, de longueur et
de séparation, calcule le volume signé et cherche les intersections entre
triangles topologiquement disjoints. Un succès de la version 0.2 est un
**certificat numérique reproductible**, pas encore une preuve exacte. Une
preuve publiable demandera ensuite des coordonnées rationnelles ou
algébriques, des intervalles certifiés et un test exhaustif des intersections,
y compris pour les faces trouées.

## 6. Ordre de recherche recommandé

1. contrôles `g=0,F=4` et `g=1,F=7`, `M=D=H=0` ;
2. à genre fixé, augmenter séparément `M`, puis `D`, puis `H` selon (2) ;
3. lancer la variante ponctuelle dans une campagne distincte ;
4. ne transmettre au solveur 3D que les cartes ayant passé tous les filtres
   topologiques ;
5. archiver pour chaque campagne les bornes, le nombre d'états visités, les
   signatures canoniques et le certificat géométrique.
