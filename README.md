# Face-Neighbourly Polyhedra Explorer

A small, static Three.js viewer for three unusual polyhedral surfaces:

1. **Szilassi polyhedron** - genus 1, 7 hexagonal faces, every pair of faces shares exactly one edge.
2. **Mizhaev 2026 realization** - genus 3, 8 nonagonal faces, exact integer coordinates.
3. **Rost-Vigh 2026 realization** - genus 3, 8 nonagonal faces, rational coordinates, combinatorially distinct from Mizhaev's example.

The site is designed to be deployed directly with GitHub Pages. It has no build step, no backend, no analytics and no runtime dependency other than a pinned Three.js ES-module import from jsDelivr.

## Features

- One-click switching among all three realizations.
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

The equivalent cross-platform command is `npm run serve`. This project has no packages to install, so `npm install` is not required.

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
