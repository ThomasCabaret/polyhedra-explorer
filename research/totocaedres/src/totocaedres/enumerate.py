from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations, product
from math import factorial
from typing import Iterator, Sequence

from .model import Pair, SurfaceMap


def complete_edge_pairs(face_count: int) -> tuple[Pair, ...]:
    return tuple((a, b) for a in range(face_count) for b in range(a + 1, face_count))


def multigraphs_with_extra_edges(face_count: int, extra_edges: int) -> Iterator[tuple[Pair, ...]]:
    """Enumerate labelled complete multigraphs with exactly ``extra_edges`` extras."""
    pairs = complete_edge_pairs(face_count)
    if extra_edges < 0:
        raise ValueError("extra_edges must be non-negative")

    def distribute(slot: int, remaining: int, counts: list[int]) -> Iterator[tuple[Pair, ...]]:
        if slot == len(pairs) - 1:
            counts.append(remaining)
            edges = list(pairs)
            for pair, count in zip(pairs, counts):
                edges.extend([pair] * count)
            yield tuple(edges)
            counts.pop()
            return
        for count in range(remaining + 1):
            counts.append(count)
            yield from distribute(slot + 1, remaining - count, counts)
            counts.pop()

    if pairs:
        yield from distribute(0, extra_edges, [])


def _canonical_cycle(cycle: Sequence[int]) -> tuple[int, ...]:
    values = tuple(cycle)
    return min(values[index:] + values[:index] for index in range(len(values)))


def _oriented_triangles(face_count: int) -> tuple[tuple[int, int, int], ...]:
    result: list[tuple[int, int, int]] = []
    for a, b, c in combinations(range(face_count), 3):
        result.append((a, b, c))
        result.append((a, c, b))
    return tuple(result)


def _triangle_arcs(triangle: tuple[int, int, int], n: int) -> tuple[int, int, int]:
    a, b, c = triangle
    return (a * n + b, b * n + c, c * n + a)


def _closes_short_cycle(successors: list[dict[int, int]], vertex: int, degree: int) -> bool:
    succ = successors[vertex]
    for start in succ:
        seen: set[int] = set()
        current = start
        while current in succ and current not in seen:
            seen.add(current)
            current = succ[current]
        if current == start and len(seen) < degree:
            return True
    return False


def _rotations_from_triangles(
    face_count: int, triangles: Sequence[tuple[int, int, int]]
) -> tuple[tuple[int, ...], ...] | None:
    successors: list[dict[int, int]] = [dict() for _ in range(face_count)]
    for a, b, c in triangles:
        for vertex, previous, following in ((a, c, b), (b, a, c), (c, b, a)):
            if previous in successors[vertex] and successors[vertex][previous] != following:
                return None
            successors[vertex][previous] = following
    rotations: list[tuple[int, ...]] = []
    for vertex, succ in enumerate(successors):
        neighbours = set(range(face_count)) - {vertex}
        if set(succ) != neighbours or set(succ.values()) != neighbours:
            return None
        start = min(neighbours)
        cycle = [start]
        while succ[cycle[-1]] != start:
            cycle.append(succ[cycle[-1]])
            if len(cycle) > len(neighbours):
                return None
        if len(cycle) != len(neighbours):
            return None
        rotations.append(tuple(cycle))
    return tuple(rotations)


def _surface_from_neighbour_rotations(rotations: Sequence[Sequence[int]]) -> SurfaceMap:
    n = len(rotations)
    edge_pairs = complete_edge_pairs(n)
    edge_index = {pair: index for index, pair in enumerate(edge_pairs)}
    edge_rotations = [
        [[edge_index[(min(face, neighbour), max(face, neighbour))] for neighbour in rotation]]
        for face, rotation in enumerate(rotations)
    ]
    return SurfaceMap.from_dual_rotation(edge_rotations, edge_pairs)


def _embedding_signature(surface: SurfaceMap, relabel: Sequence[int], reverse: bool) -> tuple:
    cycles: list[tuple[int, ...]] = []
    faces = surface.dart_faces
    for vertex in surface.vertices:
        labels = tuple(relabel[faces[dart]] for dart in vertex)
        if reverse:
            labels = tuple(reversed(labels))
        cycles.append(_canonical_cycle(labels))
    return tuple(sorted(cycles))


def canonical_complete_signature(surface: SurfaceMap) -> tuple:
    """Exact face-relabeling canonical form for simple complete dual maps.

    This intentionally uses all F! relabelings.  It is fast enough for the
    supported exact path F<=7 and avoids a heuristic graph hash in the proof of
    deduplication.
    """
    n = surface.face_count
    if n > 8:
        raise ValueError("exact factorial canonicalization is capped at eight faces")
    best: tuple | None = None
    for relabel in permutations(range(n)):
        for reverse in (False, True):
            signature = _embedding_signature(surface, relabel, reverse)
            if best is None or signature < best:
                best = signature
    assert best is not None
    return best


@dataclass
class EnumerationStats:
    states: int = 0
    exact_covers: int = 0
    connected_rotations: int = 0
    duplicates: int = 0
    yielded: int = 0
    stopped_by_limit: bool = False


def enumerate_triangular_complete(
    face_count: int,
    *,
    limit: int | None = None,
    deduplicate: bool = True,
    stats: EnumerationStats | None = None,
) -> Iterator[SurfaceMap]:
    """Enumerate orientable triangular embeddings of K_F up to isomorphism.

    The exact-cover search is rooted at the oriented triangle (0,1,2), which is
    complete up to relabeling.  It supports the production cases F=4 and F=7.
    """
    if face_count not in (4, 7):
        raise ValueError("the certified triangular fast path currently supports F=4 or F=7")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive or None")
    stats = stats if stats is not None else EnumerationStats()
    n = face_count
    triangles = _oriented_triangles(n)
    arcs = tuple(_triangle_arcs(triangle, n) for triangle in triangles)
    candidate_masks = tuple(sum(1 << arc for arc in values) for values in arcs)
    arc_candidates: list[list[int]] = [[] for _ in range(n * n)]
    for candidate, values in enumerate(arcs):
        for arc in values:
            arc_candidates[arc].append(candidate)

    root = triangles.index((0, 1, 2))
    root_mask = candidate_masks[root]
    successors: list[dict[int, int]] = [dict() for _ in range(n)]

    def assign(candidate: int) -> list[tuple[int, int]] | None:
        changes: list[tuple[int, int]] = []
        a, b, c = triangles[candidate]
        for vertex, previous, following in ((a, c, b), (b, a, c), (c, b, a)):
            existing = successors[vertex].get(previous)
            if existing is not None and existing != following:
                for changed_vertex, changed_previous in reversed(changes):
                    del successors[changed_vertex][changed_previous]
                return None
            if following in successors[vertex].values() and existing != following:
                for changed_vertex, changed_previous in reversed(changes):
                    del successors[changed_vertex][changed_previous]
                return None
            if existing is None:
                successors[vertex][previous] = following
                changes.append((vertex, previous))
        if any(_closes_short_cycle(successors, vertex, n - 1) for vertex, _ in changes):
            for changed_vertex, changed_previous in reversed(changes):
                del successors[changed_vertex][changed_previous]
            return None
        return changes

    def unassign(changes: Sequence[tuple[int, int]]) -> None:
        for vertex, previous in reversed(changes):
            del successors[vertex][previous]

    root_changes = assign(root)
    assert root_changes is not None
    required_arcs = [u * n + v for u in range(n) for v in range(n) if u != v]
    required_mask = sum(1 << arc for arc in required_arcs)
    chosen = [root]
    seen: set[tuple] = set()

    def search(used_mask: int) -> Iterator[SurfaceMap]:
        if limit is not None and stats.yielded >= limit:
            stats.stopped_by_limit = True
            return
        stats.states += 1
        if used_mask == required_mask:
            stats.exact_covers += 1
            rotations = _rotations_from_triangles(n, [triangles[index] for index in chosen])
            if rotations is None:
                return
            stats.connected_rotations += 1
            surface = _surface_from_neighbour_rotations(rotations)
            report = surface.report(require_all_edge_adjacent=True)
            expected_genus = (n - 3) * (n - 4) // 12
            if not report.valid or report.genus != expected_genus or report.degree_excess != 0:
                return
            if deduplicate:
                signature = canonical_complete_signature(surface)
                if signature in seen:
                    stats.duplicates += 1
                    return
                seen.add(signature)
            stats.yielded += 1
            yield surface
            return

        best_candidates: list[int] | None = None
        for arc in required_arcs:
            if used_mask & (1 << arc):
                continue
            available = [
                candidate
                for candidate in arc_candidates[arc]
                if not (candidate_masks[candidate] & used_mask)
            ]
            if not available:
                return
            if best_candidates is None or len(available) < len(best_candidates):
                best_candidates = available
                if len(available) == 1:
                    break
        assert best_candidates is not None
        for candidate in best_candidates:
            changes = assign(candidate)
            if changes is None:
                continue
            chosen.append(candidate)
            yield from search(used_mask | candidate_masks[candidate])
            chosen.pop()
            unassign(changes)
            if limit is not None and stats.yielded >= limit:
                stats.stopped_by_limit = True
                return

    yield from search(root_mask)
    unassign(root_changes)


def _set_partitions(items: tuple[int, ...], parts: int, min_size: int) -> Iterator[tuple[tuple[int, ...], ...]]:
    if parts == 1:
        if len(items) >= min_size:
            yield (items,)
        return
    first = items[0]
    rest = items[1:]
    max_first_size = len(items) - min_size * (parts - 1)
    for size in range(min_size, max_first_size + 1):
        for tail in combinations(rest, size - 1):
            block = (first,) + tail
            remaining = tuple(value for value in rest if value not in tail)
            for later in _set_partitions(remaining, parts - 1, min_size):
                yield (block,) + later


def _cyclic_orders(items: Sequence[int]) -> Iterator[tuple[int, ...]]:
    anchor = min(items)
    remainder = tuple(value for value in items if value != anchor)
    for order in permutations(remainder):
        yield (anchor,) + order


def _face_rotations(
    incident_edges: tuple[int, ...], components: int, min_contour_length: int
) -> Iterator[tuple[tuple[int, ...], ...]]:
    if len(incident_edges) < components * min_contour_length:
        return
    for partition in _set_partitions(incident_edges, components, min_contour_length):
        order_iterators = [_cyclic_orders(block) for block in partition]
        for cycles in product(*order_iterators):
            yield tuple(sorted(cycles))


def estimate_labelled_rotation_count(
    edge_faces: Sequence[Pair], components_per_face: Sequence[int], min_contour_length: int = 3
) -> int:
    """Conservative count used to reject accidental factorial explosions."""
    result = 1
    for face, components in enumerate(components_per_face):
        degree = sum(face in pair for pair in edge_faces)
        if degree < components * min_contour_length:
            return 0
        # Upper bound: all permutations, with cyclic anchors removed per component.
        result *= factorial(degree) // (min_contour_length**components)
    return result


def enumerate_bounded_rotations(
    edge_faces: Sequence[Pair],
    components_per_face: Sequence[int],
    *,
    target_genus: int | None = None,
    min_contour_length: int = 3,
    max_labelled_states: int = 1_000_000,
) -> Iterator[SurfaceMap]:
    """Factorial but complete labelled enumerator for a fixed dual multigraph."""
    face_count = len(components_per_face)
    if any(a == b or not 0 <= a < face_count or not 0 <= b < face_count for a, b in edge_faces):
        raise ValueError("edge_faces must contain distinct in-range face labels")
    estimate = estimate_labelled_rotation_count(edge_faces, components_per_face, min_contour_length)
    if estimate > max_labelled_states:
        raise ValueError(
            f"estimated labelled search ({estimate}) exceeds max_labelled_states={max_labelled_states}"
        )
    incident = [tuple(i for i, pair in enumerate(edge_faces) if face in pair) for face in range(face_count)]
    iterators = [
        _face_rotations(edges, components_per_face[face], min_contour_length)
        for face, edges in enumerate(incident)
    ]
    for rotations in product(*iterators):
        surface = SurfaceMap.from_dual_rotation(rotations, edge_faces)
        report = surface.report(min_contour_length=min_contour_length)
        if report.valid and (target_genus is None or report.genus == target_genus):
            yield surface
