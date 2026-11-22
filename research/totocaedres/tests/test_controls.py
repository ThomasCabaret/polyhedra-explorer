from totocaedres.controls import load_positive_controls, verify_positive_controls
from totocaedres.enumerate import canonical_complete_signature, enumerate_triangular_complete
from totocaedres.symmetry_search import PlaneSearchStats, discover_symmetry_actions, search_planes


CATALOG = "benchmarks/positive_controls.json"


def test_all_external_certificates_are_exactly_valid() -> None:
    results = verify_positive_controls(CATALOG)
    assert [control.surface.report().genus for control, _ in results] == [1, 3, 3]
    assert all(certificate.valid for _, certificate in results)


def test_szilassi_is_the_enumerated_k7_topology() -> None:
    szilassi = load_positive_controls(CATALOG)[0].surface
    enumerated = next(enumerate_triangular_complete(7, limit=1))
    assert canonical_complete_signature(szilassi) == canonical_complete_signature(enumerated)


def test_map_derived_symmetry_search_finds_genus3_without_known_planes() -> None:
    control = load_positive_controls(CATALOG)[1]
    actions = discover_symmetry_actions(control.surface)
    assert any(action.kind == "C4-improper" for action in actions)
    stats = PlaneSearchStats()
    candidates = search_planes(
        control.surface,
        trials_per_action=1_000,
        seed=2026111807,
        max_actions=2,
        stats=stats,
    )
    assert candidates
    assert candidates[0].exact_certificate.valid
    assert stats.trials == 313
