from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from .model import SurfaceMap


def _coordinate(value: int | float | str) -> float:
    if isinstance(value, str):
        return float(Fraction(value))
    return float(value)


def viewer_model(
    surface: SurfaceMap,
    coordinates: Sequence[Sequence[int | float | str]],
    *,
    model_id: str,
    title: str,
    description: str,
    symmetry: str,
    reference_label: str,
    reference_url: str,
    date: str = "Generated search candidate",
) -> dict[str, Any]:
    report = surface.report()
    if not report.valid:
        raise ValueError(f"cannot export an invalid map: {report.errors}")
    if any(len(parts) != 1 for parts in surface.face_vertex_boundaries):
        raise ValueError("the current web viewer supports disk faces only")
    vertices = [[_coordinate(value) for value in point] for point in coordinates]
    if len(vertices) != report.vertex_count or any(len(point) != 3 for point in vertices):
        raise ValueError("coordinates must contain one 3D point per map vertex")
    faces = [[int(vertex) for vertex in parts[0]] for parts in surface.face_vertex_boundaries]
    sizes = sorted({len(face) for face in faces})
    face_type = (
        f"{len(faces)} faces of size {sizes[0]}"
        if len(sizes) == 1
        else f"{len(faces)} faces; sizes {', '.join(map(str, sizes))}"
    )
    return {
        "id": model_id,
        "shortName": title,
        "title": title,
        "date": date,
        "author": "Totocaedres search",
        "referenceLabel": reference_label,
        "referenceUrl": reference_url,
        "dataUrl": "",
        "description": description,
        "symmetry": symmetry,
        "faceType": face_type,
        "expected": {
            "vertices": report.vertex_count,
            "edges": report.edge_count,
            "faces": report.face_count,
            "genus": report.genus,
        },
        "vertices": vertices,
        "faceNames": [f"F{index + 1}" for index in range(report.face_count)],
        "faces": faces,
    }


def models_from_search_artifact(data: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    schema = data.get("schema")
    models: list[dict[str, Any]] = []
    if schema == "totocaedres.validation-campaign.v1":
        for row in data["controls"]:
            if not row.get("found_candidates"):
                continue
            candidate = row["found_candidates"][0]
            action = candidate.get("action") or {}
            source = str(row.get("source", ""))
            trials = int(row["search_stats"]["trials"])
            models.append(
                viewer_model(
                    SurfaceMap.from_dict(row["surface"]),
                    candidate["exact_certificate"]["exact_coordinates"],
                    model_id=f"search-{row['control_id']}",
                    title=f"Search: {row['control_id']}",
                    description=(
                        f"Rational realization found by the generic map-derived symmetry search "
                        f"after {trials} trials. Known coordinates were not used."
                    ),
                    symmetry=str(action.get("kind", "none")),
                    reference_label=str(row.get("description", row["control_id"])),
                    reference_url=source if source.startswith("http") else "",
                )
            )
    elif schema == "totocaedres.plane-search.v1":
        surface = SurfaceMap.from_dict(data["surface"])
        for index, candidate in enumerate(data.get("candidates", []), start=1):
            action = candidate.get("action") or {}
            models.append(
                viewer_model(
                    surface,
                    candidate["exact_certificate"]["exact_coordinates"],
                    model_id=f"search-candidate-{index}",
                    title=f"Search candidate {index}",
                    description="Rational realization produced by the generic plane search.",
                    symmetry=str(action.get("kind", "none")),
                    reference_label="Totocaedres search artifact",
                    reference_url="",
                )
            )
    elif schema == "totocaedres.discovery-candidate.v1":
        surface = SurfaceMap.from_dict(data["surface"])
        geometry = data.get("geometry") or {}
        for index, candidate in enumerate(geometry.get("exact_candidates", []), start=1):
            certificate = candidate["exact_certificate"]
            if not certificate["valid"]:
                continue
            fingerprint = data["fingerprint"]
            action = candidate.get("action") or {}
            models.append(
                viewer_model(
                    surface,
                    certificate["exact_coordinates"],
                    model_id=f"discovery-{fingerprint}-{index}",
                    title=f"Discovery: genus {certificate['genus']}, {surface.face_count} faces",
                    description=(
                        "Exact rational realization from the discovery campaign. "
                        f"Map source: {data['source']['method']}."
                    ),
                    symmetry=str(action.get("kind", "none")),
                    reference_label=f"Discovery record {fingerprint}",
                    reference_url="",
                )
            )
    else:
        raise ValueError(f"unsupported search artifact schema: {schema!r}")
    return tuple(models)


def write_viewer_module(
    artifact: str | Path | Sequence[str | Path], output: str | Path
) -> int:
    paths = (artifact,) if isinstance(artifact, (str, Path)) else artifact
    model_map: dict[str, dict[str, Any]] = {}
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as stream:
            models = models_from_search_artifact(json.load(stream))
        for model in models:
            model_id = model["id"]
            if model_id in model_map and model_map[model_id] != model:
                raise ValueError(f"conflicting viewer model id: {model_id}")
            model_map[model_id] = model
    text = (
        "// Generated by `python -m totocaedres export-viewer`; do not edit by hand.\n"
        f"const DATA = {json.dumps(model_map, ensure_ascii=False, indent=2)};\n\n"
        "for (const model of Object.values(DATA)) {\n"
        "  model.vertexLabel = (index) => String(index + 1);\n"
        "}\n\n"
        "export const GENERATED_MODELS = DATA;\n"
        f"export const GENERATED_MODEL_ORDER = {json.dumps(list(model_map))};\n"
    )
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return len(model_map)
