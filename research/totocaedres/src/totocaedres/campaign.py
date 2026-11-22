from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .enumerate import enumerate_triangular_complete
from .geometry import solve_geometry
from .io import write_json
from .model import Pair, SurfaceMap
from .planner import FeasibleSignature, plan_principal_search
from .symmetry_search import PlaneSearchStats, search_planes


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class CampaignConfig:
    max_genus: int = 3
    max_faces: int = 9
    max_extra_edges: int = 8
    max_holes: int = 2
    signatures_per_genus_per_cycle: int = 4
    topology_trials_per_signature: int = 120
    geometry_candidates_per_cycle: int = 4
    geometry_trials_per_action: int = 150
    initial_geometry_trials_per_action: int = 5_000
    max_symmetry_actions: int = 24
    numerical_restarts: int = 1
    numerical_max_nfev: int = 750
    sleep_between_cycles_seconds: int = 2
    seed: int = 2026112101

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "CampaignConfig":
        known = {field for field in cls.__dataclass_fields__}
        unknown = set(values) - known - {"schema", "description"}
        if unknown:
            raise ValueError(f"unknown campaign configuration keys: {sorted(unknown)}")
        config = cls(**{key: values[key] for key in known if key in values})
        if min(
            config.max_genus,
            config.max_faces,
            config.max_extra_edges,
            config.max_holes,
            config.signatures_per_genus_per_cycle,
            config.topology_trials_per_signature,
            config.geometry_candidates_per_cycle,
            config.geometry_trials_per_action,
            config.initial_geometry_trials_per_action,
            config.max_symmetry_actions,
            config.numerical_restarts,
            config.numerical_max_nfev,
            config.sleep_between_cycles_seconds,
        ) < 0:
            raise ValueError("campaign bounds and budgets must be non-negative")
        return config


def load_config(path: str | Path) -> CampaignConfig:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema") != "totocaedres.discovery-campaign-config.v1":
        raise ValueError("unsupported discovery campaign configuration schema")
    return CampaignConfig.from_dict(data)


def _atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    write_json(temporary, data)
    for attempt in range(100):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 99:
                raise
            # Windows readers (including the status command and virus
            # scanners) can briefly prevent ReplaceFile semantics.
            time.sleep(0.02 + min(attempt, 9) * 0.01)


def _event(runtime: Path, kind: str, **payload: Any) -> None:
    record = {"time": _now(), "kind": kind, **payload}
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _fingerprint(surface: SurfaceMap) -> str:
    encoded = json.dumps(surface.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def _new_state(config: CampaignConfig) -> dict[str, Any]:
    return {
        "schema": "totocaedres.discovery-campaign-state.v1",
        "status": "starting",
        "pid": os.getpid(),
        "started_at": _now(),
        "updated_at": _now(),
        "cycle": 0,
        "current_job": "initialization",
        "signature_cursors": {str(genus): 0 for genus in range(config.max_genus + 1)},
        "totals": {
            "topology_attempts": 0,
            "topology_valid": 0,
            "topology_unique": 0,
            "geometry_attempts": 0,
            "numerical_realizations": 0,
            "exact_realizations": 0,
            "errors": 0,
        },
        "by_genus": {
            str(genus): {
                "topology_attempts": 0,
                "topology_valid": 0,
                "topology_unique": 0,
                "geometry_attempts": 0,
                "numerical_realizations": 0,
                "exact_realizations": 0,
            }
            for genus in range(config.max_genus + 1)
        },
        "last_candidate": None,
        "last_error": None,
        "config": asdict(config),
    }


def _load_or_create_state(runtime: Path, config: CampaignConfig) -> dict[str, Any]:
    state_path = runtime / "state.json"
    if state_path.exists():
        with state_path.open("r", encoding="utf-8") as stream:
            state = json.load(stream)
        state["pid"] = os.getpid()
        state["status"] = "starting"
        state["updated_at"] = _now()
        state["last_error"] = None
        state["config"] = asdict(config)
        for genus in range(config.max_genus + 1):
            state.setdefault("signature_cursors", {}).setdefault(str(genus), 0)
            state.setdefault("by_genus", {}).setdefault(
                str(genus),
                {
                    "topology_attempts": 0,
                    "topology_valid": 0,
                    "topology_unique": 0,
                    "geometry_attempts": 0,
                    "numerical_realizations": 0,
                    "exact_realizations": 0,
                },
            )
        return state
    return _new_state(config)


def _save_state(runtime: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _atomic_json(runtime / "state.json", state)


def _increment(state: dict[str, Any], genus: int, key: str, amount: int = 1) -> None:
    state["totals"][key] += amount
    state["by_genus"][str(genus)][key] += amount


def _random_composition(total: int, parts: int, rng: random.Random) -> list[int]:
    result = [0] * parts
    for _ in range(total):
        result[rng.randrange(parts)] += 1
    return result


def random_surface_for_signature(
    signature: FeasibleSignature, rng: random.Random
) -> SurfaceMap | None:
    face_count = signature.faces
    base_pairs: list[Pair] = [
        (a, b) for a in range(face_count) for b in range(a + 1, face_count)
    ]
    edge_faces = base_pairs + [rng.choice(base_pairs) for _ in range(signature.extra_edges)]
    holes_by_face = _random_composition(signature.holes, face_count, rng)
    components_per_face = [1 + holes for holes in holes_by_face]
    incident = [
        [edge for edge, pair in enumerate(edge_faces) if face in pair]
        for face in range(face_count)
    ]
    rotations: list[list[list[int]]] = []
    for face, edges in enumerate(incident):
        component_count = components_per_face[face]
        if len(edges) < 3 * component_count:
            return None
        rng.shuffle(edges)
        sizes = [3] * component_count
        for _ in range(len(edges) - 3 * component_count):
            sizes[rng.randrange(component_count)] += 1
        parts: list[list[int]] = []
        cursor = 0
        for size in sizes:
            cycle = edges[cursor : cursor + size]
            cursor += size
            rng.shuffle(cycle)
            parts.append(cycle)
        rotations.append(parts)
    try:
        return SurfaceMap.from_dual_rotation(rotations, edge_faces)
    except ValueError:
        return None


def _signature_label(signature: FeasibleSignature) -> str:
    return (
        f"g={signature.genus},F={signature.faces},M={signature.extra_edges},"
        f"D={signature.degree_excess},H={signature.holes}"
    )


def _store_topology_candidate(
    runtime: Path,
    state: dict[str, Any],
    surface: SurfaceMap,
    source: dict[str, Any],
) -> tuple[Path, bool]:
    fingerprint = _fingerprint(surface)
    target = runtime / "candidates" / f"{fingerprint}.json"
    if target.exists():
        return target, False
    report = surface.report(require_all_edge_adjacent=True)
    payload = {
        "schema": "totocaedres.discovery-candidate.v1",
        "fingerprint": fingerprint,
        "created_at": _now(),
        "source": source,
        "surface": surface.to_dict(),
        "topology": report.to_dict(),
        "geometry": None,
    }
    _atomic_json(target, payload)
    _increment(state, report.genus or 0, "topology_unique")
    state["last_candidate"] = {
        "fingerprint": fingerprint,
        "genus": report.genus,
        "path": str(target),
        "geometry": "pending",
    }
    _event(runtime, "topology_candidate", fingerprint=fingerprint, genus=report.genus, source=source)
    return target, True


def _attempt_geometry(
    runtime: Path,
    state: dict[str, Any],
    candidate_path: Path,
    config: CampaignConfig,
    *,
    initial: bool,
    seed: int,
) -> None:
    with candidate_path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    surface = SurfaceMap.from_dict(payload["surface"])
    report = surface.report()
    genus = report.genus or 0
    _increment(state, genus, "geometry_attempts")
    state["current_job"] = f"geometry {candidate_path.stem} (g={genus})"
    _save_state(runtime, state)
    disk_faces = all(len(parts) == 1 for parts in surface.boundaries)
    trivalent = all(len(vertex) == 3 for vertex in surface.vertices)
    geometry: dict[str, Any]
    if disk_faces and trivalent:
        stats = PlaneSearchStats()
        candidates = search_planes(
            surface,
            trials_per_action=(
                config.initial_geometry_trials_per_action
                if initial
                else config.geometry_trials_per_action
            ),
            seed=seed,
            max_actions=config.max_symmetry_actions,
            stop_after=1,
            stats=stats,
        )
        geometry = {
            "method": "map-derived-symmetry-plane-search",
            "stats": asdict(stats),
            "exact_candidates": [candidate.to_dict() for candidate in candidates],
        }
        if candidates:
            _increment(state, genus, "exact_realizations")
            _event(
                runtime,
                "exact_realization",
                fingerprint=payload["fingerprint"],
                genus=genus,
                method=geometry["method"],
            )
    else:
        result = solve_geometry(
            surface,
            restarts=max(1, config.numerical_restarts),
            seed=seed,
            max_nfev=max(1, config.numerical_max_nfev),
        )
        geometry = {"method": "numerical-planarity", "result": result.to_dict()}
        if result.success:
            _increment(state, genus, "numerical_realizations")
            _event(
                runtime,
                "numerical_realization",
                fingerprint=payload["fingerprint"],
                genus=genus,
                method=geometry["method"],
            )
    payload["geometry"] = geometry
    payload["geometry_updated_at"] = _now()
    _atomic_json(candidate_path, payload)
    state["last_candidate"] = {
        "fingerprint": payload["fingerprint"],
        "genus": genus,
        "path": str(candidate_path),
        "geometry": (
            "exact"
            if geometry.get("exact_candidates")
            else "numerical"
            if geometry.get("result", {}).get("success")
            else "not_realized"
        ),
    }


def _select_signatures(
    config: CampaignConfig, state: dict[str, Any]
) -> list[FeasibleSignature]:
    planned = plan_principal_search(
        max_genus=config.max_genus,
        max_faces=config.max_faces,
        max_extra_edges=config.max_extra_edges,
        max_holes=config.max_holes,
    )
    selected: list[FeasibleSignature] = []
    for genus in range(config.max_genus + 1):
        rows = [row for row in planned if row.genus == genus]
        if not rows:
            continue
        cursor = state["signature_cursors"].get(str(genus), 0) % len(rows)
        count = min(config.signatures_per_genus_per_cycle, len(rows))
        selected.extend(rows[(cursor + offset) % len(rows)] for offset in range(count))
        state["signature_cursors"][str(genus)] = (cursor + count) % len(rows)
    return selected


def _pending_geometry(runtime: Path) -> dict[int, list[Path]]:
    result: dict[int, list[Path]] = {}
    for path in sorted((runtime / "candidates").glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            if payload.get("geometry") is not None:
                continue
            genus = payload.get("topology", {}).get("genus")
            if isinstance(genus, int):
                result.setdefault(genus, []).append(path)
        except (OSError, ValueError, TypeError):
            continue
    return result


def _acquire_lock(runtime: Path) -> Path:
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / "runner.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"campaign lock already exists: {lock}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    return lock


def run_campaign(
    config_path: str | Path,
    runtime_path: str | Path,
    *,
    max_cycles: int | None = None,
) -> int:
    config_file = Path(config_path).resolve()
    runtime = Path(runtime_path).resolve()
    lock = _acquire_lock(runtime)
    state: dict[str, Any] | None = None
    try:
        config = load_config(config_file)
        stop_file = runtime / "STOP"
        if stop_file.exists():
            stop_file.unlink()
        state = _load_or_create_state(runtime, config)
        state["status"] = "running"
        state["pid"] = os.getpid()
        _save_state(runtime, state)
        _event(runtime, "campaign_started", pid=os.getpid(), config=asdict(config))
        rng = random.Random(config.seed + int(state["cycle"]) * 1_000_003)

        while not stop_file.exists():
            config = load_config(config_file)
            state["config"] = asdict(config)
            cycle = int(state["cycle"])
            per_genus_geometry = max(
                1,
                config.geometry_candidates_per_cycle // max(1, config.max_genus + 1),
            )
            geometry_budget = {
                genus: per_genus_geometry for genus in range(config.max_genus + 1)
            }
            state["current_job"] = f"cycle {cycle}: deterministic low-genus maps"
            _save_state(runtime, state)

            for face_count in (4, 7):
                genus = 0 if face_count == 4 else 1
                if genus > config.max_genus:
                    continue
                for surface in enumerate_triangular_complete(face_count, limit=1):
                    candidate_path, created = _store_topology_candidate(
                        runtime,
                        state,
                        surface,
                        {
                            "method": "exact triangular complete embedding",
                            "faces": face_count,
                            "genus": genus,
                        },
                    )
                    if created and geometry_budget.get(genus, 0) > 0:
                        _attempt_geometry(
                            runtime,
                            state,
                            candidate_path,
                            config,
                            initial=True,
                            seed=config.seed + face_count,
                        )
                        geometry_budget[genus] -= 1

            for genus, paths in _pending_geometry(runtime).items():
                while paths and geometry_budget.get(genus, 0) > 0:
                    _attempt_geometry(
                        runtime,
                        state,
                        paths.pop(0),
                        config,
                        initial=genus in (0, 1),
                        seed=rng.randrange(2**31),
                    )
                    geometry_budget[genus] -= 1

            selected = _select_signatures(config, state)
            multiplier = 1 + int(math.log2(cycle + 1))
            for signature in selected:
                if stop_file.exists():
                    break
                label = _signature_label(signature)
                state["current_job"] = f"cycle {cycle}: topology {label}"
                _save_state(runtime, state)
                trials = config.topology_trials_per_signature * multiplier
                for trial in range(trials):
                    if stop_file.exists():
                        break
                    _increment(state, signature.genus, "topology_attempts")
                    surface = random_surface_for_signature(signature, rng)
                    if surface is None:
                        continue
                    report = surface.report(require_all_edge_adjacent=True)
                    if (
                        not report.valid
                        or report.genus != signature.genus
                        or report.holes != signature.holes
                        or report.degree_excess != signature.degree_excess
                    ):
                        continue
                    _increment(state, signature.genus, "topology_valid")
                    candidate_path, created = _store_topology_candidate(
                        runtime,
                        state,
                        surface,
                        {
                            "method": "random bounded rotation system",
                            "signature": signature.to_dict(),
                            "cycle": cycle,
                            "trial": trial,
                        },
                    )
                    if created and geometry_budget.get(signature.genus, 0) > 0:
                        _attempt_geometry(
                            runtime,
                            state,
                            candidate_path,
                            config,
                            initial=False,
                            seed=rng.randrange(2**31),
                        )
                        geometry_budget[signature.genus] -= 1
                    if trial % 50 == 0:
                        _save_state(runtime, state)

            state["cycle"] = cycle + 1
            state["current_job"] = "between cycles"
            _save_state(runtime, state)
            _event(runtime, "cycle_completed", cycle=cycle, totals=state["totals"])
            if max_cycles is not None and state["cycle"] >= max_cycles:
                state["status"] = "test_budget_complete"
                break
            for _ in range(config.sleep_between_cycles_seconds):
                if stop_file.exists():
                    break
                time.sleep(1)

        if state["status"] != "test_budget_complete":
            state["status"] = "stopped"
        state["current_job"] = None
        _save_state(runtime, state)
        _event(runtime, "campaign_stopped", status=state["status"])
        return 0
    except Exception as exc:
        if state is None:
            state = {
                "schema": "totocaedres.discovery-campaign-state.v1",
                "status": "error",
                "pid": os.getpid(),
                "started_at": _now(),
                "totals": {"errors": 1},
            }
        else:
            state["status"] = "error"
            state["totals"]["errors"] += 1
        state["last_error"] = {
            "time": _now(),
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        state["current_job"] = None
        _save_state(runtime, state)
        _event(runtime, "campaign_error", message=str(exc))
        return 1
    finally:
        if lock.exists():
            lock.unlink()


def read_status(runtime_path: str | Path) -> dict[str, Any]:
    path = Path(runtime_path) / "state.json"
    if not path.exists():
        return {
            "schema": "totocaedres.discovery-campaign-state.v1",
            "status": "not_started",
            "runtime": str(Path(runtime_path)),
        }
    with path.open("r", encoding="utf-8") as stream:
        state = json.load(stream)
    state["lock_present"] = (Path(runtime_path) / "runner.lock").exists()
    state["stop_requested"] = (Path(runtime_path) / "STOP").exists()
    pid = state.get("pid")
    alive = _process_is_alive(pid)
    state["process_alive"] = alive
    if state.get("status") == "running" and (
        not state["lock_present"] or alive is False
    ):
        state["status"] = "stale"
    return state


def _process_is_alive(pid: Any) -> bool | None:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            # Access may be denied across Windows job/sandbox boundaries even
            # though the worker is healthy.  Keep that distinct from an
            # invalid/nonexistent PID so the status command does not lie.
            return None if ctypes.get_last_error() == 5 else False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def format_status(state: dict[str, Any]) -> str:
    if state.get("status") == "not_started":
        return "Campaign status: NOT STARTED"
    totals = state.get("totals", {})
    alive = state.get("process_alive")
    alive_label = "unknown (access denied)" if alive is None else str(alive)
    lines = [
        f"Campaign status: {str(state.get('status', 'unknown')).upper()}",
        f"PID: {state.get('pid', '-')}   cycle: {state.get('cycle', 0)}",
        f"Process alive: {alive_label}   lock: {state.get('lock_present', False)}",
        f"Updated: {state.get('updated_at', '-')}",
        f"Current job: {state.get('current_job') or '-'}",
        (
            "Totals: topology attempts={topology_attempts}, valid={topology_valid}, "
            "unique={topology_unique}, geometry={geometry_attempts}, "
            "numerical={numerical_realizations}, exact={exact_realizations}, errors={errors}"
        ).format(
            topology_attempts=totals.get("topology_attempts", 0),
            topology_valid=totals.get("topology_valid", 0),
            topology_unique=totals.get("topology_unique", 0),
            geometry_attempts=totals.get("geometry_attempts", 0),
            numerical_realizations=totals.get("numerical_realizations", 0),
            exact_realizations=totals.get("exact_realizations", 0),
            errors=totals.get("errors", 0),
        ),
        "By genus:",
    ]
    for genus, row in sorted(state.get("by_genus", {}).items(), key=lambda item: int(item[0])):
        lines.append(
            f"  g={genus}: attempts={row.get('topology_attempts', 0)}, "
            f"valid={row.get('topology_valid', 0)}, unique={row.get('topology_unique', 0)}, "
            f"geometry={row.get('geometry_attempts', 0)}, "
            f"numerical={row.get('numerical_realizations', 0)}, "
            f"exact={row.get('exact_realizations', 0)}"
        )
    if state.get("last_candidate"):
        candidate = state["last_candidate"]
        lines.append(
            f"Last candidate: {candidate.get('fingerprint')} g={candidate.get('genus')} "
            f"geometry={candidate.get('geometry')}"
        )
        lines.append(f"  {candidate.get('path')}")
    if state.get("last_error"):
        lines.append(f"Last error: {state['last_error'].get('message')}")
    if state.get("stop_requested"):
        lines.append("A graceful stop has been requested.")
    return "\n".join(lines)
