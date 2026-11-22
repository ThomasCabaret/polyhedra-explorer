from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
from typing import Sequence

from .model import SurfaceMap


Q = Fraction
Point2 = tuple[Q, Q]
Point3 = tuple[Q, Q, Q]
Plane = tuple[Q, Q, Q, Q]


def _q(value: int | str | Q) -> Q:
    return value if isinstance(value, Q) else Q(value)


def _dot(a: Sequence[Q], b: Sequence[Q]) -> Q:
    return sum((x * y for x, y in zip(a, b)), Q(0))


def _cross(a: Sequence[Q], b: Sequence[Q]) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: Sequence[Q], b: Sequence[Q]) -> Point3:
    return tuple(x - y for x, y in zip(a, b))  # type: ignore[return-value]


def _solve_three(planes: Sequence[Plane]) -> Point3:
    normals = [plane[:3] for plane in planes]
    offsets = [plane[3] for plane in planes]
    determinant = _dot(normals[0], _cross(normals[1], normals[2]))
    if determinant == 0:
        raise ValueError("singular supporting-plane triple")
    columns = (
        _cross(normals[1], normals[2]),
        _cross(normals[2], normals[0]),
        _cross(normals[0], normals[1]),
    )
    return tuple(
        sum((offsets[i] * columns[i][coordinate] for i in range(3)), Q(0))
        / determinant
        for coordinate in range(3)
    )  # type: ignore[return-value]


def _orient(a: Point2, b: Point2, c: Point2) -> Q:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(point: Point2, a: Point2, b: Point2) -> bool:
    return _orient(a, b, point) == 0 and all(
        min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, point)
    )


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    values = (_orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b))
    if values[0] * values[1] < 0 and values[2] * values[3] < 0:
        return True
    return any(
        value == 0 and _on_segment(point, start, end)
        for value, point, start, end in (
            (values[0], c, a, b),
            (values[1], d, a, b),
            (values[2], a, c, d),
            (values[3], b, c, d),
        )
    )


def _simple_polygon(polygon: Sequence[Point2]) -> bool:
    size = len(polygon)
    if size < 3 or len(set(polygon)) != size:
        return False
    area2 = sum(
        polygon[i][0] * polygon[(i + 1) % size][1]
        - polygon[i][1] * polygon[(i + 1) % size][0]
        for i in range(size)
    )
    if area2 == 0:
        return False
    for i in range(size):
        for j in range(i + 2, size):
            if i == 0 and j == size - 1:
                continue
            if _segments_intersect(
                polygon[i], polygon[(i + 1) % size], polygon[j], polygon[(j + 1) % size]
            ):
                return False
    return True


def _point_in_polygon(point: Point2, polygon: Sequence[Point2]) -> bool:
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(point, a, b):
            return True
    x, y = point
    crossings = 0
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            x_hit = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
            crossings += x_hit > x
    return bool(crossings % 2)


def _project(normal: Sequence[Q], points: Sequence[Point3]) -> tuple[list[Point2], int]:
    discarded = max(range(3), key=lambda coordinate: abs(normal[coordinate]))
    return (
        [tuple(point[k] for k in range(3) if k != discarded) for point in points],  # type: ignore[list-item]
        discarded,
    )


def _line_of_planes(a: Plane, b: Plane) -> tuple[Point3, Point3, int] | None:
    direction = _cross(a[:3], b[:3])
    if direction == (0, 0, 0):
        return None
    coordinate = max(range(3), key=lambda k: abs(direction[k]))
    other = [k for k in range(3) if k != coordinate]
    u, v = other
    determinant = a[u] * b[v] - a[v] * b[u]
    if determinant == 0:
        raise AssertionError("selected a zero line minor")
    point = [Q(0), Q(0), Q(0)]
    point[u] = (a[3] * b[v] - b[3] * a[v]) / determinant
    point[v] = (a[u] * b[3] - b[u] * a[3]) / determinant
    return tuple(point), direction, coordinate  # type: ignore[return-value]


def _line_breakpoints(
    planes: Sequence[Plane],
    xyz: Sequence[Point3],
    boundaries: Sequence[Sequence[int]],
    i: int,
    j: int,
    point: Point3,
    direction: Point3,
    coordinate: int,
) -> list[Q]:
    values: set[Q] = set()
    for face, other in ((i, j), (j, i)):
        normal, offset = planes[other][:3], planes[other][3]
        boundary = boundaries[face]
        for u, v in zip(boundary, boundary[1:] + boundary[:1]):
            a, b = xyz[u], xyz[v]
            sa = _dot(normal, a) - offset
            sb = _dot(normal, b) - offset
            if sa == 0:
                values.add((a[coordinate] - point[coordinate]) / direction[coordinate])
            if sb == 0:
                values.add((b[coordinate] - point[coordinate]) / direction[coordinate])
            if sa * sb < 0:
                crossing = a[coordinate] + (b[coordinate] - a[coordinate]) * (-sa) / (sb - sa)
                values.add((crossing - point[coordinate]) / direction[coordinate])
    return sorted(values)


@dataclass(frozen=True)
class ExactGeometryCertificate:
    valid: bool
    errors: tuple[str, ...]
    face_count: int
    vertex_count: int
    edge_count: int
    genus: int | None
    tested_face_pairs: int
    exact_coordinates: tuple[tuple[str, str, str], ...]
    signed_six_volume: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def certify_rational_planes(
    surface: SurfaceMap,
    plane_coefficients: Sequence[Sequence[int | str | Q]],
) -> ExactGeometryCertificate:
    """Exact certificate for disk faces supported by distinct nonparallel planes.

    Vertices may have valence above three: the first three incident planes
    determine the point and all remaining incidences are then checked exactly.
    """
    report = surface.report()
    errors: list[str] = list(report.errors)
    if len(plane_coefficients) != surface.face_count:
        errors.append("one plane equation is required for every face")
    if any(len(parts) != 1 for parts in surface.boundaries):
        errors.append("the exact v0.2 certificate currently supports disk faces only")
    try:
        planes: tuple[Plane, ...] = tuple(
            tuple(_q(value) for value in plane)  # type: ignore[misc]
            for plane in plane_coefficients
        )
    except (ValueError, ZeroDivisionError):
        planes = ()
        errors.append("invalid rational plane coefficient")
    if any(len(plane) != 4 or plane[:3] == (0, 0, 0) for plane in planes):
        errors.append("each plane needs a nonzero normal and one offset")

    faces_by_vertex: list[tuple[int, ...]] = []
    dart_faces = surface.dart_faces
    for cycle in surface.vertices:
        faces_by_vertex.append(tuple(sorted({dart_faces[dart] for dart in cycle})))
    xyz: list[Point3] = []
    if not errors:
        for vertex, incident in enumerate(faces_by_vertex):
            if len(incident) < 3:
                errors.append(f"vertex {vertex} has fewer than three supporting planes")
                xyz.append((Q(0), Q(0), Q(0)))
                continue
            try:
                point = _solve_three([planes[face] for face in incident[:3]])
            except ValueError as exc:
                errors.append(f"vertex {vertex}: {exc}")
                xyz.append((Q(0), Q(0), Q(0)))
                continue
            if any(_dot(planes[face][:3], point) != planes[face][3] for face in incident):
                errors.append(f"vertex {vertex} misses an incident supporting plane")
            xyz.append(point)
        if len(set(xyz)) != len(xyz):
            errors.append("two combinatorially distinct vertices have identical coordinates")

    boundaries = [list(parts[0]) for parts in surface.face_vertex_boundaries] if xyz else []
    projections: list[tuple[list[Point2], int]] = []
    if xyz and not errors:
        for face, boundary in enumerate(boundaries):
            if any(_dot(planes[face][:3], xyz[vertex]) != planes[face][3] for vertex in boundary):
                errors.append(f"face {face} is not planar")
            projection = _project(planes[face][:3], [xyz[vertex] for vertex in boundary])
            projections.append(projection)
            if not _simple_polygon(projection[0]):
                errors.append(f"face {face} is not a simple polygon")

    common_edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    common_vertices: dict[tuple[int, int], set[int]] = {}
    if xyz:
        for edge, pair in zip(surface.primal_edges, surface.edge_face_pairs):
            common_edges.setdefault(pair, []).append(edge)
        for vertex, incident in enumerate(faces_by_vertex):
            for pair in combinations(incident, 2):
                common_vertices.setdefault(pair, set()).add(vertex)

    tested_pairs = 0
    if xyz and len(projections) == surface.face_count and not errors:
        for i, j in combinations(range(surface.face_count), 2):
            tested_pairs += 1
            pair = (i, j)
            line = _line_of_planes(planes[i], planes[j])
            expected_contact = bool(common_vertices.get(pair) or common_edges.get(pair))
            if line is None:
                cross_offset = tuple(
                    planes[i][k] * planes[j][3] - planes[j][k] * planes[i][3]
                    for k in range(3)
                )
                if cross_offset == (0, 0, 0):
                    errors.append(f"faces {i},{j} have coplanar supports and should be merged")
                elif expected_contact:
                    errors.append(f"contacting faces {i},{j} have parallel supports")
                continue
            base, direction, coordinate = line
            breaks = _line_breakpoints(planes, xyz, boundaries, i, j, base, direction, coordinate)

            def point_at(parameter: Q) -> Point3:
                return tuple(base[k] + parameter * direction[k] for k in range(3))  # type: ignore[return-value]

            def actual(parameter: Q) -> bool:
                point = point_at(parameter)
                return all(
                    _point_in_polygon(
                        tuple(point[k] for k in range(3) if k != projections[face][1]),  # type: ignore[arg-type]
                        projections[face][0],
                    )
                    for face in (i, j)
                )

            def expected(parameter: Q) -> bool:
                point = point_at(parameter)
                if any(point == xyz[vertex] for vertex in common_vertices.get(pair, ())):
                    return True
                for u, v in common_edges.get(pair, ()):
                    a, b = xyz[u], xyz[v]
                    if _cross(_sub(point, a), _sub(b, a)) == (0, 0, 0) and all(
                        min(x, y) <= z <= max(x, y) for z, x, y in zip(point, a, b)
                    ):
                        return True
                return False

            if len(breaks) < 2 and expected_contact:
                errors.append(f"faces {i},{j} have no certified intersection interval")
                continue
            mismatch = False
            for a, b in zip(breaks, breaks[1:]):
                midpoint = (a + b) / 2
                if actual(midpoint) != expected(midpoint):
                    errors.append(f"faces {i},{j} have an extra or missing intersection segment")
                    mismatch = True
                    break
            if not mismatch:
                for parameter in breaks:
                    if actual(parameter) != expected(parameter):
                        errors.append(f"faces {i},{j} have an extra or missing point contact")
                        break

    signed_six_volume = Q(0)
    if xyz:
        for boundary in boundaries:
            anchor = boundary[0]
            for index in range(1, len(boundary) - 1):
                signed_six_volume += _dot(
                    xyz[anchor], _cross(xyz[boundary[index]], xyz[boundary[index + 1]])
                )
        if signed_six_volume == 0:
            errors.append("the exact signed volume is zero")

    return ExactGeometryCertificate(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        face_count=surface.face_count,
        vertex_count=len(surface.vertices),
        edge_count=surface.edge_count,
        genus=report.genus,
        tested_face_pairs=tested_pairs,
        exact_coordinates=tuple(tuple(str(value) for value in point) for point in xyz),
        signed_six_volume=str(signed_six_volume),
    )
