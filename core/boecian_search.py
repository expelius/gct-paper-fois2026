"""Boecian search — search-as-maxim-application.

> "From a topos comes the maxim that warrants the inference."
> — Boethius, *De topicis differentiis*

In the Boecian tradition, each topos (locus) carries a maxim that licenses
inferences from premises located there. This module inverts the perspective:
**search itself becomes maxim-application**. A query is a hypothetical edge
(a missing relation we want to test); for each candidate target, we
construct the would-be edge, run the maxim's validator, and return the
candidates that pass with the strongest implications.

This is "find Y such that the maxim M is satisfied by edge X→Y[slot=S]".

Concrete example:

    Query: "find candidate genera for D-101 (under the CONTAINER maxim)"
    Source: D-101, slot: CONTAINER, direction: incoming
    For each node N at scale > D-101.scale:
        construct hypothetical edge N → D-101 [CONTAINER]
        run _validate_container(N → D-101)
        if no violation → N is a candidate genus
    Return ranked by some criterion (scale fit, semantic neighborhood, etc.)

This is the most ambitious of the four philosophical searches: search and
inference are unified. Each query is a small experiment in maxim-licensed
construction.
"""
from __future__ import annotations

from typing import Optional

from .builder import TensegrityGraph
from .schema import Confidence, Edge, Node, Slot, Layer
from .maxims import MAXIMS


# Direction of a slot: "incoming" means we're searching for SOURCES that
# could populate this slot at the query node; "outgoing" means TARGETS.
def _candidate_targets(graph_dict: dict,
                       source_id: str,
                       slot: Slot,
                       direction: str = "outgoing",
                       max_candidates: int = 100) -> list[str]:
    """Pre-filter candidate nodes by simple structural plausibility before
    running the full validator (which can be expensive)."""
    nodes = {n["id"]: n for n in graph_dict["nodes"]}
    src = nodes.get(source_id)
    if not src:
        return []
    src_scale = src.get("scale", 1)
    out = []
    for n in graph_dict["nodes"]:
        if n["id"] == source_id:
            continue
        # Skip functional / thermo holons by default — usually we want
        # structural-to-structural relations.
        if n.get("layer") not in ("structural", None):
            continue
        # Quick filter by slot semantics:
        if slot == Slot.CONTAINER:
            # CONTAINER edges go FROM container (higher scale) TO contained
            if direction == "outgoing":
                # We want targets at LOWER scale than source
                if (n.get("scale", 99)) >= src_scale: continue
            else:
                # We want sources at HIGHER scale
                if (n.get("scale", 0)) <= src_scale: continue
        elif slot == Slot.SUBSTRATE:
            # SUBSTRATE: substrate at LOWER scale than what it enables
            if direction == "outgoing":
                if (n.get("scale", 0)) >= src_scale: continue
            else:
                if (n.get("scale", 99)) <= src_scale: continue
        elif slot in (Slot.PEER_COHERENT, Slot.PEER_CONTRADICTORY):
            # Peers should be at same scale (within ±1 tolerated)
            if abs(n.get("scale", 0) - src_scale) > 1: continue
        # No other pre-filtering for CAUSE/EFFECT/SPECIFICATION/INSTANTIATION
        out.append(n["id"])
        if len(out) >= max_candidates:
            break
    return out


def maxim_search(graph_dict: dict,
                 source_id: str,
                 slot_name: str,
                 direction: str = "outgoing",
                 top_k: int = 15,
                 require_no_violations: bool = True) -> list[dict]:
    """For each candidate target, construct a hypothetical edge and ask whether
    the maxim's validator accepts it.

    Args:
        source_id: existing node from which the hypothetical edge starts (or ends, if direction=incoming).
        slot_name: one of the 12 slot names — the relation type to test
        direction: "outgoing" (source→target) or "incoming" (target→source)
        top_k: max results to return
        require_no_violations: if True, filter to edges that pass the validator with 0 violations

    Returns ranked list of {target_id, label, would_pass, n_violations,
    violations, fires_inferences}.
    """
    try:
        slot = Slot[slot_name.upper()]
    except KeyError:
        return [{"error": f"unknown slot '{slot_name}'"}]
    maxim = MAXIMS.get(slot)
    if not maxim or not maxim.validation_rule:
        return [{"error": f"slot {slot.name} has no validator (no maxim grounding)"}]

    # Build a transient graph that mirrors the snapshot just enough for the
    # validator to run. We need _nodes/_edges + node objects with scale +
    # active_since accessible. Reusing TensegrityGraph here for fidelity.
    g = TensegrityGraph()
    layers_map = {"structural": Layer.STRUCTURAL,
                  "functional": Layer.FUNCTIONAL,
                  "thermodynamic": Layer.THERMODYNAMIC}
    # Inject source + candidate nodes into the transient graph
    nodes_idx = {n["id"]: n for n in graph_dict["nodes"]}
    needed_ids = {source_id} | set(_candidate_targets(graph_dict, source_id, slot, direction))
    for nid in needed_ids:
        n = nodes_idx.get(nid)
        if not n:
            continue
        try:
            node = Node(
                id=n["id"], label=n.get("label", ""),
                scale=n.get("scale", 1),
                layer=layers_map.get(n.get("layer", "structural"), Layer.STRUCTURAL),
                metadata=n.get("metadata") or {},
            )
            node.active_since = n.get("active_since", "")
            g.add_node(node)
        except Exception:
            continue

    out = []
    for cand_id in needed_ids - {source_id}:
        if direction == "outgoing":
            edge = Edge(source=source_id, target=cand_id, slot=slot,
                        confidence=Confidence.INFERRED,
                        scale_from=g._nodes[source_id].scale,
                        scale_to=g._nodes[cand_id].scale,
                        evidence=f"hypothetical edge for boecian search")
        else:
            edge = Edge(source=cand_id, target=source_id, slot=slot,
                        confidence=Confidence.INFERRED,
                        scale_from=g._nodes[cand_id].scale,
                        scale_to=g._nodes[source_id].scale,
                        evidence=f"hypothetical edge for boecian search")
        # Run the validator on this hypothetical
        try:
            violations = maxim.validation_rule(g, edge)
        except Exception as e:
            violations = [f"validator threw: {e}"]
        passes = len(violations) == 0
        if require_no_violations and not passes:
            continue
        # Inference fire?
        inference_proposals = []
        if maxim.inference_rule:
            try:
                inference_proposals = maxim.inference_rule(g, edge)
            except Exception:
                pass
        cand = nodes_idx.get(cand_id, {})
        out.append({
            "candidate_id": cand_id,
            "label": (cand.get("label") or "")[:80],
            "scale": cand.get("scale"),
            "layer": cand.get("layer"),
            "would_pass": passes,
            "n_violations": len(violations),
            "violations_sample": [v[:120] for v in violations[:2]],
            "n_inferences_fired": len(inference_proposals),
        })
    # Rank: passers first, by absence of violations + presence of inferences fired
    out.sort(key=lambda x: (not x["would_pass"],
                             x["n_violations"],
                             -x["n_inferences_fired"]))
    return out[:top_k]


def boecian_summary(graph_dict: dict, node_id: str) -> dict:
    """Run boecian_search across ALL slots that have validators, for the given
    node. Returns a summary of which slots can absorb candidate edges and how
    many candidates pass the validator for each."""
    out = {"node": node_id, "by_slot": {}}
    for slot, maxim in MAXIMS.items():
        if not maxim.validation_rule:
            continue
        try:
            results = maxim_search(graph_dict, node_id, slot.name,
                                   direction="outgoing", top_k=5,
                                   require_no_violations=True)
        except Exception:
            continue
        if results and "error" not in results[0]:
            out["by_slot"][slot.name] = {
                "maxim": maxim.classical_name,
                "n_candidates_passing": len(results),
                "top_3": [
                    {"id": r["candidate_id"], "label": r["label"][:50]}
                    for r in results[:3]
                ],
            }
    return out


# ---- This module's own __holon__ ----
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="boecian_search",
    scale=1,
    aristotelian_cause="formal",
    container=["core"],
    substrate=["core.schema", "core.builder", "core.maxims"],
    effect=["candidate edges that satisfy a given maxim — search becomes inference"],
    description="Boecian search: each query is a hypothetical edge tested against the maxim layer",
)
