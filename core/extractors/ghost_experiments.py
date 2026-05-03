"""Ghost experiment extractor — reconciles disk results vs EXPERIMENTS-LOG.

Scans FASE 5/results_d*/ for result directories, then compares against the
D-IDs already registered in the graph (by the experiments_log extractor).
Any D-ID found on disk but absent from the graph gets a ghost_experiment node.

Ghost nodes are:
  - node_type = "ghost_experiment"
  - state     = "UNREGISTERED"
  - scale     = 1  (same as registered experiments)
  - layer     = STRUCTURAL

This turns invisible absences into visible, queryable graph nodes. The
carousel renders them in an alert color (handled via node_type in polyhedra
rules); `kg_find ghost` lists them; `kg_violations` can surface them as
schema gaps. The intended workflow:
  1. At session start, the SessionStart hook already shows the delta as text
  2. The graph additionally makes them browsable as first-class nodes
  3. The user inspects, then either backfills EXPERIMENTS-LOG or deletes orphan

REQUIRES: ["experiments_log"] — must run after the log extractor so we can
check which D-IDs are already in the graph and avoid duplicates.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Layer, Node
from ..workspace_config import WorkspaceConfig

REQUIRES: list[str] = ["experiments_log"]

# Load config once at import time (fast — just discovers the TOML file)
_cfg = WorkspaceConfig.load(start=Path(__file__).parent)


def extract(graph) -> dict:
    """Add ghost_experiment nodes for results directories with no log entry."""
    disk_dids = _cfg.scan_results_dids()
    if not disk_dids:
        return {
            "extractor": "ghost_experiments",
            "skipped":   "no results dirs found",
            "nodes_added": 0, "edges_added": 0,
        }

    already_registered: set[str] = set(graph._nodes.keys())
    n_scanned = len(disk_dids)
    n_ghost   = 0
    n_skip    = 0

    for did, entry in sorted(disk_dids.items()):
        if did in already_registered:
            n_skip += 1
            continue

        json_files = list(entry.glob("*.json"))
        n_json  = len(json_files)
        n_files = sum(1 for _ in entry.iterdir())

        ghost = Node(
            id=did,
            label=f"{did} [GHOST] {entry.name}",
            scale=1,
            layer=Layer.STRUCTURAL,
            active_since=None,
            metadata={
                "node_type":     "ghost_experiment",
                "state":         "UNREGISTERED",
                "results_dir":   entry.name,
                "n_json_files":  n_json,
                "n_total_files": n_files,
                "note": (
                    "Results exist on disk but no EXPERIMENTS-LOG row. "
                    "Register via `python run_exp.py <script>` or add a "
                    "manual backfill row to EXPERIMENTS-LOG.md §3.5."
                ),
            },
        )
        try:
            graph.add_node(ghost)
            n_ghost += 1
        except Exception:
            n_skip += 1

    return {
        "extractor":     "ghost_experiments",
        "dirs_scanned":  n_scanned,
        "nodes_added":   n_ghost,
        "edges_added":   0,
        "already_known": n_skip,
        "config_source": str(_cfg.toml_path or "defaults"),
    }


# ---- This module's own __holon__ ----
from ..holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="ghost_experiments",
    scale=1,
    aristotelian_cause="efficient",
    container=["core.extractors"],
    substrate=["core.schema"],
    effect=["ghost_experiment nodes for unregistered result directories"],
    description=(
        "Reconciles disk results_d*/ vs EXPERIMENTS-LOG: unregistered "
        "experiments become ghost_experiment nodes, making absences visible."
    ),
)
