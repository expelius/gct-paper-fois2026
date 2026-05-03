"""Extractor for results_*/*.json files — produces JSONResult thermodynamic nodes (s0).

Each results JSON corresponds to a D-XXX experiment's measurement output.
Creates a thermodynamic node referring back to the structural D-XXX.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log']   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
RESULTS_GLOB_DIRS = [
    PROJECT_ROOT / "LINEAS DE INVESTIGACIÓN" / "LINEA A" / "FASE 5",
    PROJECT_ROOT / "LINEAS DE INVESTIGACIÓN" / "LINEA A" / "FASE 4",
]

DID_FROM_PATH_RE = re.compile(r"d(\d{3})[a-z]?", re.IGNORECASE)


def _did_from_path(path: Path) -> str | None:
    """Try to extract D-ID from path components."""
    for part in path.parts:
        m = DID_FROM_PATH_RE.search(part)
        if m:
            return f"D-{m.group(1)}"
    name_m = DID_FROM_PATH_RE.search(path.stem)
    if name_m:
        return f"D-{name_m.group(1)}"
    return None


def _extract_anchor(jf: Path, graph) -> tuple[str | None, str]:
    """Find the structural anchor for a JSON file, in order of preference:

      1. D-XXX matched in path or filename (existing behavior)
      2. The PARENT DIRECTORY name treated as a research-run group (anchor
         to a synthetic 'run_xxx' node we create on the fly)
      3. None — orphan, will be anchored to a generic 'unanchored_results' bucket

    Returns (anchor_node_id, anchor_kind) where anchor_kind ∈
    {'d_id', 'directory_run', 'unanchored'}.
    """
    did = _did_from_path(jf)
    if did and did in graph._nodes:
        return did, "d_id"

    # Try the parent directory name (e.g., results_d033_lyapunov_spectrum →
    # synthetic run_d033_lyapunov_spectrum if we can't match D-033 directly)
    parent = jf.parent.name
    if parent and parent != "":
        run_id = "run_" + re.sub(r"[^a-z0-9_]+", "_", parent.lower()).strip("_")[:60]
        return run_id, "directory_run"

    return "unanchored_results", "unanchored"


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    nodes_added = 0
    edges_added = 0
    files_processed = 0
    anchor_stats = {"d_id": 0, "directory_run": 0, "unanchored": 0}

    # Pre-create the unanchored bucket node (a thermodynamic-layer holon
    # representing "results we couldn't trace to a specific experiment")
    if "unanchored_results" not in graph._nodes:
        graph.add_node(Node(
            id="unanchored_results",
            label="Unanchored results bucket",
            scale=1,
            layer=Layer.STRUCTURAL,
            metadata={"node_type": "results_bucket",
                      "description": "Holon for results JSONs with no D-ID inferable from path"},
        ))
        nodes_added += 1

    for base in RESULTS_GLOB_DIRS:
        if not base.exists():
            continue
        for jf in base.rglob("*.json"):
            try:
                with open(jf, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            files_processed += 1

            anchor_id, anchor_kind = _extract_anchor(jf, graph)
            anchor_stats[anchor_kind] += 1

            # If anchor is a synthetic directory_run, materialize it on first sight
            if anchor_kind == "directory_run" and anchor_id not in graph._nodes:
                graph.add_node(Node(
                    id=anchor_id,
                    label=f"Run group: {jf.parent.name[:60]}",
                    scale=1,
                    layer=Layer.STRUCTURAL,
                    metadata={
                        "node_type": "results_run_group",
                        "source_dir": str(jf.parent.relative_to(PROJECT_ROOT)),
                        "description": "Auto-created from results directory; no D-ID was inferable",
                    },
                ))
                nodes_added += 1

            # Build the JSON's own thermodynamic node
            rel = jf.relative_to(base)
            node_id = "json_" + re.sub(r"[^a-z0-9_]+", "_", str(rel).lower()).strip("_")[:80]
            if node_id in graph._nodes:
                continue
            top_keys = list(data.keys())[:8] if isinstance(data, dict) else []
            graph.add_node(Node(
                id=node_id,
                label=f"JSON: {jf.name[:60]}",
                scale=0,
                layer=Layer.THERMODYNAMIC,
                structural_ref=anchor_id,
                metadata={
                    "node_type": "json_result",
                    "source_file": str(jf.relative_to(PROJECT_ROOT)),
                    "top_level_keys": top_keys,
                    "is_dict": isinstance(data, dict),
                    "size_bytes": jf.stat().st_size,
                    "anchor_kind": anchor_kind,
                    "mtime_iso": _mtime_iso(jf),
                },
            ))
            nodes_added += 1
            try:
                graph.add_edge(Edge(
                    source=node_id, target=anchor_id,
                    slot=Slot.EFFECT, confidence=Confidence.EXTRACTED,
                    scale_from=0, scale_to=1,
                    evidence=f"results JSON {jf.name} produced by {anchor_id} ({anchor_kind})",
                ))
                edges_added += 1
            except (KeyError, ValueError):
                pass

    return {
        "extractor": "results_jsons",
        "files_processed": files_processed,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "anchor_stats": anchor_stats,
    }


def _mtime_iso(path: Path) -> str:
    """File mtime as ISO 8601 timestamp — useful for time-axis filtering."""
    from datetime import datetime
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return ""


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='results_jsons',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['thermodynamic JSON nodes + EFFECT edges + run_group anchors'],
)
