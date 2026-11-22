from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .exact_geometry import ExactGeometryCertificate, certify_rational_planes
from .model import SurfaceMap


@dataclass(frozen=True)
class PositiveControl:
    control_id: str
    description: str
    source: str
    surface: SurfaceMap
    certificate_planes: tuple[tuple[int | str, ...], ...]


def load_positive_controls(path: str | Path) -> tuple[PositiveControl, ...]:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema") != "totocaedres.positive-controls.v1":
        raise ValueError("unsupported positive-control schema")
    controls: list[PositiveControl] = []
    for row in data["controls"]:
        surface = SurfaceMap.from_unoriented_face_vertices(
            [[list(boundary)] for boundary in row["faces"]]
        )
        controls.append(
            PositiveControl(
                control_id=row["id"],
                description=row["description"],
                source=row["source"],
                surface=surface,
                certificate_planes=tuple(tuple(plane) for plane in row["certificate_planes"]),
            )
        )
    return tuple(controls)


def verify_positive_controls(
    path: str | Path,
) -> tuple[tuple[PositiveControl, ExactGeometryCertificate], ...]:
    return tuple(
        (control, certify_rational_planes(control.surface, control.certificate_planes))
        for control in load_positive_controls(path)
    )
