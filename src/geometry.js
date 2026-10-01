import * as THREE from "three";

export function normalizeVertices(rawVertices) {
  const points = rawVertices.map(([x, y, z]) => new THREE.Vector3(x, y, z));
  const box = new THREE.Box3().setFromPoints(points);
  const center = box.getCenter(new THREE.Vector3());

  for (const point of points) point.sub(center);

  let radius = 0;
  for (const point of points) radius = Math.max(radius, point.length());
  const scale = radius > 0 ? 1 / radius : 1;
  for (const point of points) point.multiplyScalar(scale);

  return { points, sourceCenter: center, sourceScale: scale };
}

export function computeFaceNormal(points) {
  const normal = new THREE.Vector3();
  for (let i = 0; i < points.length; i += 1) {
    const current = points[i];
    const next = points[(i + 1) % points.length];
    normal.x += (current.y - next.y) * (current.z + next.z);
    normal.y += (current.z - next.z) * (current.x + next.x);
    normal.z += (current.x - next.x) * (current.y + next.y);
  }
  if (normal.lengthSq() < 1e-20) {
    normal.crossVectors(
      new THREE.Vector3().subVectors(points[1], points[0]),
      new THREE.Vector3().subVectors(points[2], points[0])
    );
  }
  return normal.normalize();
}

export function createPolygonGeometry(points) {
  const centroid = points.reduce((sum, point) => sum.add(point), new THREE.Vector3()).multiplyScalar(1 / points.length);
  const normal = computeFaceNormal(points);

  const reference = Math.abs(normal.z) < 0.9
    ? new THREE.Vector3(0, 0, 1)
    : new THREE.Vector3(0, 1, 0);
  const axisU = new THREE.Vector3().crossVectors(reference, normal).normalize();
  const axisV = new THREE.Vector3().crossVectors(normal, axisU).normalize();

  const projected = points.map((point) => {
    const relative = new THREE.Vector3().subVectors(point, centroid);
    return new THREE.Vector2(relative.dot(axisU), relative.dot(axisV));
  });

  const triangles = THREE.ShapeUtils.triangulateShape(projected, []);
  const positions = [];

  for (const triangle of triangles) {
    for (const index of triangle) {
      const point = points[index];
      positions.push(point.x, point.y, point.z);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();

  return { geometry, normal, centroid, triangleCount: triangles.length };
}

export function uniqueEdges(faces) {
  const map = new Map();
  for (const face of faces) {
    for (let i = 0; i < face.length; i += 1) {
      const a = face[i];
      const b = face[(i + 1) % face.length];
      const key = a < b ? `${a}:${b}` : `${b}:${a}`;
      if (!map.has(key)) map.set(key, a < b ? [a, b] : [b, a]);
    }
  }
  return [...map.values()];
}

export function topologySummary(model) {
  const edgeCounts = new Map();
  for (const face of model.faces) {
    for (let i = 0; i < face.length; i += 1) {
      const a = face[i];
      const b = face[(i + 1) % face.length];
      const key = a < b ? `${a}:${b}` : `${b}:${a}`;
      edgeCounts.set(key, (edgeCounts.get(key) || 0) + 1);
    }
  }

  const V = model.vertices.length;
  const E = edgeCounts.size;
  const F = model.faces.length;
  const chi = V - E + F;
  const genus = (2 - chi) / 2;

  const adjacency = Array.from({ length: F }, () => Array(F).fill(0));
  for (const [edgeKey] of edgeCounts) {
    const [a, b] = edgeKey.split(":").map(Number);
    const incident = [];
    for (let i = 0; i < F; i += 1) {
      const face = model.faces[i];
      for (let j = 0; j < face.length; j += 1) {
        const x = face[j];
        const y = face[(j + 1) % face.length];
        if ((x === a && y === b) || (x === b && y === a)) {
          incident.push(i);
          break;
        }
      }
    }
    if (incident.length === 2) {
      adjacency[incident[0]][incident[1]] += 1;
      adjacency[incident[1]][incident[0]] += 1;
    }
  }

  let singlePairs = 0;
  let doublePairs = 0;
  let missingPairs = 0;
  for (let i = 0; i < F; i += 1) {
    for (let j = i + 1; j < F; j += 1) {
      if (adjacency[i][j] === 1) singlePairs += 1;
      else if (adjacency[i][j] === 2) doublePairs += 1;
      else if (adjacency[i][j] === 0) missingPairs += 1;
    }
  }

  return { V, E, F, chi, genus, edgeCounts, adjacency, singlePairs, doublePairs, missingPairs };
}

export function makeEdgeMesh(start, end, geometry, material, radius) {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();
  const midpoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(midpoint);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
  mesh.scale.set(radius, length, radius);
  mesh.userData.edgeRadius = radius;
  return mesh;
}
