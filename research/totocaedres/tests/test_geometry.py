import numpy as np

from totocaedres.enumerate import enumerate_triangular_complete
from totocaedres.geometry import certify_geometry, solve_geometry


def test_tetrahedron_realization_and_certificate() -> None:
    surface = next(enumerate_triangular_complete(4, limit=1))
    result = solve_geometry(surface, restarts=1, seed=1, max_nfev=1_000)
    assert result.success, result.certificate.errors
    assert result.certificate.max_planarity_error < 1e-10
    assert result.certificate.absolute_volume > 0.1


def test_certificate_rejects_collapsed_coordinates() -> None:
    surface = next(enumerate_triangular_complete(4, limit=1))
    certificate = certify_geometry(surface, np.zeros((4, 3)))
    assert not certificate.valid
    assert certificate.min_edge_length == 0.0
