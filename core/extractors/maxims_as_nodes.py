"""maxims_as_nodes — promote the 12 Boethian/Aristotelian maxims to first-class nodes.

Until this extractor, the 12 maxims lived only in `core/maxims.py` as a
registry consulted externally by `validate_graph()` / `infer_missing_edges()`.
This extractor materializes them as actual Node objects in the graph, with
the existing edge `slot` field acting as the (denormalized) type-pointer
back to its governing maxim.

Why this matters:

  - The graph now contains its own structural laws as data, not just code.
  - Maxims become navigable, citable, and subject to the same validation/
    consolidation machinery as any other holon.
  - The reciprocal-pair structure of the IVM (6 polar axes) is encoded
    explicitly as PEER_COHERENT edges between dual maxims (e.g.,
    CONTAINER↔SUBSTRATE; CAUSE↔EFFECT).
  - Consumers (carousel, query_graph) can query "all instances of maxim X"
    via the existing edge-slot index — no new edge type needed.

Design choice: do NOT add per-edge SPECIFICATION/INSTANTIATION edges from
every governed edge to its maxim. That would multiply the graph's edge
count by ~3× and would distort the existing slot-saturation / VE / asymmetry
metrics (since every node would suddenly have many SPECIFICATION-slot
populations). Instead, the existing `edge.slot` field IS the type pointer;
maxim "instances" are computed on demand by querying edges with matching
slot. The maxim nodes themselves carry only their ontological metadata +
PEER edges to their reciprocal partners.

Each maxim node:
  - id:    "maxim_<slot_name_lowercase>"  (e.g., "maxim_container")
  - scale: 4                              (universal — governs all scales)
  - layer: STRUCTURAL                     (laws are structure, not function)
  - metadata: latin_form, english_form, classical_name, governs_slot,
              has_validation_rule, has_inference_rule

Reciprocal pairs (6 PEER_COHERENT edges):
  SUCCESSOR ↔ PREDECESSOR     (temporal axis)
  SUBSTRATE ↔ CONTAINER       (vertical axis)
  PEER_COHERENT ↔ PEER_CONTRADICTORY  (lateral axis — duals as PEER)
  CODE ↔ THERMO               (halves axis)
  CAUSE ↔ EFFECT              (causal axis)
  SPECIFICATION ↔ INSTANTIATION  (type axis)
"""
from __future__ import annotations

from ..maxims import MAXIMS
from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['project_graph']   # extractors that must run before this one


def _slug(slot: Slot) -> str:
    return f"maxim_{slot.name.lower()}"


# The 6 polar axes of the IVM cuboctahedron — used for PEER_COHERENT
# wiring between dual maxims.
RECIPROCAL_PAIRS = [
    (Slot.SUCCESSOR, Slot.PREDECESSOR),
    (Slot.SUBSTRATE, Slot.CONTAINER),
    (Slot.PEER_COHERENT, Slot.PEER_CONTRADICTORY),
    (Slot.CODE, Slot.THERMO),
    (Slot.CAUSE, Slot.EFFECT),
    (Slot.SPECIFICATION, Slot.INSTANTIATION),
]


def extract(graph) -> dict:
    nodes_added = 0
    edges_added = 0

    # Step 1 — create the 12 maxim nodes
    for slot, maxim in MAXIMS.items():
        nid = _slug(slot)
        if nid in graph._nodes:
            continue
        graph.add_node(Node(
            id=nid,
            label=f"Maxim: {maxim.classical_name}",
            scale=4,                         # universal — sits at project scale
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "maxim",
                "governs_slot": slot.name,
                "slot_number": slot.number,
                "classical_name": maxim.classical_name,
                "latin_form": maxim.latin_form,
                "english_form": maxim.english_form,
                "has_validation_rule": maxim.validation_rule is not None,
                "has_inference_rule": maxim.inference_rule is not None,
                "axis": slot.axis,
                "polarity": slot.polarity,
                "mechanical": slot.mechanical,
                "aristotelian_cause": slot.aristotelian_cause,
                "source": "core/maxims.py registry — Boethius / Porphyry / Aristotle",
            },
        ))
        nodes_added += 1

    # Step 2 — wire the 6 reciprocal pairs as PEER_COHERENT (slot 5)
    # Note: PEER_COHERENT goes both ways structurally (the slot is symmetric);
    # add only one direction per pair to avoid double-counting.
    for slot_a, slot_b in RECIPROCAL_PAIRS:
        a = _slug(slot_a)
        b = _slug(slot_b)
        if a not in graph._nodes or b not in graph._nodes:
            continue
        try:
            graph.add_edge(Edge(
                source=a, target=b,
                slot=Slot.PEER_COHERENT,
                confidence=Confidence.EXTRACTED,
                scale_from=4, scale_to=4,
                evidence=f"reciprocal IVM dual: {slot_a.axis}-axis pair "
                         f"({slot_a.polarity} ↔ {slot_b.polarity})",
            ))
            edges_added += 1
        except (KeyError, ValueError):
            continue

    # Step 3 — wire each maxim to the project root via SUBSTRATE (cable, vertical+).
    # Says: the maxim is materially part of the project's structural ground.
    # Only if the project node exists.
    if "tensegrity_project" in graph._nodes:
        for slot in MAXIMS:
            mid = _slug(slot)
            try:
                graph.add_edge(Edge(
                    source=mid, target="tensegrity_project",
                    slot=Slot.SUBSTRATE,
                    confidence=Confidence.EXTRACTED,
                    scale_from=4, scale_to=4,
                    evidence=f"the {slot.name} maxim is part of the structural ground "
                             f"upon which the project's IVM-governed graph rests",
                ))
                edges_added += 1
            except (KeyError, ValueError):
                continue

    return {
        "extractor": "maxims_as_nodes",
        "files_processed": 0,           # no files — pure schema-derived
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "axes_wired": len(RECIPROCAL_PAIRS),
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='maxims_as_nodes',
    scale=2,
    aristotelian_cause='formal',
    container=['core.extractors'],
    substrate=['core.maxims'],
    effect=['12 maxim nodes at scale 4 + reciprocal pairs'],
)
