import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";
import { MODELS, MODEL_ORDER } from "./models.js";
import {
  createPolygonGeometry,
  makeEdgeMesh,
  normalizeVertices,
  topologySummary,
  uniqueEdges
} from "./geometry.js";

const dom = {
  canvas: document.querySelector("#scene-canvas"),
  viewport: document.querySelector("#viewport"),
  panel: document.querySelector("#panel"),
  panelToggle: document.querySelector("#panel-toggle"),
  modelButtons: document.querySelector("#model-buttons"),
  modelDate: document.querySelector("#model-date"),
  modelTitle: document.querySelector("#model-title"),
  modelGenus: document.querySelector("#model-genus"),
  modelStats: document.querySelector("#model-stats"),
  modelDescription: document.querySelector("#model-description"),
  modelReference: document.querySelector("#model-reference"),
  orbitMode: document.querySelector("#orbit-mode"),
  flyMode: document.querySelector("#fly-mode"),
  fitView: document.querySelector("#fit-view"),
  frontView: document.querySelector("#front-view"),
  topView: document.querySelector("#top-view"),
  sideView: document.querySelector("#side-view"),
  autoRotate: document.querySelector("#auto-rotate"),
  flySpeed: document.querySelector("#fly-speed"),
  flySpeedValue: document.querySelector("#fly-speed-value"),
  faceOpacity: document.querySelector("#face-opacity"),
  opacityValue: document.querySelector("#opacity-value"),
  edgeThickness: document.querySelector("#edge-thickness"),
  edgeThicknessValue: document.querySelector("#edge-thickness-value"),
  showFaces: document.querySelector("#show-faces"),
  showEdges: document.querySelector("#show-edges"),
  showVertices: document.querySelector("#show-vertices"),
  selectionCard: document.querySelector("#selection-card"),
  clearSelection: document.querySelector("#clear-selection"),
  modeHint: document.querySelector("#mode-hint"),
  flyHint: document.querySelector("#fly-hint"),
  crosshair: document.querySelector("#crosshair")
};

const renderer = new THREE.WebGLRenderer({
  canvas: dom.canvas,
  antialias: true,
  alpha: true,
  powerPreference: "high-performance"
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.setClearColor(0x000000, 0);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.005, 100);
camera.position.set(2.3, 1.55, 2.55);

const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;
orbit.dampingFactor = 0.065;
orbit.rotateSpeed = 0.68;
orbit.zoomSpeed = 0.82;
orbit.enablePan = false;
orbit.minDistance = 0.18;
orbit.maxDistance = 12;
orbit.target.set(0, 0, 0);
orbit.update();

const fly = new PointerLockControls(camera, renderer.domElement);
fly.pointerSpeed = 0.8;

scene.add(new THREE.HemisphereLight(0xbddcff, 0x171b25, 1.35));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
keyLight.position.set(3, 4, 5);
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0xaab7ff, 1.15);
rimLight.position.set(-4, -1.5, -3);
scene.add(rimLight);

const state = {
  modelId: MODEL_ORDER[0],
  navMode: "orbit",
  modelRoot: null,
  facesGroup: null,
  edgesGroup: null,
  verticesGroup: null,
  faceMeshes: [],
  edgeMeshes: [],
  topology: null,
  points: [],
  selectedFace: null,
  keys: new Set(),
  pointerDown: null,
  edgeBaseRadius: 0.008,
  flySpeed: 1,
  clock: new THREE.Clock()
};

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const unitCylinder = new THREE.CylinderGeometry(1, 1, 1, 10, 1, false);
const vertexGeometry = new THREE.SphereGeometry(0.022, 16, 10);
const flyForwardVector = new THREE.Vector3();
const flyRightVector = new THREE.Vector3();

function faceColor(index, count, modelId) {
  const offsets = { szilassi: 0.03, mizhaev: 0.56, rostVigh: 0.78 };
  const color = new THREE.Color();
  color.setHSL((offsets[modelId] + index / Math.max(count, 1)) % 1, 0.58, 0.57);
  return color;
}

function disposeObject(object) {
  object.traverse((child) => {
    if (child.geometry && child.geometry !== unitCylinder && child.geometry !== vertexGeometry) {
      child.geometry.dispose();
    }
    if (child.material) {
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      for (const material of materials) material.dispose();
    }
  });
}

function clearModel() {
  clearSelection();
  if (!state.modelRoot) return;
  scene.remove(state.modelRoot);
  disposeObject(state.modelRoot);
  state.modelRoot = null;
  state.faceMeshes = [];
  state.edgeMeshes = [];
}

function buildModel(modelId) {
  clearModel();
  state.modelId = modelId;
  const model = MODELS[modelId];
  const normalized = normalizeVertices(model.vertices);
  state.points = normalized.points;
  state.topology = topologySummary(model);

  const root = new THREE.Group();
  root.name = model.title;
  const facesGroup = new THREE.Group();
  const edgesGroup = new THREE.Group();
  const verticesGroup = new THREE.Group();
  root.add(facesGroup, edgesGroup, verticesGroup);

  for (let faceIndex = 0; faceIndex < model.faces.length; faceIndex += 1) {
    const face = model.faces[faceIndex];
    const facePoints = face.map((vertexIndex) => state.points[vertexIndex]);
    const { geometry } = createPolygonGeometry(facePoints);
    const material = new THREE.MeshStandardMaterial({
      color: faceColor(faceIndex, model.faces.length, modelId),
      roughness: 0.72,
      metalness: 0.02,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: Number(dom.faceOpacity.value),
      depthWrite: Number(dom.faceOpacity.value) >= 0.98
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.faceIndex = faceIndex;
    mesh.userData.modelId = modelId;
    facesGroup.add(mesh);
    state.faceMeshes.push(mesh);
  }

  const edgeMaterial = new THREE.MeshBasicMaterial({ color: 0xe6edf7, transparent: true, opacity: 0.93 });
  for (const [a, b] of uniqueEdges(model.faces)) {
    const edgeMesh = makeEdgeMesh(state.points[a], state.points[b], unitCylinder, edgeMaterial, state.edgeBaseRadius);
    edgeMesh.userData.vertices = [a, b];
    edgesGroup.add(edgeMesh);
    state.edgeMeshes.push(edgeMesh);
  }

  const vertexMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const vertexMesh = new THREE.InstancedMesh(vertexGeometry, vertexMaterial, state.points.length);
  const matrix = new THREE.Matrix4();
  for (let i = 0; i < state.points.length; i += 1) {
    matrix.makeTranslation(state.points[i].x, state.points[i].y, state.points[i].z);
    vertexMesh.setMatrixAt(i, matrix);
  }
  vertexMesh.instanceMatrix.needsUpdate = true;
  verticesGroup.add(vertexMesh);

  state.modelRoot = root;
  state.facesGroup = facesGroup;
  state.edgesGroup = edgesGroup;
  state.verticesGroup = verticesGroup;
  scene.add(root);

  updateModelUi();
  applyAppearance();
  setCanonicalView("fit");
}

function updateModelUi() {
  const model = MODELS[state.modelId];
  const topo = state.topology;

  for (const button of dom.modelButtons.querySelectorAll("button")) {
    button.classList.toggle("active", button.dataset.modelId === state.modelId);
  }

  dom.modelDate.textContent = model.date;
  dom.modelTitle.textContent = model.title;
  dom.modelGenus.textContent = `genus ${topo.genus}`;
  dom.modelDescription.textContent = model.description;
  dom.modelReference.textContent = model.referenceLabel;
  dom.modelReference.href = model.referenceUrl;

  const stats = [
    [topo.F, "faces"],
    [topo.E, "edges"],
    [topo.V, "vertices"],
    [topo.chi, "Euler chi"]
  ];
  dom.modelStats.replaceChildren(...stats.map(([value, label]) => {
    const item = document.createElement("div");
    item.className = "stat";
    const strong = document.createElement("strong");
    strong.textContent = String(value);
    const span = document.createElement("span");
    span.textContent = label;
    item.append(strong, span);
    return item;
  }));
}

function applyAppearance() {
  const opacity = Number(dom.faceOpacity.value);
  dom.opacityValue.value = `${Math.round(opacity * 100)}%`;
  for (const mesh of state.faceMeshes) {
    mesh.material.opacity = opacity;
    mesh.material.transparent = opacity < 1;
    mesh.material.depthWrite = opacity >= 0.98;
    mesh.material.needsUpdate = true;
  }

  state.facesGroup.visible = dom.showFaces.checked;
  state.edgesGroup.visible = dom.showEdges.checked;
  state.verticesGroup.visible = dom.showVertices.checked;

  const thickness = Number(dom.edgeThickness.value);
  dom.edgeThicknessValue.value = `${thickness.toFixed(1)}x`;
  for (const edge of state.edgeMeshes) {
    const radius = state.edgeBaseRadius * thickness;
    edge.scale.x = radius;
    edge.scale.z = radius;
  }
}

function setCanonicalView(view) {
  if (state.navMode !== "orbit") setNavigationMode("orbit", false);
  const distance = 3.15;
  const positions = {
    fit: new THREE.Vector3(2.3, 1.55, 2.55).normalize().multiplyScalar(distance),
    front: new THREE.Vector3(0, 0, distance),
    top: new THREE.Vector3(0.001, distance, 0.001),
    side: new THREE.Vector3(distance, 0, 0)
  };
  camera.position.copy(positions[view] || positions.fit);
  camera.up.set(0, 1, 0);
  orbit.target.set(0, 0, 0);
  orbit.update();
}

function setNavigationMode(mode, requestLock = true) {
  state.navMode = mode;
  const isOrbit = mode === "orbit";
  orbit.enabled = isOrbit;
  dom.orbitMode.classList.toggle("active", isOrbit);
  dom.flyMode.classList.toggle("active", !isOrbit);
  dom.modeHint.classList.toggle("hidden", !isOrbit);
  dom.flyHint.classList.toggle("hidden", isOrbit);
  dom.crosshair.classList.toggle("hidden", isOrbit || !fly.isLocked);

  if (isOrbit) {
    if (fly.isLocked) fly.unlock();
    orbit.target.set(0, 0, 0);
    orbit.update();
  } else {
    dom.autoRotate.checked = false;
    orbit.autoRotate = false;
    if (requestLock && !fly.isLocked) fly.lock();
  }
}

function clearSelection() {
  if (state.selectedFace !== null && state.faceMeshes[state.selectedFace]) {
    const material = state.faceMeshes[state.selectedFace].material;
    material.emissive.setHex(0x000000);
    material.emissiveIntensity = 1;
  }
  state.selectedFace = null;
  dom.selectionCard.classList.add("empty");
  dom.selectionCard.textContent = "No face selected.";
  dom.clearSelection.disabled = true;
}

function selectFace(faceIndex) {
  clearSelection();
  const model = MODELS[state.modelId];
  const mesh = state.faceMeshes[faceIndex];
  if (!mesh) return;

  state.selectedFace = faceIndex;
  mesh.material.emissive.setHex(0x2f3b4c);
  mesh.material.emissiveIntensity = 0.9;

  const faceName = model.faceNames[faceIndex] || `Face ${faceIndex + 1}`;
  const boundary = model.faces[faceIndex].map((index) => model.vertexLabel(index)).join(" - ");
  const neighbours = state.topology.adjacency[faceIndex]
    .map((count, index) => ({ count, index }))
    .filter(({ count }) => count > 0)
    .map(({ count, index }) => `${model.faceNames[index] || `F${index + 1}`} (${count} edge${count > 1 ? "s" : ""})`)
    .join(", ");

  dom.selectionCard.classList.remove("empty");
  dom.selectionCard.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = faceName;
  const boundaryLine = document.createElement("div");
  boundaryLine.textContent = `Boundary: ${boundary}`;
  const neighbourLine = document.createElement("div");
  neighbourLine.textContent = `Adjacent to: ${neighbours}`;
  dom.selectionCard.append(heading, boundaryLine, neighbourLine);
  dom.clearSelection.disabled = false;
}

function inspectAt(clientX, clientY) {
  if (state.navMode !== "orbit" || !dom.showFaces.checked) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(state.faceMeshes, false);
  if (hits.length) selectFace(hits[0].object.userData.faceIndex);
  else clearSelection();
}

function updateFly(delta) {
  if (state.navMode !== "fly" || !fly.isLocked) return;
  const boost = state.keys.has("ShiftLeft") || state.keys.has("ShiftRight") ? 3.2 : 1;
  const distance = delta * 0.9 * state.flySpeed * boost;
  const forward = (state.keys.has("KeyW") ? 1 : 0) - (state.keys.has("KeyS") ? 1 : 0);
  const right = (state.keys.has("KeyD") ? 1 : 0) - (state.keys.has("KeyA") ? 1 : 0);
  const vertical = (state.keys.has("KeyE") ? 1 : 0) - (state.keys.has("KeyQ") ? 1 : 0);

  if (forward) {
    camera.getWorldDirection(flyForwardVector);
    camera.position.addScaledVector(flyForwardVector, forward * distance);
  }
  if (right) {
    flyRightVector.set(1, 0, 0).applyQuaternion(camera.quaternion).normalize();
    camera.position.addScaledVector(flyRightVector, right * distance);
  }
  if (vertical) camera.position.y += vertical * distance;
}

function resize() {
  const width = dom.viewport.clientWidth;
  const height = dom.viewport.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
}

function animate() {
  const delta = Math.min(state.clock.getDelta(), 0.05);
  if (state.navMode === "orbit") {
    orbit.autoRotate = dom.autoRotate.checked;
    orbit.autoRotateSpeed = 0.75;
    orbit.update(delta);
  } else {
    updateFly(delta);
  }
  renderer.render(scene, camera);
}

function buildModelButtons() {
  for (const id of MODEL_ORDER) {
    const model = MODELS[id];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "model-button";
    button.dataset.modelId = id;
    const name = document.createElement("span");
    name.textContent = model.shortName;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `g=${model.expected.genus}, F=${model.expected.faces}`;
    button.append(name, meta);
    button.addEventListener("click", () => buildModel(id));
    dom.modelButtons.append(button);
  }
}

function wireUi() {
  dom.panelToggle.addEventListener("click", () => dom.panel.classList.toggle("collapsed"));
  dom.orbitMode.addEventListener("click", () => setNavigationMode("orbit"));
  dom.flyMode.addEventListener("click", () => setNavigationMode("fly"));
  dom.fitView.addEventListener("click", () => setCanonicalView("fit"));
  dom.frontView.addEventListener("click", () => setCanonicalView("front"));
  dom.topView.addEventListener("click", () => setCanonicalView("top"));
  dom.sideView.addEventListener("click", () => setCanonicalView("side"));

  dom.faceOpacity.addEventListener("input", applyAppearance);
  dom.edgeThickness.addEventListener("input", applyAppearance);
  dom.showFaces.addEventListener("change", applyAppearance);
  dom.showEdges.addEventListener("change", applyAppearance);
  dom.showVertices.addEventListener("change", applyAppearance);
  dom.clearSelection.addEventListener("click", clearSelection);

  dom.flySpeed.addEventListener("input", () => {
    state.flySpeed = Number(dom.flySpeed.value);
    dom.flySpeedValue.value = `${state.flySpeed.toFixed(2).replace(/\.00$/, ".0")}x`;
  });

  fly.addEventListener("lock", () => {
    dom.crosshair.classList.toggle("hidden", state.navMode !== "fly");
    dom.flyHint.textContent = "Fly active: WASD move, Q/E down/up, Shift boosts, Esc releases the mouse.";
  });
  fly.addEventListener("unlock", () => {
    dom.crosshair.classList.add("hidden");
    if (state.navMode === "fly") {
      dom.flyHint.textContent = "Fly paused: click the 3D view to recapture the mouse. WASD move, Q/E down/up.";
    }
  });

  renderer.domElement.addEventListener("click", () => {
    if (state.navMode === "fly" && !fly.isLocked) fly.lock();
  });

  renderer.domElement.addEventListener("pointerdown", (event) => {
    state.pointerDown = { x: event.clientX, y: event.clientY, button: event.button };
  });
  renderer.domElement.addEventListener("pointerup", (event) => {
    if (!state.pointerDown || state.pointerDown.button !== 0 || event.button !== 0) return;
    const distance = Math.hypot(event.clientX - state.pointerDown.x, event.clientY - state.pointerDown.y);
    if (distance < 5) inspectAt(event.clientX, event.clientY);
    state.pointerDown = null;
  });

  window.addEventListener("keydown", (event) => {
    if (["KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "ShiftLeft", "ShiftRight"].includes(event.code)) {
      state.keys.add(event.code);
      if (state.navMode === "fly") event.preventDefault();
    }
  });
  window.addEventListener("keyup", (event) => state.keys.delete(event.code));
  window.addEventListener("blur", () => state.keys.clear());
  window.addEventListener("resize", resize);
}

buildModelButtons();
wireUi();
resize();
buildModel(MODEL_ORDER[0]);
renderer.setAnimationLoop(animate);
