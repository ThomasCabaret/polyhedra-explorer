from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import SurfaceMap


def read_surface(path: str | Path) -> SurfaceMap:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if "surface" in data:
        data = data["surface"]
    elif "results" in data:
        if not data["results"]:
            raise ValueError("the enumeration file contains no maps")
        data = data["results"][0]["surface"]
    return SurfaceMap.from_dict(data)


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
