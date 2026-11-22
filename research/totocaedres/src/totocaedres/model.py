from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Iterable, Iterator, Sequence


Pair = tuple[int, int]


def _cycles(permutation: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    seen = [False] * len(permutation)
    result: list[tuple[int, ...]] = []
    for start in range(len(permutation)):
        if seen[start]:
            continue
        cycle: list[int] = []
        current = start
        while not seen[current]:
            seen[current] = True
            cycle.append(current)
            current = permutation[current]
        if current != start:
            raise ValueError("not a permutation")
        result.append(tuple(cycle))
    return tuple(result)


def _normalise_pair(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


@dataclass(frozen=True)
class TopologyReport:
    valid: bool
    errors: tuple[str, ...]
    face_count: int
    boundary_component_count: int
    holes: int
    edge_count: int
    vertex_count: int
    euler_characteristic: int
    genus: int | None
    degree_excess: int
    segment_contacts: dict[str, int]
    point_contacts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SurfaceMap:
    """An orientable generalized map encoded by darts.

    ``alpha`` pairs the two darts of every primal edge.  ``boundaries`` groups
    cycles of the face-boundary permutation by generalized face.  A face with
    k cycles has k-1 holes.  Darts in each boundary are stored in their common
    orientation.
    """

    alpha: tuple[int, ...]
    boundaries: tuple[tuple[tuple[int, ...], ...], ...]

    @property
    def dart_count(self) -> int:
        return len(self.alpha)

    @property
    def face_count(self) -> int:
        return len(self.boundaries)

    @property
    def edge_count(self) -> int:
        return self.dart_count // 2

    @property
    def dart_faces(self) -> tuple[int, ...]:
        result = [-1] * self.dart_count
        for face, components in enumerate(self.boundaries):
            for component in components:
                for dart in component:
                    if 0 <= dart < self.dart_count:
                        result[dart] = face
        return tuple(result)

    @property
    def rho(self) -> tuple[int, ...]:
        result = [-1] * self.dart_count
        for components in self.boundaries:
            for component in components:
                if not component:
                    continue
                for current, following in zip(component, component[1:] + component[:1]):
                    if 0 <= current < self.dart_count:
                        result[current] = following
        return tuple(result)

    @property
    def phi(self) -> tuple[int, ...]:
        rho = self.rho
        return tuple(rho[self.alpha[dart]] for dart in range(self.dart_count))

    @property
    def vertices(self) -> tuple[tuple[int, ...], ...]:
        return _cycles(self.phi)

    @property
    def dart_vertices(self) -> tuple[int, ...]:
        result = [-1] * self.dart_count
        for vertex, cycle in enumerate(self.vertices):
            for dart in cycle:
                result[dart] = vertex
        return tuple(result)

    @property
    def primal_edges(self) -> tuple[tuple[int, int], ...]:
        dart_vertices = self.dart_vertices
        result: list[tuple[int, int]] = []
        for dart, other in enumerate(self.alpha):
            if dart < other:
                result.append((dart_vertices[dart], dart_vertices[other]))
        return tuple(result)

    @property
    def face_vertex_boundaries(self) -> tuple[tuple[tuple[int, ...], ...], ...]:
        dart_vertices = self.dart_vertices
        return tuple(
            tuple(tuple(dart_vertices[dart] for dart in component) for component in components)
            for components in self.boundaries
        )

    @property
    def edge_face_pairs(self) -> tuple[Pair, ...]:
        faces = self.dart_faces
        return tuple(
            _normalise_pair(faces[dart], faces[other])
            for dart, other in enumerate(self.alpha)
            if dart < other
        )

    def segment_contact_matrix(self) -> dict[Pair, int]:
        """Count connected components of shared-edge subgraphs for each pair."""
        vertices = self.primal_edges
        by_pair: dict[Pair, list[int]] = defaultdict(list)
        for edge, pair in enumerate(self.edge_face_pairs):
            by_pair[pair].append(edge)

        counts: dict[Pair, int] = {}
        for pair, edge_ids in by_pair.items():
            incident: dict[int, list[int]] = defaultdict(list)
            for edge_id in edge_ids:
                a, b = vertices[edge_id]
                incident[a].append(edge_id)
                incident[b].append(edge_id)
            unseen = set(edge_ids)
            components = 0
            while unseen:
                components += 1
                queue = [unseen.pop()]
                while queue:
                    edge_id = queue.pop()
                    for vertex in vertices[edge_id]:
                        for neighbour in incident[vertex]:
                            if neighbour in unseen:
                                unseen.remove(neighbour)
                                queue.append(neighbour)
            counts[pair] = components
        return counts

    def point_contact_matrix(self) -> dict[Pair, int]:
        faces = self.dart_faces
        counts: dict[Pair, int] = defaultdict(int)
        for cycle in self.vertices:
            incident_faces = [faces[dart] for dart in cycle]
            edge_pairs = {
                _normalise_pair(faces[dart], faces[self.alpha[dart]]) for dart in cycle
            }
            for index, a in enumerate(incident_faces):
                for b in incident_faces[index + 1 :]:
                    pair = _normalise_pair(a, b)
                    if a != b and pair not in edge_pairs:
                        counts[pair] += 1
        return dict(counts)

    def report(
        self,
        *,
        reduced: bool = True,
        min_contour_length: int = 3,
        require_connected: bool = True,
        require_all_edge_adjacent: bool = False,
        require_all_contacting: bool = False,
    ) -> TopologyReport:
        errors: list[str] = []
        n = self.dart_count
        if n == 0 or n % 2:
            errors.append("the dart count must be positive and even")

        if len(self.alpha) != n or any(not 0 <= a < n for a in self.alpha):
            errors.append("alpha contains an out-of-range dart")
        elif any(self.alpha[a] != d or a == d for d, a in enumerate(self.alpha)):
            errors.append("alpha must be a fixed-point-free involution")

        all_darts: list[int] = []
        for face, components in enumerate(self.boundaries):
            if not components:
                errors.append(f"face {face} has no boundary component")
            for component in components:
                if len(component) < min_contour_length:
                    errors.append(
                        f"face {face} has a contour shorter than {min_contour_length}"
                    )
                all_darts.extend(component)
        if sorted(all_darts) != list(range(n)):
            errors.append("every dart must occur exactly once in the face boundaries")

        safe_permutations = not errors and n > 0
        vertex_cycles: tuple[tuple[int, ...], ...] = ()
        if safe_permutations:
            try:
                vertex_cycles = self.vertices
            except (IndexError, ValueError):
                errors.append("rho o alpha is not a permutation")

        faces = self.dart_faces if len(all_darts) == n else tuple([-1] * n)
        if safe_permutations:
            for dart, other in enumerate(self.alpha):
                if faces[dart] == faces[other]:
                    errors.append(f"edge {min(dart, other)} is incident twice to one face")
                    break
            for vertex, cycle in enumerate(vertex_cycles):
                labels = [faces[dart] for dart in cycle]
                if len(labels) != len(set(labels)):
                    errors.append(f"face pinches or repeats at vertex {vertex}")
                if reduced and len(cycle) < 3:
                    errors.append(f"vertex {vertex} has degree below three")

            dart_vertices = [-1] * n
            for vertex, cycle in enumerate(vertex_cycles):
                for dart in cycle:
                    dart_vertices[dart] = vertex
            for dart, other in enumerate(self.alpha):
                if dart < other and dart_vertices[dart] == dart_vertices[other]:
                    errors.append(f"edge {dart // 2} is a loop or has zero topological length")

        adjacency: dict[int, set[int]] = defaultdict(set)
        if safe_permutations:
            for dart, other in enumerate(self.alpha):
                if dart < other:
                    a, b = faces[dart], faces[other]
                    adjacency[a].add(b)
                    adjacency[b].add(a)
        if require_connected and self.face_count:
            reached = {0}
            queue: deque[int] = deque([0])
            while queue:
                current = queue.popleft()
                new_faces = adjacency[current] - reached
                reached.update(new_faces)
                queue.extend(new_faces)
            if len(reached) != self.face_count:
                errors.append("the surface map is disconnected")

        boundary_count = sum(len(parts) for parts in self.boundaries)
        holes = boundary_count - self.face_count
        edge_count = n // 2
        vertex_count = len(vertex_cycles)
        chi = vertex_count - edge_count + self.face_count - holes
        genus_numerator = 2 - chi
        genus = genus_numerator // 2 if genus_numerator >= 0 and genus_numerator % 2 == 0 else None
        if genus is None:
            errors.append("Euler characteristic is not that of a closed orientable surface")
        degree_excess = sum(len(cycle) - 3 for cycle in vertex_cycles)

        segment = self.segment_contact_matrix() if safe_permutations else {}
        point = self.point_contact_matrix() if safe_permutations else {}
        all_pairs = {
            (a, b) for a in range(self.face_count) for b in range(a + 1, self.face_count)
        }
        if require_all_edge_adjacent:
            missing = sorted(all_pairs - set(segment))
            if missing:
                errors.append(f"missing edge contacts: {missing}")
        if require_all_contacting:
            missing = sorted(all_pairs - set(segment) - set(point))
            if missing:
                errors.append(f"missing edge-or-point contacts: {missing}")

        serialise = lambda values: {f"{a},{b}": value for (a, b), value in sorted(values.items())}
        return TopologyReport(
            valid=not errors,
            errors=tuple(dict.fromkeys(errors)),
            face_count=self.face_count,
            boundary_component_count=boundary_count,
            holes=holes,
            edge_count=edge_count,
            vertex_count=vertex_count,
            euler_characteristic=chi,
            genus=genus,
            degree_excess=degree_excess,
            segment_contacts=serialise(segment),
            point_contacts=serialise(point),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "totocaedres.surface-map.v1",
            "alpha": list(self.alpha),
            "boundaries": [
                [list(component) for component in components]
                for components in self.boundaries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SurfaceMap":
        if data.get("schema") != "totocaedres.surface-map.v1":
            raise ValueError("unsupported or missing surface-map schema")
        raw_boundaries = data["boundaries"]
        assert isinstance(raw_boundaries, list)
        return cls(
            alpha=tuple(int(value) for value in data["alpha"]),  # type: ignore[arg-type]
            boundaries=tuple(
                tuple(tuple(int(dart) for dart in component) for component in components)
                for components in raw_boundaries
            ),
        )

    @classmethod
    def from_dual_rotation(
        cls,
        rotations: Sequence[Sequence[Sequence[int]]],
        edge_faces: Sequence[Pair],
    ) -> "SurfaceMap":
        """Build from dual face labels and cyclic incident edge numbers.

        Each item of ``edge_faces`` is a pair of generalized faces.  Every
        occurrence of that edge number in a boundary creates one dart.
        """
        occurrences: dict[int, list[int]] = defaultdict(list)
        boundaries: list[list[tuple[int, ...]]] = []
        next_dart = 0
        for face, components in enumerate(rotations):
            built_components: list[tuple[int, ...]] = []
            for component in components:
                built: list[int] = []
                for edge in component:
                    a, b = edge_faces[edge]
                    if face not in (a, b):
                        raise ValueError(f"edge {edge} is not incident to face {face}")
                    occurrences[edge].append(next_dart)
                    built.append(next_dart)
                    next_dart += 1
                built_components.append(tuple(built))
            boundaries.append(built_components)
        if set(occurrences) != set(range(len(edge_faces))):
            raise ValueError("each edge must occur in the supplied rotations")
        alpha = [-1] * next_dart
        for edge, darts in occurrences.items():
            if len(darts) != 2:
                raise ValueError(f"edge {edge} occurs {len(darts)} times instead of twice")
            a, b = darts
            alpha[a] = b
            alpha[b] = a
        return cls(tuple(alpha), tuple(tuple(parts) for parts in boundaries))

    @classmethod
    def from_oriented_face_vertices(
        cls, face_boundaries: Sequence[Sequence[Sequence[int]]]
    ) -> "SurfaceMap":
        """Convenience constructor from consistently oriented primal contours."""
        edge_occurrences: dict[Pair, list[tuple[int, int, int]]] = defaultdict(list)
        dart_components: list[list[list[int]]] = []
        next_dart = 0
        for face, components in enumerate(face_boundaries):
            face_parts: list[list[int]] = []
            for component in components:
                if len(component) < 3:
                    raise ValueError("a polygonal contour needs at least three vertices")
                darts: list[int] = []
                for a, b in zip(component, component[1:] + component[:1]):
                    dart = next_dart
                    next_dart += 1
                    darts.append(dart)
                    edge_occurrences[_normalise_pair(a, b)].append((dart, a, b))
                face_parts.append(darts)
            dart_components.append(face_parts)
        alpha = [-1] * next_dart
        for edge, occurrences in edge_occurrences.items():
            if len(occurrences) != 2:
                raise ValueError(f"primal edge {edge} occurs {len(occurrences)} times")
            (d0, a0, b0), (d1, a1, b1) = occurrences
            if (a0, b0) != (b1, a1):
                raise ValueError(f"edge {edge} is not oppositely oriented")
            alpha[d0] = d1
            alpha[d1] = d0
        return cls(
            tuple(alpha),
            tuple(tuple(tuple(component) for component in parts) for parts in dart_components),
        )

    @classmethod
    def from_unoriented_face_vertices(
        cls, face_boundaries: Sequence[Sequence[Sequence[int]]]
    ) -> "SurfaceMap":
        """Orient a connected polygonal surface, then build its dart map.

        Input cycles may be independently reversed.  The method solves the
        signs forced by shared edges and rejects non-manifold or non-orientable
        gluings.  It is useful for published incidence tables, whose rows do
        not always use a common outward orientation.
        """
        edge_occurrences: dict[Pair, list[tuple[int, int]]] = defaultdict(list)
        for face, components in enumerate(face_boundaries):
            for component in components:
                for a, b in zip(component, component[1:] + component[:1]):
                    edge_occurrences[_normalise_pair(a, b)].append(
                        (face, 1 if a < b else -1)
                    )
        constraints: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for edge, occurrences in edge_occurrences.items():
            if len(occurrences) != 2:
                raise ValueError(f"primal edge {edge} occurs {len(occurrences)} times")
            (a, sign_a), (b, sign_b) = occurrences
            relative = -sign_a * sign_b
            constraints[a].append((b, relative))
            constraints[b].append((a, relative))
        orientation: dict[int, int] = {}
        for root in range(len(face_boundaries)):
            if root in orientation:
                continue
            orientation[root] = 1
            queue: deque[int] = deque([root])
            while queue:
                face = queue.popleft()
                for other, relative in constraints[face]:
                    expected = orientation[face] * relative
                    if other not in orientation:
                        orientation[other] = expected
                        queue.append(other)
                    elif orientation[other] != expected:
                        raise ValueError("the face gluing is non-orientable")
        oriented = [
            [list(component if orientation[face] == 1 else reversed(component)) for component in parts]
            for face, parts in enumerate(face_boundaries)
        ]
        return cls.from_oriented_face_vertices(oriented)
