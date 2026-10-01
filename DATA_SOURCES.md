# Geometry data sources and attribution

This viewer intentionally stores the published vertex coordinates and face-boundary data as readable JavaScript arrays. That makes the visualization auditable and keeps the rendered surfaces tied to explicit mathematical data rather than opaque mesh exports.

## Szilassi polyhedron

- Lajos Szilassi, *Regular Toroids*, Structural Topology 13 (1986), pp. 69-80. The polyhedron was discovered in 1977.
  - https://upcommons.upc.edu/handle/2099/573
- The coordinate realization used by this viewer is derived from the Python source published with **Szilassi polyhedron.stl** by Wikimedia Commons user Cmglee.
  - https://commons.wikimedia.org/wiki/File:Szilassi_polyhedron.stl
  - Source license: CC BY-SA 4.0.
- The two hexagons that the Wikimedia STL source stores as pairs of coplanar quadrilaterals are represented here by their six-vertex boundary cycles. This preserves the same surface while allowing the browser to triangulate each complete polygon.

## Mizhaev genus-3 octahedron

- Ruslan Mizhaev, *Integer Realization of an Equivelar Octahedron of Genus 3*, arXiv:2609.17700, submitted 15 September 2026.
  - https://arxiv.org/abs/2609.17700
  - HTML with Tables 1-2: https://arxiv.org/html/2609.17700v1
- The viewer transcribes the 24 integer vertex coordinates and the eight cyclic nonagonal face walks from the paper's coordinate certificate.

## Rost-Vigh genus-3 polyhedron

- Gergely Rost and Viktor Vigh, *A second eight-faced polyhedron in which every two faces share an edge*, arXiv:2609.32998, submitted 26 September 2026.
  - https://arxiv.org/abs/2609.32998
  - HTML with Tables 1-2: https://arxiv.org/html/2609.32998
- The viewer transcribes the 24 rational vertex coordinates and eight nonagonal boundary cycles reported in the paper.
- The arXiv paper is marked CC BY-NC-ND 4.0. This repository does not relicense the paper or its prose/figures; the source is cited here for the mathematical coordinate and incidence data used by the independent visualization.

## Software

- Three.js r186.1, MIT License.
  - https://threejs.org/
  - https://www.npmjs.com/package/three/v/0.186.1

## Repository licensing note

The JavaScript, HTML, CSS and validation code in this repository are released under the MIT License in `LICENSE`. Geometry/source data retain the attribution and source-license notices above. In particular, the Szilassi coordinate realization derived from the Wikimedia source remains subject to CC BY-SA 4.0.
