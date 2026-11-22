from totocaedres.controls import load_positive_controls
from totocaedres.exact_geometry import certify_rational_planes
from totocaedres.visualization import models_from_search_artifact, write_viewer_module


def test_campaign_candidate_exports_to_viewer_model() -> None:
    control = load_positive_controls("benchmarks/positive_controls.json")[0]
    certificate = certify_rational_planes(control.surface, control.certificate_planes)
    artifact = {
        "schema": "totocaedres.validation-campaign.v1",
        "controls": [
            {
                "control_id": control.control_id,
                "description": control.description,
                "source": control.source,
                "surface": control.surface.to_dict(),
                "search_stats": {"trials": 12},
                "found_candidates": [
                    {
                        "action": {"kind": "C2-half-turn"},
                        "exact_certificate": certificate.to_dict(),
                    }
                ],
            }
        ],
    }
    models = models_from_search_artifact(artifact)
    assert len(models) == 1
    assert models[0]["expected"] == {"vertices": 14, "edges": 21, "faces": 7, "genus": 1}
    assert len(models[0]["faces"]) == 7


def test_export_combines_archived_controls_and_discovery(tmp_path) -> None:
    output = tmp_path / "models.js"
    count = write_viewer_module(
        [
            "results/validation-campaign.json",
            "results/discovery/9b4c587e1cb3c920ac499cd6.json",
        ],
        output,
    )
    assert count == 4
    assert '"discovery-9b4c587e1cb3c920ac499cd6-1"' in output.read_text(
        encoding="utf-8"
    )
