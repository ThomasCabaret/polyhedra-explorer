from totocaedres.enumerate import EnumerationStats, enumerate_triangular_complete
from totocaedres.model import SurfaceMap


def test_tetrahedral_map() -> None:
    stats = EnumerationStats()
    maps = list(enumerate_triangular_complete(4, stats=stats))
    assert len(maps) == 1
    report = maps[0].report(require_all_edge_adjacent=True)
    assert report.valid, report.errors
    assert (report.face_count, report.vertex_count, report.edge_count) == (4, 4, 6)
    assert report.genus == 0
    assert report.degree_excess == 0
    assert not report.point_contacts


def test_k7_torus_map() -> None:
    stats = EnumerationStats()
    surface = next(enumerate_triangular_complete(7, limit=1, stats=stats))
    report = surface.report(require_all_edge_adjacent=True)
    assert report.valid, report.errors
    assert (report.face_count, report.vertex_count, report.edge_count) == (7, 14, 21)
    assert report.genus == 1
    assert report.degree_excess == 0
    assert len(report.segment_contacts) == 21


def test_json_round_trip() -> None:
    surface = next(enumerate_triangular_complete(4, limit=1))
    restored = SurfaceMap.from_dict(surface.to_dict())
    assert restored == surface
    assert restored.report(require_all_edge_adjacent=True).valid


def test_point_contacts_at_square_pyramid_apex() -> None:
    # Outward orientations: square base plus four triangular side faces.
    surface = SurfaceMap.from_oriented_face_vertices(
        [
            [[0, 3, 2, 1]],
            [[0, 1, 4]],
            [[1, 2, 4]],
            [[2, 3, 4]],
            [[3, 0, 4]],
        ]
    )
    report = surface.report()
    assert report.valid, report.errors
    assert report.genus == 0
    assert report.point_contacts == {"1,3": 1, "2,4": 1}
