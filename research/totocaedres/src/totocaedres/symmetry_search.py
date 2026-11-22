from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, permutations
from typing import Iterator, Sequence

import numpy as np
from numpy.typing import NDArray

from .exact_geometry import ExactGeometryCertificate, certify_rational_planes
from .geometry import GeometryCertificate, certify_geometry
from .model import SurfaceMap


Permutation = tuple[int, ...]
Matrix = tuple[tuple[float, float, float], ...]


def _compose(left: Permutation, right: Permutation) -> Permutation:
    return tuple(left[right[index]] for index in range(len(left)))


def _power(permutation: Permutation, exponent: int) -> Permutation:
    result = tuple(range(len(permutation)))
    for _ in range(exponent):
        result = _compose(permutation, result)
    return result


def _order(permutation: Permutation) -> int:
    identity = tuple(range(len(permutation)))
    value = identity
    for exponent in range(1, 65):
        value = _compose(permutation, value)
        if value == identity:
            return exponent
    raise ValueError("permutation order exceeds supported bound")


def _vertex_face_labels(surface: SurfaceMap) -> tuple[tuple[int, ...], ...]:
    dart_faces = surface.dart_faces
    return tuple(
        tuple(sorted({dart_faces[dart] for dart in cycle})) for cycle in surface.vertices
    )


def _normalise_label_cycle(cycle: Sequence[tuple[int, ...]]) -> tuple[tuple[int, ...], ...]:
    values = tuple(cycle)
    return min(values[index:] + values[:index] for index in range(len(values)))


def _mapped_boundary_signature(
    surface: SurfaceMap, permutation: Permutation, reverse: bool
) -> tuple[tuple[tuple[tuple[int, ...], ...], ...], ...]:
    vertex_labels = _vertex_face_labels(surface)
    by_target_face: list[tuple[tuple[tuple[int, ...], ...], ...] | None] = [
        None
    ] * surface.face_count
    for source_face, components in enumerate(surface.face_vertex_boundaries):
        mapped_components: list[tuple[tuple[int, ...], ...]] = []
        for component in components:
            labels = [
                tuple(sorted(permutation[face] for face in vertex_labels[vertex]))
                for vertex in component
            ]
            if reverse:
                labels.reverse()
            mapped_components.append(_normalise_label_cycle(labels))
        by_target_face[permutation[source_face]] = tuple(sorted(mapped_components))
    assert all(value is not None for value in by_target_face)
    return tuple(by_target_face)  # type: ignore[arg-type,return-value]


@lru_cache(maxsize=128)
def face_automorphisms(surface: SurfaceMap, *, max_faces: int = 9) -> tuple[Permutation, ...]:
    """Exact brute-force automorphisms of the face/vertex incidence structure."""
    face_count = surface.face_count
    if face_count > max_faces:
        raise ValueError(f"face automorphism search is capped at F={max_faces}")
    identity = tuple(range(face_count))
    target = _mapped_boundary_signature(surface, identity, False)
    automorphisms: list[Permutation] = []
    for permutation in permutations(range(face_count)):
        candidate = tuple(permutation)
        if (
            _mapped_boundary_signature(surface, candidate, False) == target
            or _mapped_boundary_signature(surface, candidate, True) == target
        ):
            automorphisms.append(tuple(permutation))
    return tuple(automorphisms)


@dataclass(frozen=True)
class SymmetryAction:
    kind: str
    elements: tuple[tuple[Permutation, Matrix], ...]
    face_orbits: tuple[tuple[int, ...], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "group_order": len(self.elements),
            "face_orbits": [list(orbit) for orbit in self.face_orbits],
            "permutations": [list(permutation) for permutation, _ in self.elements],
        }


def _matrix_power(matrix: NDArray[np.float64], exponent: int) -> Matrix:
    value = np.linalg.matrix_power(matrix, exponent)
    return tuple(tuple(float(x) for x in row) for row in value)


def _orbits(group: Sequence[Permutation], face_count: int) -> tuple[tuple[int, ...], ...]:
    unseen = set(range(face_count))
    result: list[tuple[int, ...]] = []
    while unseen:
        root = min(unseen)
        orbit = tuple(sorted({permutation[root] for permutation in group}))
        result.append(orbit)
        unseen.difference_update(orbit)
    return tuple(result)


def discover_symmetry_actions(
    surface: SurfaceMap,
    *,
    include_c2: bool = True,
    include_c4: bool = True,
    include_v4: bool = True,
    max_actions: int = 64,
) -> tuple[SymmetryAction, ...]:
    """Derive standard 3D C4/V4 actions from map automorphisms.

    No face labels or benchmark names are special-cased.  These two small
    groups are the first general library because they have real 3D orthogonal
    representations and occur frequently in low-complexity maps.
    """
    automorphisms = face_automorphisms(surface)
    identity = tuple(range(surface.face_count))
    actions: list[SymmetryAction] = []
    seen: set[tuple[str, frozenset[Permutation]]] = set()
    if include_c2:
        representations = (
            ("C2-half-turn", np.diag((-1.0, -1.0, 1.0))),
            ("C2-reflection", np.diag((-1.0, 1.0, 1.0))),
            ("C2-inversion", -np.eye(3)),
        )
        for generator in automorphisms:
            if generator == identity or _order(generator) != 2:
                continue
            subgroup = frozenset((identity, generator))
            for kind, matrix in representations:
                key = (kind, subgroup)
                if key in seen:
                    continue
                seen.add(key)
                actions.append(
                    SymmetryAction(
                        kind,
                        (
                            (identity, _matrix_power(matrix, 0)),
                            (generator, _matrix_power(matrix, 1)),
                        ),
                        _orbits((identity, generator), surface.face_count),
                    )
                )
    if include_c4:
        proper = np.asarray(((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
        improper = np.asarray(((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0)))
        for generator in automorphisms:
            if _order(generator) != 4:
                continue
            powers = tuple(_power(generator, exponent) for exponent in range(4))
            subgroup = frozenset(powers)
            for kind, matrix in (("C4-proper", proper), ("C4-improper", improper)):
                key = (kind, subgroup)
                if key in seen:
                    continue
                seen.add(key)
                actions.append(
                    SymmetryAction(
                        kind,
                        tuple(
                            (permutation, _matrix_power(matrix, exponent))
                            for exponent, permutation in enumerate(powers)
                        ),
                        _orbits(powers, surface.face_count),
                    )
                )
    if include_v4:
        involutions = [p for p in automorphisms if p != identity and _order(p) == 2]
        rz = np.diag((-1.0, -1.0, 1.0))
        rx = np.diag((1.0, -1.0, -1.0))
        ry = np.diag((-1.0, 1.0, -1.0))
        matrix_by_index = (
            np.eye(3),
            rz,
            rx,
            ry,
        )
        for first, second in combinations(involutions, 2):
            product = _compose(first, second)
            if product == identity or _compose(second, first) != product:
                continue
            permutations4 = (identity, first, second, product)
            subgroup = frozenset(permutations4)
            key = ("V4", subgroup)
            if key in seen:
                continue
            seen.add(key)
            actions.append(
                SymmetryAction(
                    "V4",
                    tuple(
                        (
                            permutation,
                            tuple(tuple(float(x) for x in row) for row in matrix),
                        )
                        for permutation, matrix in zip(permutations4, matrix_by_index)
                    ),
                    _orbits(permutations4, surface.face_count),
                )
            )
    actions.sort(key=lambda action: (len(action.face_orbits), action.kind, action.face_orbits))
    return tuple(actions[:max_actions])


def _sample_action_planes(
    action: SymmetryAction, rng: np.random.Generator
) -> NDArray[np.float64] | None:
    face_count = len(action.elements[0][0])
    planes = np.full((face_count, 4), np.nan)
    for orbit in action.face_orbits:
        root = orbit[0]
        stabilizers = [
            np.asarray(matrix)
            for permutation, matrix in action.elements
            if permutation[root] == root
        ]
        normal: NDArray[np.float64] | None = None
        for _ in range(16):
            trial = rng.normal(size=3)
            projected = sum((matrix @ trial for matrix in stabilizers), np.zeros(3))
            size = float(np.linalg.norm(projected))
            if size > 1e-8:
                normal = projected / size
                break
        if normal is None:
            return None
        offset = float(rng.uniform(-1.0, 1.0))
        for permutation, matrix in action.elements:
            face = permutation[root]
            transformed = np.asarray(matrix) @ normal
            if np.isfinite(planes[face, 0]) and np.linalg.norm(planes[face, :3] - transformed) > 1e-7:
                return None
            planes[face, :3] = transformed
            planes[face, 3] = offset
    return planes if np.isfinite(planes).all() else None


def _sample_cold_planes(face_count: int, rng: np.random.Generator) -> NDArray[np.float64]:
    normals = rng.normal(size=(face_count, 3))
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    return np.column_stack((normals, rng.uniform(-1.0, 1.0, size=face_count)))


def _vertex_triples(surface: SurfaceMap) -> tuple[tuple[int, ...], ...]:
    dart_faces = surface.dart_faces
    return tuple(tuple(sorted({dart_faces[dart] for dart in cycle})) for cycle in surface.vertices)


def _coordinates_from_planes(
    triples: Sequence[Sequence[int]], planes: NDArray[np.float64]
) -> NDArray[np.float64] | None:
    if any(len(triple) < 3 for triple in triples):
        return None
    matrices = np.asarray([[planes[face, :3] for face in triple[:3]] for triple in triples])
    offsets = np.asarray([[planes[face, 3] for face in triple[:3]] for triple in triples])
    determinants = np.linalg.det(matrices)
    if np.min(np.abs(determinants)) < 1e-7:
        return None
    coordinates = np.linalg.solve(matrices, offsets[..., None])[..., 0]
    if not np.isfinite(coordinates).all() or np.max(np.abs(coordinates)) > 1e7:
        return None
    for vertex, triple in enumerate(triples):
        if any(
            abs(float(planes[face, :3] @ coordinates[vertex] - planes[face, 3])) > 1e-7
            for face in triple[3:]
        ):
            return None
    return coordinates


def _orient2(a: NDArray[np.float64], b: NDArray[np.float64], c: NDArray[np.float64]) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _on_segment2(
    point: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64], eps: float
) -> bool:
    return abs(_orient2(a, b, point)) <= eps and bool(
        np.all(point >= np.minimum(a, b) - eps) and np.all(point <= np.maximum(a, b) + eps)
    )


def _segments_intersect2(
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    eps: float = 1e-10,
) -> bool:
    values = (_orient2(a, b, c), _orient2(a, b, d), _orient2(c, d, a), _orient2(c, d, b))
    if values[0] * values[1] < -eps and values[2] * values[3] < -eps:
        return True
    return any(
        abs(value) <= eps and _on_segment2(point, start, end, eps)
        for value, point, start, end in (
            (values[0], c, a, b),
            (values[1], d, a, b),
            (values[2], a, c, d),
            (values[3], b, c, d),
        )
    )


def _all_faces_simple(
    surface: SurfaceMap, planes: NDArray[np.float64], coordinates: NDArray[np.float64]
) -> bool:
    if any(len(parts) != 1 for parts in surface.face_vertex_boundaries):
        return False
    for face, parts in enumerate(surface.face_vertex_boundaries):
        boundary = parts[0]
        discarded = int(np.argmax(np.abs(planes[face, :3])))
        polygon = coordinates[list(boundary)][:, [k for k in range(3) if k != discarded]]
        area2 = sum(
            polygon[i, 0] * polygon[(i + 1) % len(polygon), 1]
            - polygon[i, 1] * polygon[(i + 1) % len(polygon), 0]
            for i in range(len(polygon))
        )
        if abs(float(area2)) < 1e-9:
            return False
        for i in range(len(polygon)):
            for j in range(i + 2, len(polygon)):
                if i == 0 and j == len(polygon) - 1:
                    continue
                if _segments_intersect2(
                    polygon[i],
                    polygon[(i + 1) % len(polygon)],
                    polygon[j],
                    polygon[(j + 1) % len(polygon)],
                ):
                    return False
    return True


@dataclass(frozen=True)
class PlaneSearchCandidate:
    action: dict[str, object] | None
    floating_planes: tuple[tuple[float, float, float, float], ...]
    rational_planes: tuple[tuple[str, str, str, str], ...]
    numerical_certificate: GeometryCertificate
    exact_certificate: ExactGeometryCertificate

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["numerical_certificate"] = self.numerical_certificate.to_dict()
        result["exact_certificate"] = self.exact_certificate.to_dict()
        return result


@dataclass
class PlaneSearchStats:
    actions_considered: int = 0
    trials: int = 0
    nonsingular: int = 0
    all_faces_simple: int = 0
    numerically_valid: int = 0
    exactly_valid: int = 0


def search_planes(
    surface: SurfaceMap,
    *,
    trials_per_action: int = 10_000,
    seed: int = 0,
    use_symmetry: bool = True,
    include_cold: bool = False,
    max_actions: int = 64,
    max_denominator: int = 1_000,
    stop_after: int = 1,
    stats: PlaneSearchStats | None = None,
) -> tuple[PlaneSearchCandidate, ...]:
    """Search plane realizations from the map alone.

    Symmetries are discovered from incidence automorphisms and matched to a
    small, map-independent library of orthogonal group representations.
    Published coordinates and benchmark ids are never consulted.
    """
    if trials_per_action < 1 or stop_after < 1:
        raise ValueError("trial and result budgets must be positive")
    report = surface.report()
    if not report.valid:
        raise ValueError(f"invalid map: {report.errors}")
    if any(len(triple) != 3 for triple in _vertex_triples(surface)):
        raise ValueError("the current plane search requires trivalent vertices")
    stats = stats if stats is not None else PlaneSearchStats()
    rng = np.random.default_rng(seed)
    actions: list[SymmetryAction | None] = []
    if use_symmetry:
        actions.extend(discover_symmetry_actions(surface, max_actions=max_actions))
    if include_cold or not actions:
        actions.append(None)
    triples = _vertex_triples(surface)
    candidates: list[PlaneSearchCandidate] = []
    for action in actions:
        stats.actions_considered += 1
        for _ in range(trials_per_action):
            stats.trials += 1
            planes = (
                _sample_cold_planes(surface.face_count, rng)
                if action is None
                else _sample_action_planes(action, rng)
            )
            if planes is None:
                continue
            coordinates = _coordinates_from_planes(triples, planes)
            if coordinates is None:
                continue
            stats.nonsingular += 1
            if not _all_faces_simple(surface, planes, coordinates):
                continue
            stats.all_faces_simple += 1
            numerical = certify_geometry(surface, coordinates)
            if not numerical.valid:
                continue
            stats.numerically_valid += 1
            rational = tuple(
                tuple(Fraction(float(value)).limit_denominator(max_denominator) for value in plane)
                for plane in planes
            )
            exact = certify_rational_planes(surface, rational)
            if not exact.valid:
                continue
            stats.exactly_valid += 1
            candidates.append(
                PlaneSearchCandidate(
                    action=None if action is None else action.to_dict(),
                    floating_planes=tuple(tuple(float(value) for value in plane) for plane in planes),
                    rational_planes=tuple(tuple(str(value) for value in plane) for plane in rational),
                    numerical_certificate=numerical,
                    exact_certificate=exact,
                )
            )
            if len(candidates) >= stop_after:
                return tuple(candidates)
    return tuple(candidates)
