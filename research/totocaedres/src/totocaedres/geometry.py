from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

from .model import SurfaceMap


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class GeometryCertificate:
    valid: bool
    errors: tuple[str, ...]
    numerical: bool
    max_planarity_error: float
    min_edge_length: float
    min_vertex_distance: float
    absolute_volume: float
    disjoint_triangle_intersections: int
    triangle_count: int
    tolerances: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GeometryResult:
    success: bool
    coordinates: tuple[tuple[float, float, float], ...]
    objective: float
    restarts: int
    message: str
    certificate: GeometryCertificate

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "totocaedres.geometry-result.v1",
            "success": self.success,
            "coordinates": [list(row) for row in self.coordinates],
            "objective": self.objective,
            "restarts": self.restarts,
            "message": self.message,
            "certificate": self.certificate.to_dict(),
        }


def _face_incident_vertices(surface: SurfaceMap) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(sorted({vertex for component in parts for vertex in component}))
        for parts in surface.face_vertex_boundaries
    )


def _initial_planes(surface: SurfaceMap, coordinates: FloatArray) -> tuple[FloatArray, FloatArray]:
    normals: list[FloatArray] = []
    offsets: list[float] = []
    for vertices in _face_incident_vertices(surface):
        points = coordinates[list(vertices)]
        centre = points.mean(axis=0)
        _, _, vh = np.linalg.svd(points - centre, full_matrices=False)
        normal = vh[-1]
        normal /= max(np.linalg.norm(normal), 1e-12)
        normals.append(normal)
        offsets.append(float(-normal @ centre))
    return np.asarray(normals), np.asarray(offsets)


def _tetrahedron_seed(surface: SurfaceMap) -> FloatArray | None:
    if len(surface.vertices) != 4 or len(surface.primal_edges) != 6:
        return None
    if len({tuple(sorted(edge)) for edge in surface.primal_edges}) != 6:
        return None
    return np.asarray(
        [
            (1.0, 1.0, 1.0),
            (1.0, -1.0, -1.0),
            (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0),
        ],
        dtype=float,
    ) / np.sqrt(3.0)


def solve_geometry(
    surface: SurfaceMap,
    *,
    restarts: int = 8,
    seed: int = 0,
    max_nfev: int = 5_000,
) -> GeometryResult:
    """Numerically search for planar faces; certification is performed later."""
    report = surface.report()
    if not report.valid:
        raise ValueError(f"cannot realize an invalid surface map: {report.errors}")
    if any(len(parts) != 1 for parts in surface.boundaries):
        certificate = GeometryCertificate(
            False,
            ("the v0.2 geometric solver does not triangulate holes",),
            True,
            float("inf"),
            0.0,
            0.0,
            0.0,
            0,
            0,
            _default_tolerances(),
        )
        return GeometryResult(False, (), float("inf"), 0, certificate.errors[0], certificate)
    if restarts < 1:
        raise ValueError("restarts must be positive")

    vertex_count = len(surface.vertices)
    face_count = surface.face_count
    incidences = _face_incident_vertices(surface)
    edges = np.asarray(surface.primal_edges, dtype=int)
    rng = np.random.default_rng(seed)
    tetra_seed = _tetrahedron_seed(surface)
    best_x: FloatArray | None = None
    best_cost = float("inf")
    best_rank = float("inf")
    best_message = "no optimization run"

    variable_count = 3 * vertex_count + 4 * face_count
    residual_count = (
        sum(len(vertices) for vertices in incidences)
        + face_count
        + 3
        + 1
        + 2 * len(edges)
        + vertex_count * (vertex_count - 1) // 2
    )
    sparsity = lil_matrix((residual_count, variable_count), dtype=int)
    row = 0
    normal_start = 3 * vertex_count
    offset_start = normal_start + 3 * face_count
    for face, vertices in enumerate(incidences):
        for vertex in vertices:
            sparsity[row, 3 * vertex : 3 * vertex + 3] = 1
            sparsity[row, normal_start + 3 * face : normal_start + 3 * face + 3] = 1
            sparsity[row, offset_start + face] = 1
            row += 1
    for face in range(face_count):
        sparsity[row, normal_start + 3 * face : normal_start + 3 * face + 3] = 1
        row += 1
    for coordinate in range(3):
        sparsity[row, coordinate : 3 * vertex_count : 3] = 1
        row += 1
    sparsity[row, : 3 * vertex_count] = 1
    row += 1
    for a, b in edges:
        for _ in range(2):
            sparsity[row, 3 * a : 3 * a + 3] = 1
            sparsity[row, 3 * b : 3 * b + 3] = 1
            row += 1
    for a in range(vertex_count):
        for b in range(a + 1, vertex_count):
            sparsity[row, 3 * a : 3 * a + 3] = 1
            sparsity[row, 3 * b : 3 * b + 3] = 1
            row += 1
    assert row == residual_count
    jacobian_sparsity = sparsity.tocsr()

    for restart in range(restarts):
        if restart == 0 and tetra_seed is not None:
            coordinates = tetra_seed.copy()
        else:
            coordinates = rng.normal(size=(vertex_count, 3))
            coordinates -= coordinates.mean(axis=0)
            coordinates /= max(np.sqrt(np.mean(np.sum(coordinates**2, axis=1))), 1e-12)
        normals, offsets = _initial_planes(surface, coordinates)
        initial = np.concatenate((coordinates.ravel(), normals.ravel(), offsets))

        def residual(vector: FloatArray) -> FloatArray:
            cursor = 3 * vertex_count
            xyz = vector[:cursor].reshape(vertex_count, 3)
            normal = vector[cursor : cursor + 3 * face_count].reshape(face_count, 3)
            offset = vector[cursor + 3 * face_count :]
            values: list[float] = []
            for face, vertices in enumerate(incidences):
                for vertex in vertices:
                    values.append(8.0 * float(normal[face] @ xyz[vertex] + offset[face]))
            values.extend(float(np.dot(row, row) - 1.0) for row in normal)
            values.extend(2.0 * value for value in xyz.mean(axis=0))
            rms = float(np.mean(np.sum(xyz**2, axis=1)))
            values.append(2.0 * (rms - 1.0))
            for a, b in edges:
                length = float(np.linalg.norm(xyz[a] - xyz[b]))
                values.append(0.08 * (length - 1.0))
                values.append(2.0 * max(0.0, 0.15 - length))
            for a in range(vertex_count):
                for b in range(a + 1, vertex_count):
                    distance = float(np.linalg.norm(xyz[a] - xyz[b]))
                    values.append(0.5 * max(0.0, 0.08 - distance))
            return np.asarray(values)

        fitted = least_squares(
            residual,
            initial,
            method="trf",
            max_nfev=max_nfev,
            jac_sparsity=jacobian_sparsity,
            x_scale="jac",
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
        )
        xyz = fitted.x[: 3 * vertex_count].reshape(vertex_count, 3)
        cost = float(2.0 * fitted.cost)
        certificate = certify_geometry(surface, xyz)
        ranked_cost = cost if certificate.valid else cost + 1_000_000.0
        if ranked_cost < best_rank:
            best_rank = ranked_cost
            best_cost = cost
            best_x = xyz.copy()
            best_message = fitted.message
        if certificate.valid:
            best_x = xyz.copy()
            best_cost = cost
            best_rank = cost
            best_message = fitted.message
            break

    assert best_x is not None
    certificate = certify_geometry(surface, best_x)
    return GeometryResult(
        success=certificate.valid,
        coordinates=tuple(tuple(float(value) for value in row) for row in best_x),
        objective=float(best_cost),
        restarts=restart + 1,
        message=str(best_message),
        certificate=certificate,
    )


def _default_tolerances() -> dict[str, float]:
    return {
        "planarity": 1e-7,
        "edge_length": 1e-5,
        "vertex_distance": 1e-5,
        "volume": 1e-8,
        "intersection": 1e-9,
    }


def _project_polygon(points: FloatArray) -> tuple[FloatArray, float]:
    centre = points.mean(axis=0)
    _, singular, vh = np.linalg.svd(points - centre, full_matrices=False)
    projected = (points - centre) @ vh[:2].T
    planarity = float(singular[-1] / max(np.sqrt(len(points)), 1.0)) if len(singular) == 3 else 0.0
    return projected, planarity


def _signed_area(points: FloatArray) -> float:
    return 0.5 * float(
        sum(
            points[i, 0] * points[(i + 1) % len(points), 1]
            - points[(i + 1) % len(points), 0] * points[i, 1]
            for i in range(len(points))
        )
    )


def _cross2(a: FloatArray, b: FloatArray, c: FloatArray) -> float:
    u = b - a
    v = c - a
    return float(u[0] * v[1] - u[1] * v[0])


def _point_in_triangle_2d(p: FloatArray, a: FloatArray, b: FloatArray, c: FloatArray, eps: float) -> bool:
    values = (_cross2(a, b, p), _cross2(b, c, p), _cross2(c, a, p))
    return all(value >= -eps for value in values) or all(value <= eps for value in values)


def _ear_clip(vertex_ids: Sequence[int], points: FloatArray, eps: float = 1e-12) -> list[tuple[int, int, int]]:
    if len(vertex_ids) == 3:
        return [tuple(vertex_ids)]  # type: ignore[list-item]
    orientation = 1.0 if _signed_area(points) > 0 else -1.0
    remaining = list(range(len(vertex_ids)))
    triangles: list[tuple[int, int, int]] = []
    guard = 0
    while len(remaining) > 3 and guard < len(vertex_ids) ** 2:
        guard += 1
        clipped = False
        for position, current in enumerate(remaining):
            previous = remaining[position - 1]
            following = remaining[(position + 1) % len(remaining)]
            if orientation * _cross2(points[previous], points[current], points[following]) <= eps:
                continue
            if any(
                _point_in_triangle_2d(
                    points[other], points[previous], points[current], points[following], eps
                )
                for other in remaining
                if other not in (previous, current, following)
            ):
                continue
            triangles.append(
                (vertex_ids[previous], vertex_ids[current], vertex_ids[following])
            )
            del remaining[position]
            clipped = True
            break
        if not clipped:
            raise ValueError("polygon is non-simple, self-touching, or numerically degenerate")
    if len(remaining) != 3:
        raise ValueError("polygon triangulation failed")
    triangles.append(tuple(vertex_ids[index] for index in remaining))
    return triangles


def _triangles(surface: SurfaceMap, coordinates: FloatArray) -> tuple[list[tuple[int, int, int]], float, list[str]]:
    triangles: list[tuple[int, int, int]] = []
    max_planarity = 0.0
    errors: list[str] = []
    for face, components in enumerate(surface.face_vertex_boundaries):
        if len(components) != 1:
            errors.append(f"face {face} has holes; v0.2 triangulation is disk-only")
            continue
        vertices = components[0]
        projected, planarity = _project_polygon(coordinates[list(vertices)])
        max_planarity = max(max_planarity, planarity)
        try:
            triangles.extend(_ear_clip(vertices, projected))
        except ValueError as exc:
            errors.append(f"face {face}: {exc}")
    return triangles, max_planarity, errors


def _projections_overlap(points_a: FloatArray, points_b: FloatArray, axis: FloatArray, eps: float) -> bool:
    norm = float(np.linalg.norm(axis))
    if norm <= eps:
        return True
    axis = axis / norm
    projection_a = points_a @ axis
    projection_b = points_b @ axis
    return not (projection_a.max() < projection_b.min() - eps or projection_b.max() < projection_a.min() - eps)


def _triangles_intersect(a: FloatArray, b: FloatArray, eps: float) -> bool:
    edges_a = [a[(i + 1) % 3] - a[i] for i in range(3)]
    edges_b = [b[(i + 1) % 3] - b[i] for i in range(3)]
    normal_a = np.cross(edges_a[0], edges_a[1])
    normal_b = np.cross(edges_b[0], edges_b[1])
    axes: list[FloatArray] = [normal_a, normal_b]
    axes.extend(np.cross(edge_a, edge_b) for edge_a in edges_a for edge_b in edges_b)
    axes.extend(np.cross(normal_a, edge) for edge in edges_a)
    axes.extend(np.cross(normal_b, edge) for edge in edges_b)
    return all(_projections_overlap(a, b, axis, eps) for axis in axes)


def certify_geometry(
    surface: SurfaceMap,
    coordinates: Sequence[Sequence[float]] | FloatArray,
    *,
    tolerances: dict[str, float] | None = None,
) -> GeometryCertificate:
    """Independent numerical checker; it does not reuse optimizer planes."""
    tol = dict(_default_tolerances() if tolerances is None else tolerances)
    xyz = np.asarray(coordinates, dtype=float)
    errors: list[str] = []
    if xyz.shape != (len(surface.vertices), 3) or not np.isfinite(xyz).all():
        return GeometryCertificate(
            False,
            ("coordinates must be a finite V by 3 array",),
            True,
            float("inf"),
            0.0,
            0.0,
            0.0,
            0,
            0,
            tol,
        )

    edge_lengths = [float(np.linalg.norm(xyz[a] - xyz[b])) for a, b in surface.primal_edges]
    min_edge = min(edge_lengths, default=0.0)
    distances = [
        float(np.linalg.norm(xyz[a] - xyz[b]))
        for a in range(len(xyz))
        for b in range(a + 1, len(xyz))
    ]
    min_distance = min(distances, default=0.0)
    if min_edge <= tol["edge_length"]:
        errors.append("an edge is too short")
    if min_distance <= tol["vertex_distance"]:
        errors.append("two distinct vertices coincide")

    triangles, max_planarity, triangulation_errors = _triangles(surface, xyz)
    errors.extend(triangulation_errors)
    if max_planarity > tol["planarity"]:
        errors.append("a face is not planar within tolerance")

    volume = abs(
        sum(float(np.dot(xyz[a], np.cross(xyz[b], xyz[c]))) / 6.0 for a, b, c in triangles)
    )
    if volume <= tol["volume"]:
        errors.append("the signed enclosed volume is zero or inconsistent")

    intersections = 0
    for index, triangle_a in enumerate(triangles):
        set_a = set(triangle_a)
        points_a = xyz[list(triangle_a)]
        for triangle_b in triangles[index + 1 :]:
            if set_a & set(triangle_b):
                continue
            if _triangles_intersect(points_a, xyz[list(triangle_b)], tol["intersection"]):
                intersections += 1
    if intersections:
        errors.append(f"found {intersections} intersections between disjoint triangles")

    return GeometryCertificate(
        valid=not errors,
        errors=tuple(errors),
        numerical=True,
        max_planarity_error=max_planarity,
        min_edge_length=min_edge,
        min_vertex_distance=min_distance,
        absolute_volume=volume,
        disjoint_triangle_intersections=intersections,
        triangle_count=len(triangles),
        tolerances=tol,
    )
