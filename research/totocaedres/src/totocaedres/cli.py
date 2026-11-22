from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .campaign import format_status, read_status, run_campaign
from .controls import load_positive_controls
from .enumerate import EnumerationStats, enumerate_triangular_complete
from .exact_geometry import certify_rational_planes
from .geometry import solve_geometry
from .io import read_surface, write_json
from .planner import plan_principal_search
from .symmetry_search import (
    PlaneSearchStats,
    discover_symmetry_actions,
    face_automorphisms,
    search_planes,
)
from .visualization import write_viewer_module


def _print(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _cmd_plan(args: argparse.Namespace) -> int:
    rows = plan_principal_search(
        max_genus=args.max_genus,
        max_faces=args.max_faces,
        max_extra_edges=args.max_extra_edges,
        max_holes=args.max_holes,
    )
    _print(
        {
            "problem": "principal: every face pair shares an edge",
            "necessary_only": True,
            "bounds": {
                "max_genus": args.max_genus,
                "max_faces": args.max_faces,
                "max_extra_edges": args.max_extra_edges,
                "max_holes": args.max_holes,
            },
            "signatures": [row.to_dict() for row in rows],
        }
    )
    return 0


def _cmd_enumerate_triangular(args: argparse.Namespace) -> int:
    stats = EnumerationStats()
    surfaces = list(
        enumerate_triangular_complete(
            args.faces,
            limit=args.limit,
            deduplicate=not args.labelled,
            stats=stats,
        )
    )
    payload = {
        "schema": "totocaedres.enumeration.v1",
        "complete": not stats.stopped_by_limit,
        "scope": {
            "faces": args.faces,
            "dual_graph": f"K{args.faces}",
            "primal_vertex_degree": 3,
            "holes": 0,
            "extra_edges": 0,
            "rooted_face": [0, 1, 2],
            "isomorphism_deduplication": not args.labelled,
        },
        "stats": vars(stats),
        "results": [
            {"surface": surface.to_dict(), "topology": surface.report(require_all_edge_adjacent=True).to_dict()}
            for surface in surfaces
        ],
    }
    if args.output:
        write_json(args.output, payload)
    _print({key: value for key, value in payload.items() if key != "results"} | {"result_count": len(surfaces)})
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    surface = read_surface(args.path)
    report = surface.report(
        require_all_edge_adjacent=args.principal,
        require_all_contacting=args.point_variant,
    )
    _print(report.to_dict())
    return 0 if report.valid else 2


def _cmd_solve(args: argparse.Namespace) -> int:
    surface = read_surface(args.path)
    result = solve_geometry(
        surface,
        restarts=args.restarts,
        seed=args.seed,
        max_nfev=args.max_nfev,
    )
    payload = {"surface": surface.to_dict(), "geometry": result.to_dict()}
    if args.output:
        write_json(args.output, payload)
    _print(result.to_dict())
    return 0 if result.success else 3


def _cmd_demo(args: argparse.Namespace) -> int:
    output = Path(args.output_dir)
    stats = EnumerationStats()
    surface = next(enumerate_triangular_complete(4, limit=1, stats=stats))
    map_path = output / "tetrahedron-map.json"
    result_path = output / "tetrahedron-realization.json"
    write_json(
        map_path,
        {
            "surface": surface.to_dict(),
            "topology": surface.report(require_all_edge_adjacent=True).to_dict(),
            "enumeration_stats": vars(stats),
        },
    )
    result = solve_geometry(surface, restarts=args.restarts, seed=args.seed)
    write_json(result_path, {"surface": surface.to_dict(), "geometry": result.to_dict()})
    _print(
        {
            "success": result.success,
            "map": str(map_path),
            "realization": str(result_path),
            "certificate": result.certificate.to_dict(),
        }
    )
    return 0 if result.success else 3


def _cmd_search_planes(args: argparse.Namespace) -> int:
    surface = read_surface(args.path)
    stats = PlaneSearchStats()
    candidates = search_planes(
        surface,
        trials_per_action=args.trials_per_action,
        seed=args.seed,
        use_symmetry=not args.cold_only,
        include_cold=args.include_cold or args.cold_only,
        max_actions=args.max_actions,
        max_denominator=args.max_denominator,
        stop_after=args.limit,
        stats=stats,
    )
    payload = {
        "schema": "totocaedres.plane-search.v1",
        "complete": False,
        "reason": "random geometric search under an explicit trial budget",
        "configuration": {
            "trials_per_action": args.trials_per_action,
            "seed": args.seed,
            "max_actions": args.max_actions,
            "max_denominator": args.max_denominator,
            "cold_only": args.cold_only,
            "include_cold": args.include_cold,
        },
        "surface": surface.to_dict(),
        "stats": vars(stats),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    if args.output:
        write_json(args.output, payload)
    _print({key: value for key, value in payload.items() if key != "candidates"} | {"candidate_count": len(candidates)})
    return 0 if candidates else 4


def _cmd_campaign_controls(args: argparse.Namespace) -> int:
    rows = []
    all_passed = True
    for index, control in enumerate(load_positive_controls(args.catalog)):
        topology = control.surface.report(require_all_edge_adjacent=True)
        known_certificate = certify_rational_planes(control.surface, control.certificate_planes)
        stats = PlaneSearchStats()
        candidates = search_planes(
            control.surface,
            trials_per_action=args.trials_per_action,
            seed=args.seed + index * args.seed_stride,
            max_actions=args.max_actions,
            max_denominator=args.max_denominator,
            stop_after=1,
            stats=stats,
        )
        passed = topology.valid and known_certificate.valid and bool(candidates)
        all_passed &= passed
        rows.append(
            {
                "control_id": control.control_id,
                "description": control.description,
                "source": control.source,
                "surface": control.surface.to_dict(),
                "passed": passed,
                "topology": topology.to_dict(),
                "known_certificate": known_certificate.to_dict(),
                "automorphism_count": len(face_automorphisms(control.surface)),
                "discovered_actions": [
                    action.to_dict()
                    for action in discover_symmetry_actions(
                        control.surface, max_actions=args.max_actions
                    )
                ],
                "search_stats": vars(stats),
                "found_candidates": [candidate.to_dict() for candidate in candidates],
            }
        )
    payload = {
        "schema": "totocaedres.validation-campaign.v1",
        "algorithm_policy": "identical generic search; control ids are reporting labels only",
        "passed": all_passed,
        "configuration": {
            "catalog": str(Path(args.catalog)),
            "trials_per_action": args.trials_per_action,
            "seed": args.seed,
            "seed_stride": args.seed_stride,
            "max_actions": args.max_actions,
            "max_denominator": args.max_denominator,
        },
        "controls": rows,
    }
    if args.output:
        write_json(args.output, payload)
    _print(
        {
            "schema": payload["schema"],
            "passed": all_passed,
            "configuration": payload["configuration"],
            "controls": [
                {
                    "control_id": row["control_id"],
                    "passed": row["passed"],
                    "search_stats": row["search_stats"],
                    "candidate_count": len(row["found_candidates"]),
                }
                for row in rows
            ],
        }
    )
    return 0 if all_passed else 5


def _cmd_export_viewer(args: argparse.Namespace) -> int:
    count = write_viewer_module(args.artifact, args.output)
    _print({"exported_models": count, "output": str(Path(args.output))})
    return 0


def _cmd_campaign_run(args: argparse.Namespace) -> int:
    return run_campaign(args.config, args.runtime, max_cycles=args.cycles)


def _cmd_campaign_status(args: argparse.Namespace) -> int:
    state = read_status(args.runtime)
    if args.json:
        _print(state)
    else:
        print(format_status(state))
    return 0 if state.get("status") != "error" else 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="totocaedres")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="list necessary integer signatures")
    plan.add_argument("--max-genus", type=int, default=3)
    plan.add_argument("--max-faces", type=int, default=10)
    plan.add_argument("--max-extra-edges", type=int, default=4)
    plan.add_argument("--max-holes", type=int, default=2)
    plan.set_defaults(func=_cmd_plan)

    enumerate_parser = sub.add_parser(
        "enumerate-triangular", help="exact-cover enumeration of triangular K4 or K7 embeddings"
    )
    enumerate_parser.add_argument("--faces", type=int, choices=(4, 7), required=True)
    enumerate_parser.add_argument("--limit", type=int)
    enumerate_parser.add_argument("--labelled", action="store_true")
    enumerate_parser.add_argument("--output")
    enumerate_parser.set_defaults(func=_cmd_enumerate_triangular)

    validate = sub.add_parser("validate", help="validate a serialized map")
    validate.add_argument("path")
    mode = validate.add_mutually_exclusive_group()
    mode.add_argument("--principal", action="store_true", help="require an edge contact per pair")
    mode.add_argument("--point-variant", action="store_true", help="allow edge or point contact")
    validate.set_defaults(func=_cmd_validate)

    solve = sub.add_parser("solve", help="run numerical geometric realization")
    solve.add_argument("path")
    solve.add_argument("--output")
    solve.add_argument("--restarts", type=int, default=8)
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--max-nfev", type=int, default=5_000)
    solve.set_defaults(func=_cmd_solve)

    demo = sub.add_parser("demo", help="enumerate, realize, and certify the tetrahedral control")
    demo.add_argument("--output-dir", default="output/demo")
    demo.add_argument("--restarts", type=int, default=2)
    demo.add_argument("--seed", type=int, default=0)
    demo.set_defaults(func=_cmd_demo)

    plane_search = sub.add_parser(
        "search-planes", help="generic random plane search with map-derived symmetries"
    )
    plane_search.add_argument("path")
    plane_search.add_argument("--output")
    plane_search.add_argument("--trials-per-action", type=int, default=5_000)
    plane_search.add_argument("--seed", type=int, default=2026111807)
    plane_search.add_argument("--max-actions", type=int, default=64)
    plane_search.add_argument("--max-denominator", type=int, default=1_000)
    plane_search.add_argument("--limit", type=int, default=1)
    plane_search.add_argument("--include-cold", action="store_true")
    plane_search.add_argument("--cold-only", action="store_true")
    plane_search.set_defaults(func=_cmd_search_planes)

    campaign = sub.add_parser(
        "campaign-controls", help="run the same generic pipeline on external positive controls"
    )
    campaign.add_argument("--catalog", default="benchmarks/positive_controls.json")
    campaign.add_argument("--output", default="output/validation-campaign.json")
    campaign.add_argument("--trials-per-action", type=int, default=5_000)
    campaign.add_argument("--seed", type=int, default=2026111807)
    campaign.add_argument("--seed-stride", type=int, default=0)
    campaign.add_argument("--max-actions", type=int, default=64)
    campaign.add_argument("--max-denominator", type=int, default=1_000)
    campaign.set_defaults(func=_cmd_campaign_controls)

    export_viewer = sub.add_parser(
        "export-viewer", help="export exact search candidates to Polyhedra Explorer"
    )
    export_viewer.add_argument("artifact", nargs="+")
    export_viewer.add_argument(
        "--output",
        default="output/generated-models.js",
    )
    export_viewer.set_defaults(func=_cmd_export_viewer)

    campaign_run = sub.add_parser(
        "campaign-run", help="run or resume the continuous offline discovery campaign"
    )
    campaign_run.add_argument("--config", default="campaign/config.json")
    campaign_run.add_argument("--runtime", default="campaign/runtime")
    campaign_run.add_argument(
        "--cycles", type=int, help="test-only cycle limit; omit for continuous operation"
    )
    campaign_run.set_defaults(func=_cmd_campaign_run)

    campaign_status = sub.add_parser("campaign-status", help="show discovery campaign status")
    campaign_status.add_argument("--runtime", default="campaign/runtime")
    campaign_status.add_argument("--json", action="store_true")
    campaign_status.set_defaults(func=_cmd_campaign_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
