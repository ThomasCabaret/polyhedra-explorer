from __future__ import annotations

from dataclasses import asdict, dataclass
from math import comb


@dataclass(frozen=True, order=True)
class FeasibleSignature:
    genus: int
    faces: int
    extra_edges: int
    degree_excess: int
    holes: int
    edges: int
    vertices: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def plan_principal_search(
    *,
    max_genus: int,
    max_faces: int,
    max_extra_edges: int,
    max_holes: int,
    min_faces: int = 4,
) -> tuple[FeasibleSignature, ...]:
    """List integer signatures allowed by the necessary identities.

    The planner is for the principal problem (at least one edge per face pair)
    after suppressing degree-two vertices.  Returned rows are not existence
    claims.
    """
    if min(max_genus, max_faces, max_extra_edges, max_holes) < 0:
        raise ValueError("search bounds must be non-negative")
    result: list[FeasibleSignature] = []
    for genus in range(max_genus + 1):
        for faces in range(min_faces, max_faces + 1):
            baseline = (faces - 3) * (faces - 4)
            for holes in range(max_holes + 1):
                for extra in range(max_extra_edges + 1):
                    twice_excess = 12 * genus - baseline - 2 * extra - 6 * holes
                    if twice_excess < 0 or twice_excess % 2:
                        continue
                    degree_excess = twice_excess // 2
                    edges = comb(faces, 2) + extra
                    degree_sum_without_excess = 2 * edges - degree_excess
                    if degree_sum_without_excess < 0 or degree_sum_without_excess % 3:
                        continue
                    vertices = degree_sum_without_excess // 3
                    # Every polygonal contour has at least three distinct
                    # vertices, and local manifoldness lets a face occur at
                    # most once around a vertex.  Hence 3 <= deg(v) <= F.
                    if vertices < 3 or degree_excess > (faces - 3) * vertices:
                        continue
                    if vertices - edges + faces - holes != 2 - 2 * genus:
                        continue
                    result.append(
                        FeasibleSignature(
                            genus,
                            faces,
                            extra,
                            degree_excess,
                            holes,
                            edges,
                            vertices,
                        )
                    )
    return tuple(result)
