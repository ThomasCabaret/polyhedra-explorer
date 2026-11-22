from totocaedres.planner import plan_principal_search


def test_trivalent_control_signatures() -> None:
    rows = plan_principal_search(
        max_genus=3,
        max_faces=10,
        max_extra_edges=0,
        max_holes=0,
    )
    keys = {(row.genus, row.faces, row.degree_excess) for row in rows}
    assert (0, 4, 0) in keys
    assert (1, 7, 0) in keys


def test_paper_example_f8_g2_forces_no_holes() -> None:
    rows = plan_principal_search(
        max_genus=2,
        max_faces=8,
        max_extra_edges=2,
        max_holes=2,
    )
    selected = [row for row in rows if row.genus == 2 and row.faces == 8]
    assert selected
    assert all(row.extra_edges + row.degree_excess + 3 * row.holes == 2 for row in selected)
    assert all(row.holes == 0 for row in selected)
