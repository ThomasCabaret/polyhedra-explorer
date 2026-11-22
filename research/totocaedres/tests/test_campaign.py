import json
from pathlib import Path

from totocaedres.campaign import _atomic_json, format_status, read_status, run_campaign


def test_atomic_json_retries_transient_windows_reader_lock(tmp_path, monkeypatch) -> None:
    target = tmp_path / "state.json"
    real_replace = Path.replace
    attempts = 0

    def flaky_replace(path: Path, destination: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise PermissionError("simulated Windows sharing violation")
        return real_replace(path, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    _atomic_json(target, {"cycle": 7})

    assert attempts == 4
    assert json.loads(target.read_text(encoding="utf-8")) == {"cycle": 7}


def test_single_cycle_campaign_is_resumable(tmp_path) -> None:
    config = tmp_path / "config.json"
    runtime = tmp_path / "runtime"
    config.write_text(
        json.dumps(
            {
                "schema": "totocaedres.discovery-campaign-config.v1",
                "max_genus": 0,
                "max_faces": 4,
                "max_extra_edges": 0,
                "max_holes": 0,
                "signatures_per_genus_per_cycle": 1,
                "topology_trials_per_signature": 1,
                "geometry_candidates_per_cycle": 0,
                "geometry_trials_per_action": 1,
                "initial_geometry_trials_per_action": 1,
                "max_symmetry_actions": 1,
                "numerical_restarts": 1,
                "numerical_max_nfev": 10,
                "sleep_between_cycles_seconds": 0,
                "seed": 7,
            }
        ),
        encoding="utf-8",
    )
    assert run_campaign(config, runtime, max_cycles=1) == 0
    state = read_status(runtime)
    assert state["status"] == "test_budget_complete"
    assert state["cycle"] == 1
    assert state["totals"]["topology_unique"] >= 1
    assert not (runtime / "runner.lock").exists()
    assert "g=0" in format_status(state)
