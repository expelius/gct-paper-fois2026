"""Porphyrian search — taxonomic browsing via the genus/species tree.

> "Genus is predicated of the species; species of the individual."
> — Porphyry's *Isagoge*, the ancient template of taxonomic hierarchy.

The IVM CONTAINER slot in our schema IS the Porphyrian genus relation:
edge X→Y[CONTAINER] means X is the genus of Y (Y is a species under X).
This module exposes that hierarchy as taxonomic operations:

  - genus_of(N):     the genera (CONTAINER parents) of N
  - species_of(N):   the species (CONTAINER children) of N — what N contains
  - siblings_of(N):  other species under the same genus as N
  - ancestors_of(N): full path from N up to root genera
  - descendants_of(N): full subtree under N

This is structural traversal — no embeddings, no scoring, no neural model.
Just the Porphyrian Tree the graph already declares.
"""
from __future__ import annotations

from collections import deque


def _index(graph_dict: dict) -> dict:
    return {n["id"]: n for n in graph_dict["nodes"]}


def genus_of(graph_dict: dict, node_id: str) -> list[dict]:
    """Return the genera (CONTAINER parents) of the node.

    Convention: edge source→target[CONTAINER] means source is the container
    (genus), target is the contained (species). So a node's genera are the
    SOURCES of incoming CONTAINER edges.
    """
    nodes = _index(graph_dict)
    out = []
    for e in graph_dict["edges"]:
        if e["target"] == node_id and e["slot"] == "CONTAINER":
            g = nodes.get(e["source"])
            if g:
                out.append({
                    "id": g["id"],
                    "label": (g.get("label") or "")[:80],
                    "scale": g.get("scale"),
                    "via_edge_evidence": e.get("evidence", "")[:120],
                })
    return out


def species_of(graph_dict: dict, node_id: str) -> list[dict]:
    """Return the species (CONTAINER children) of the node.

    The TARGETS of outgoing CONTAINER edges from this node.
    """
    nodes = _index(graph_dict)
    out = []
    for e in graph_dict["edges"]:
        if e["source"] == node_id and e["slot"] == "CONTAINER":
            s = nodes.get(e["target"])
            if s:
                out.append({
                    "id": s["id"],
                    "label": (s.get("label") or "")[:80],
                    "scale": s.get("scale"),
                    "via_edge_evidence": e.get("evidence", "")[:120],
                })
    return out


def siblings_of(graph_dict: dict, node_id: str) -> list[dict]:
    """Return sibling species (other species under any of N's genera).

    A sibling is any node that shares at least one genus with the query node.
    Returned with `shared_genera` showing which genera grounded the sibling
    relationship.
    """
    nodes = _index(graph_dict)
    my_genera = {g["id"] for g in genus_of(graph_dict, node_id)}
    if not my_genera:
        return []
    siblings: dict[str, set[str]] = {}    # sibling_id → set of shared genus ids
    for e in graph_dict["edges"]:
        if e["slot"] != "CONTAINER":
            continue
        if e["source"] not in my_genera:
            continue
        if e["target"] == node_id:
            continue
        siblings.setdefault(e["target"], set()).add(e["source"])
    out = []
    for sid, sg in sorted(siblings.items(), key=lambda kv: -len(kv[1])):
        s = nodes.get(sid)
        if not s:
            continue
        out.append({
            "id": sid,
            "label": (s.get("label") or "")[:80],
            "scale": s.get("scale"),
            "n_shared_genera": len(sg),
            "shared_genera": sorted(sg),
        })
    return out


def ancestors_of(graph_dict: dict, node_id: str, max_depth: int = 8) -> list[list[dict]]:
    """BFS upward through CONTAINER edges; returns ancestry layers.

    Returns a list-of-lists: layers[0] = direct genera, layers[1] = grand-genera,
    etc., until max_depth or no further parents.
    """
    layers: list[list[dict]] = []
    seen = {node_id}
    frontier = {node_id}
    for _ in range(max_depth):
        next_layer = []
        next_frontier = set()
        for nid in frontier:
            for g in genus_of(graph_dict, nid):
                if g["id"] in seen:
                    continue
                seen.add(g["id"])
                next_layer.append(g)
                next_frontier.add(g["id"])
        if not next_layer:
            break
        layers.append(next_layer)
        frontier = next_frontier
    return layers


def descendants_of(graph_dict: dict, node_id: str, max_depth: int = 4) -> list[list[dict]]:
    """BFS downward through CONTAINER edges; returns descent layers.

    Returns layers[0] = direct species, layers[1] = grand-species, etc.
    """
    layers: list[list[dict]] = []
    seen = {node_id}
    frontier = {node_id}
    for _ in range(max_depth):
        next_layer = []
        next_frontier = set()
        for nid in frontier:
            for s in species_of(graph_dict, nid):
                if s["id"] in seen:
                    continue
                seen.add(s["id"])
                next_layer.append(s)
                next_frontier.add(s["id"])
        if not next_layer:
            break
        layers.append(next_layer)
        frontier = next_frontier
    return layers


def porphyrian_summary(graph_dict: dict, node_id: str) -> dict:
    """One-shot taxonomic profile of a node: ancestors + siblings + descendants."""
    nodes = _index(graph_dict)
    n = nodes.get(node_id)
    if not n:
        return {"error": f"node '{node_id}' not found"}
    return {
        "node": {
            "id": node_id,
            "label": (n.get("label") or "")[:80],
            "scale": n.get("scale"),
        },
        "genera": genus_of(graph_dict, node_id),
        "species": species_of(graph_dict, node_id),
        "siblings": siblings_of(graph_dict, node_id),
        "ancestor_layers": ancestors_of(graph_dict, node_id),
    }


# ---- This module's own __holon__ ----
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="porphyrian_search",
    scale=1,
    aristotelian_cause="formal",
    container=["core"],
    substrate=["core.schema"],
    effect=["genus / species / siblings / ancestors traversals over CONTAINER edges"],
    description="Porphyrian Tree taxonomic browsing — pure structural traversal of the genus hierarchy",
)
