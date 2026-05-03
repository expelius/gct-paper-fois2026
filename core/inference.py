"""Inference + alignment + hermeneutic build module.

Three capabilities:

1. align_intent(graph, query)        — Idea2Story's intent alignment
   match underspecified user intent to existing ResearchPattern nodes
   instead of open-ended generation

2. compute_idea_fingerprints(graph)  — apply Wittgenstein use-over-essence
   compute fingerprint for every node based on relation pattern; identify
   nodes that share fingerprint despite different labels (synonym detection)

3. hermeneutic_build(graph, ...)     — iterative parts↔whole refinement
   first pass extracts atoms; second pass re-interprets atoms in light
   of computed clusters; iterate until convergence
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Optional, TYPE_CHECKING

from .schema import Layer, Node, Slot

if TYPE_CHECKING:
    from .builder import TensegrityGraph


# ============================================================================
# Idea fingerprints (Wittgenstein, item 1)
# ============================================================================


def compute_idea_fingerprints(graph: "TensegrityGraph") -> dict[str, str]:
    """Compute idea_fingerprint for every node in the graph.

    Returns dict node_id → fingerprint (16-char sha256 prefix).
    Two nodes with same fingerprint = same idea regardless of label.
    """
    fingerprints = {}
    for nid, node in graph._nodes.items():
        neighbor_ids = set(graph.G.successors(nid)) | set(graph.G.predecessors(nid))
        layer_sig = [graph._nodes[n].layer.value for n in neighbor_ids if n in graph._nodes]
        scale_sig = [graph._nodes[n].scale for n in neighbor_ids if n in graph._nodes]
        fp = node.compute_idea_fingerprint(
            neighbor_layer_signature=layer_sig,
            neighbor_scale_signature=scale_sig,
        )
        fingerprints[nid] = fp
    return fingerprints


def detect_synonyms_via_fingerprint(graph: "TensegrityGraph") -> list[dict]:
    """Find nodes with identical idea_fingerprint but different labels.

    These are CANDIDATE SYNONYMS — same idea pattern under different names.
    User reviews; not auto-merged.
    """
    fps = compute_idea_fingerprints(graph)
    by_fp: dict[str, list[str]] = defaultdict(list)
    for nid, fp in fps.items():
        by_fp[fp].append(nid)
    synonyms = []
    for fp, nids in by_fp.items():
        if len(nids) < 2:
            continue
        labels = [graph._nodes[n].label for n in nids]
        unique_labels = set(labels)
        if len(unique_labels) > 1:
            synonyms.append({
                "fingerprint": fp,
                "node_ids": nids,
                "labels": labels,
                "interpretation": (
                    f"{len(unique_labels)} distinct labels share identical relational "
                    f"pattern → candidate synonyms (Wittgenstein: same use, different word)"
                ),
            })
    return synonyms


# ============================================================================
# Intent alignment (Idea2Story, item 5d)
# ============================================================================


def align_intent(
    graph: "TensegrityGraph",
    query_keywords: list[str],
    top_k: int = 3,
) -> list[dict]:
    """Match underspecified user intent to existing ResearchPattern nodes.

    Idea2Story: instead of open-ended generation when user query is vague,
    align to a pre-built pattern. Reduces hallucination, accelerates
    paradigm reuse.

    Currently uses keyword overlap with pattern label + typical_use_cases.
    Future: embedding-based semantic match.
    """
    patterns = [
        n for n in graph._nodes.values()
        if n.metadata.get("node_type") == "research_pattern"
    ]
    if not patterns:
        return []

    keywords_lower = [k.lower() for k in query_keywords]
    scored = []
    for p in patterns:
        text_blob = (
            p.label.lower() + " " +
            " ".join(p.metadata.get("typical_use_cases", [])).lower() + " " +
            " ".join(p.metadata.get("members", [])).lower()
        )
        matches = sum(1 for kw in keywords_lower if kw in text_blob)
        if matches > 0:
            scored.append({
                "pattern_id": p.id,
                "pattern_label": p.label,
                "match_count": matches,
                "match_ratio": round(matches / len(keywords_lower), 3),
                "god_node": p.metadata.get("god_node_id"),
                "n_members": p.metadata.get("n_members", 0),
                "typical_use_cases": p.metadata.get("typical_use_cases", []),
            })
    scored.sort(key=lambda x: -x["match_count"])
    return scored[:top_k]


# ============================================================================
# Hermeneutic build (item 4)
# ============================================================================


def hermeneutic_build(
    graph: "TensegrityGraph",
    extract_atoms_fn: Callable[["TensegrityGraph"], None],
    reinterpret_fn: Callable[["TensegrityGraph"], int],
    cluster_fn: Optional[Callable[["TensegrityGraph"], None]] = None,
    max_passes: int = 5,
    convergence_threshold: float = 0.05,
) -> dict:
    """Iterative parts↔whole build (Schleiermacher/Gadamer hermeneutic circle).

    Args:
      graph              : TensegrityGraph (mutated in place)
      extract_atoms_fn   : callable that extracts atomic structural facts
                           into the graph (PASS 1; cheap)
      reinterpret_fn     : callable that re-classifies edges/nodes in light
                           of cluster context; returns count of changes made
      cluster_fn         : optional cluster-update callable run between passes
      max_passes         : hard cap on iterations
      convergence_threshold: stop when (changes_this_pass / total_edges) < threshold

    Returns:
      dict with pass-by-pass change counts and convergence status

    Workflow:
      1. extract_atoms_fn(graph)             — initial atomic extraction
      2. cluster_fn(graph) if provided       — compute initial clusters
      3. for pass in 1..max_passes:
           changes = reinterpret_fn(graph)   — re-interpret given context
           cluster_fn(graph) if provided     — re-cluster with new info
           if changes/total < threshold: break
    """
    log = []
    extract_atoms_fn(graph)
    log.append({"pass": 0, "phase": "extract_atoms", "n_edges": len(graph._edges)})

    if cluster_fn is not None:
        cluster_fn(graph)
        log.append({"pass": 0, "phase": "initial_cluster", "n_edges": len(graph._edges)})

    converged = False
    for p in range(1, max_passes + 1):
        n_edges_before = len(graph._edges)
        n_changes = reinterpret_fn(graph)
        n_edges_after = len(graph._edges)
        change_ratio = n_changes / max(1, n_edges_after)
        log.append({
            "pass": p,
            "phase": "reinterpret",
            "n_changes": n_changes,
            "n_edges_before": n_edges_before,
            "n_edges_after": n_edges_after,
            "change_ratio": round(change_ratio, 4),
        })
        if cluster_fn is not None:
            cluster_fn(graph)
        if change_ratio < convergence_threshold:
            converged = True
            break

    return {
        "converged": converged,
        "n_passes_run": len([l for l in log if l["phase"] == "reinterpret"]),
        "max_passes_allowed": max_passes,
        "convergence_threshold": convergence_threshold,
        "log": log,
        "interpretation": (
            "converged within threshold — interpretation stable"
            if converged else
            f"hit max_passes ({max_passes}) without convergence — investigate why context shifts so much"
        ),
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='inference',
    scale=1,
    aristotelian_cause='efficient',
    container=['core'],
    substrate=['core.schema', 'core.builder'],
    description='Hermeneutic-circle build pipeline + family resemblance + idea fingerprints',
)
