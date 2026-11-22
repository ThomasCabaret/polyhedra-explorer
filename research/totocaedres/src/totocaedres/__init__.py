"""Topological search and geometric realization of generalized polyhedra."""

from .model import SurfaceMap, TopologyReport
from .planner import FeasibleSignature, plan_principal_search

__all__ = [
    "FeasibleSignature",
    "SurfaceMap",
    "TopologyReport",
    "plan_principal_search",
]

__version__ = "0.2.0"
