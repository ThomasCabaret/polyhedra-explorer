import { MODELS, MODEL_ORDER } from "../src/models.js";

function edgeKey(a, b) {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

function sub(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  ];
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function norm(a) {
  return Math.hypot(a[0], a[1], a[2]);
}

function facePlane(vertices, face) {
  const origin = vertices[face[0]];
  for (let i = 1; i < face.length - 1; i += 1) {
    const a = sub(vertices[face[i]], origin);
    const b = sub(vertices[face[i + 1]], origin);
    const normal = cross(a, b);
    const length = norm(normal);
    if (length > 1e-12) return { origin, normal: normal.map((x) => x / length) };
  }
  return null;
}

function projectFace(vertices, face, normal) {
  const ax = Math.abs(normal[0]);
  const ay = Math.abs(normal[1]);
  const az = Math.abs(normal[2]);
  if (ax >= ay && ax >= az) return face.map((i) => [vertices[i][1], vertices[i][2]]);
  if (ay >= az) return face.map((i) => [vertices[i][0], vertices[i][2]]);
  return face.map((i) => [vertices[i][0], vertices[i][1]]);
}

function orient(a, b, c) {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

function segmentsProperlyIntersect(a, b, c, d, eps = 1e-10) {
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);
  return ((o1 > eps && o2 < -eps) || (o1 < -eps && o2 > eps)) &&
    ((o3 > eps && o4 < -eps) || (o3 < -eps && o4 > eps));
}

function polygonIsSimple(points) {
  const n = points.length;
  for (let i = 0; i < n; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % n];
    for (let j = i + 1; j < n; j += 1) {
      if (j === i || j === (i + 1) % n || (j + 1) % n === i) continue;
      if (i === 0 && j === n - 1) continue;
      const c = points[j];
      const d = points[(j + 1) % n];
      if (segmentsProperlyIntersect(a, b, c, d)) return false;
    }
  }
  return true;
}

function validate(model) {
  const errors = [];
  const edgeCounts = new Map();

  for (const [faceIndex, face] of model.faces.entries()) {
    if (face.length < 3) errors.push(`Face ${faceIndex} has fewer than 3 vertices.`);
    for (const index of face) {
      if (!Number.isInteger(index) || index < 0 || index >= model.vertices.length) {
        errors.push(`Face ${faceIndex} references invalid vertex ${index}.`);
      }
    }

    const plane = facePlane(model.vertices, face);
    if (!plane) {
      errors.push(`Face ${faceIndex} is degenerate.`);
    } else {
      let scale = 1;
      let maxDistance = 0;
      for (const index of face) {
        const relative = sub(model.vertices[index], plane.origin);
        scale = Math.max(scale, norm(relative));
        maxDistance = Math.max(maxDistance, Math.abs(dot(relative, plane.normal)));
      }
      if (maxDistance > scale * 1e-9) {
        errors.push(`Face ${faceIndex} is not planar within tolerance: ${maxDistance}.`);
      }
      const projected = projectFace(model.vertices, face, plane.normal);
      if (!polygonIsSimple(projected)) errors.push(`Face ${faceIndex} is self-intersecting in projection.`);
    }

    for (let i = 0; i < face.length; i += 1) {
      const key = edgeKey(face[i], face[(i + 1) % face.length]);
      edgeCounts.set(key, (edgeCounts.get(key) || 0) + 1);
    }
  }

  for (const [edge, count] of edgeCounts.entries()) {
    if (count !== 2) errors.push(`Edge ${edge} occurs ${count} times instead of 2.`);
  }

  const V = model.vertices.length;
  const E = edgeCounts.size;
  const F = model.faces.length;
  const chi = V - E + F;
  const genus = (2 - chi) / 2;

  for (const [key, actual] of Object.entries({ vertices: V, edges: E, faces: F, genus })) {
    if (actual !== model.expected[key]) {
      errors.push(`${key}: expected ${model.expected[key]}, got ${actual}.`);
    }
  }

  const pairCounts = new Map();
  const edgeFaces = new Map();
  for (let faceIndex = 0; faceIndex < model.faces.length; faceIndex += 1) {
    const face = model.faces[faceIndex];
    for (let i = 0; i < face.length; i += 1) {
      const key = edgeKey(face[i], face[(i + 1) % face.length]);
      if (!edgeFaces.has(key)) edgeFaces.set(key, []);
      edgeFaces.get(key).push(faceIndex);
    }
  }
  for (const incidentFaces of edgeFaces.values()) {
    if (incidentFaces.length !== 2) continue;
    const key = edgeKey(incidentFaces[0], incidentFaces[1]);
    pairCounts.set(key, (pairCounts.get(key) || 0) + 1);
  }

  let missingPairs = 0;
  let singlePairs = 0;
  let doublePairs = 0;
  for (let i = 0; i < F; i += 1) {
    for (let j = i + 1; j < F; j += 1) {
      const count = pairCounts.get(edgeKey(i, j)) || 0;
      if (count === 0) missingPairs += 1;
      else if (count === 1) singlePairs += 1;
      else if (count === 2) doublePairs += 1;
      else errors.push(`Faces ${i} and ${j} share ${count} edges; expected at most 2.`);
    }
  }
  if (missingPairs !== 0) errors.push(`${missingPairs} face pair(s) are not edge-adjacent.`);

  return { V, E, F, chi, genus, singlePairs, doublePairs, errors };
}

let failed = false;
for (const id of MODEL_ORDER) {
  const model = MODELS[id];
  const result = validate(model);
  const status = result.errors.length ? "FAIL" : "OK";
  console.log(
    `${status} ${model.shortName}: V=${result.V}, E=${result.E}, F=${result.F}, ` +
    `chi=${result.chi}, genus=${result.genus}, single=${result.singlePairs}, double=${result.doublePairs}`
  );
  for (const error of result.errors) console.error(`  - ${error}`);
  failed ||= result.errors.length > 0;
}

if (failed) process.exit(1);
