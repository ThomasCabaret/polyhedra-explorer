# Face-Neighbourly Polyhedra Explorer

A small, static Three.js viewer for unusual polyhedral surfaces. The
**[Totocaedres research project](research/totocaedres/README.md)** includes the
[LaTeX research note](research/totocaedres/docs/finite_search_bounds.tex),
[genus search programs](research/totocaedres/campaign/README.md), and
[archived results and certificates](research/totocaedres/results/README.md).

The built-in reference models are:

1. **Szilassi polyhedron** - genus 1, 7 hexagonal faces, every pair of faces shares exactly one edge.
2. **Mizhaev 2026 realization** - genus 3, 8 nonagonal faces, exact integer coordinates.
3. **Rost-Vigh 2026 realization** - genus 3, 8 nonagonal faces, rational coordinates, combinatorially distinct from Mizhaev's example.

The site is designed to be deployed directly with GitHub Pages or run fully
offline. It has no build step, backend or analytics. Three.js r186.1 and the
two control modules are vendored under `vendor/three/` with their MIT license.

## Features

- One-click switching among references and certified search realizations.
- Orbit navigation by default: rotate and zoom around a locked model center.
- Free-fly navigation with pointer lock: mouse look, `WASD`, `Q/E`, and `Shift` boost.
- Adjustable face opacity, including fully transparent faces.
- Independent face, edge and vertex visibility.
- Adjustable geometric edge thickness.
- Front, top, side and fitted camera presets.
- Optional auto-rotation.
- Click-to-inspect faces, including boundary vertices and edge-adjacency multiplicities.
- On-page mathematical metadata and links to the source papers.
- Concave polygons are triangulated in their own supporting plane with Three.js/Earcut; no naive triangle-fan approximation is used.
- A Node validation script checks the combinatorial data.

## Deploy on GitHub Pages

1. Create an empty GitHub repository, for example `polyhedra-explorer`.
2. Put the contents of this folder at the repository root and push to `main`.
3. Open **Settings -> Pages** in the GitHub repository.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select branch **main** and folder **/(root)**, then save.
6. GitHub will publish the site at a URL similar to:
   `https://YOUR-USERNAME.github.io/polyhedra-explorer/`

No configuration file or build artifact is required.

## Run locally

Because the app uses JavaScript ES modules, serve the directory over HTTP instead of opening `index.html` as a `file://` URL.

### Windows

Install the current Node.js LTS release, then double-click `serve.bat` or run:

```powershell
.\serve.bat
```

Open `http://127.0.0.1:8000/`. To use another port:

```powershell
.\serve.bat --port=8080
```

The equivalent cross-platform command is `npm run serve`. This project has no
packages to install, so `npm install` and an Internet connection are not
required.

### Python alternative

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

## Validate the model data

Node.js is only needed for this optional validation step:

```bash
npm run validate
```

On Windows, `validate.bat` runs the same check.

The validator checks vertex/edge/face counts, closed-edge incidence, Euler characteristic, genus, and complete pairwise face adjacency.

## Load Totocaedres search results

From the repository root:

```powershell
cd research/totocaedres
python -m pip install -e .
python -m totocaedres export-viewer results/validation-campaign.json results/discovery/9b4c587e1cb3c920ac499cd6.json --output ../../src/generated-models.js
```

This regenerates `src/generated-models.js` at the repository root. Generated
candidates include three geometry controls and the independently enumerated
genus 1 discovery certificate. Run `npm run validate` from the repository root
to check the generated and built-in meshes.

## Navigation

### Orbit mode

- Left drag: rotate around the model center.
- Wheel/pinch: zoom.
- Click a face: inspect its boundary and neighbours.

### Fly mode

- Enter **Fly** mode, then click the viewport if the mouse is not yet captured.
- Mouse: look around.
- `W` / `S`: forward / backward.
- `A` / `D`: left / right.
- `Q` / `E`: down / up.
- Hold `Shift`: move faster.
- `Esc`: release the mouse. Click the viewport to resume.

The camera has no collision detection, intentionally: you can pass through faces and inspect the topology from inside.

## Project structure

```text
.
├── index.html
├── README.md
├── DATA_SOURCES.md
├── LICENSE
├── package.json
├── assets/
│   └── favicon.svg
├── scripts/
│   └── validate.mjs
└── src/
    ├── app.js
    ├── geometry.js
    ├── models.js
    └── styles.css
```

## Data and references

See [`DATA_SOURCES.md`](./DATA_SOURCES.md) for paper links, coordinate provenance, and attribution details.

## License

The site code is MIT licensed. Geometry/source data have their own attribution and source-license notes; see `DATA_SOURCES.md`.
