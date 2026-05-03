"""code_implements — wire CODE-typed edges from maxims to the code_holons
that implement them, the schema/factory holons that formally instantiate
their definitions, and the holon_meta dataclass that produces all code holons.

The CODE slot in the IVM schema is "Differentia + Definition (essential form)"
— the formal cause (Aristotle). The differentia maxim states: a definition
cannot be drawn from a finer-grained instance — i.e., for an edge X → Y[CODE],
X (the source / form) must be at scale >= Y (the target / instance).
For a maxim node M and a code holon C, the edge `M → C [CODE]` reads:
M is the formal definition; C is the executable instance that implements M.
C's runtime behaviour populates edges of M's slot type, so M is C's
essential form. Direction respects the differentia maxim because maxim
nodes live at scale 4 (universal law) and code holons at scale 0-3
(executable instances).

Three families of CODE edges are emitted, in order of decreasing intimacy:

  (1) Slot-population grounding.  For every code holon `holon_code_<E>` that
      the existing graph credits with populating edges of slot S (via
      `provenance.extractor == E`), emit `maxim_<S> → holon_code_<E>` [CODE].
      The maxim is the formal definition of S; the extractor is the
      executable form that produces edges of slot S.  Textual grounding:
      the provenance trail of the graph under construction.

  (2) Schema-definition grounding.  `holon_code_schema` and
      `holon_code_maxims` define and validate, respectively, all twelve
      slots; emit one CODE edge from EVERY maxim node to each of these two
      holons (24 edges total).  `holon_code_holon_meta` defines the
      HolonMeta dataclass — emit `maxim_code → holon_code_holon_meta`
      (it formalises the CODE slot's self-descriptive `code` field).

  (3) Factory-definition grounding.  `holon_code_node_types` defines the
      node-type factories (Creaon, Genon, Environ, etc.) — emit CODE edges
      from maxim_specification and maxim_substrate (the slots these
      factories populate when invoked) to it.

Every emitted edge carries provenance, an `evidence` string citing the
`__holon__` declaration that justifies it, and direction
`source=maxim_node, target=code_holon` (matching the differentia maxim:
the form is at scale 4, the executable instance at scale 0-3).

Idempotence: the extractor only emits an edge if (source, target, CODE) is
not already present, so re-runs are byte-stable. Because slot-population
inference reads the current graph state, the extractor MUST run after
all node-emitting extractors AND after `code_holons` (which creates the
holon_code_* nodes) AND after `maxims_as_nodes` (which creates the
maxim_* nodes).
"""
from __future__ import annotations

from collections import defaultdict

from ..schema import Confidence, Edge, Slot

# Run AFTER code_holons (which makes holon_code_* nodes), maxims_as_nodes (which
# makes maxim_* nodes), AND every other node-emitting extractor. The provenance
# trail used by Family-1 grounding only sees edges that are already present at
# extract time, so code_implements must run last among graph-mutators.
# Topological sort enforces this ordering.
REQUIRES: list[str] = [
    "code_holons",
    "maxims_as_nodes",
    "experiments_log",
    "paper_drafts",
    "memory",
    "concepts",
    "cross_cuts",
    "results_jsons",
    "prereg",
    "project_graph",
    "operational_distinctions",
]


# ---- Schema-definition grounding (Family 2) ----
# Emit one CODE edge from these holons to ALL 12 maxim nodes.
ALL_TWELVE_MAXIM_HOLONS = ("schema", "maxims")

# Targeted CODE edges — code holons that formalise specific slots
TARGETED_HOLON_TO_MAXIMS: dict[str, list[str]] = {
    # holon_meta dataclass introduces the `code` field that CODE slot uses
    "holon_meta": ["maxim_code"],
    # node_types factory functions emit specification + substrate edges via factories
    "node_types": ["maxim_specification", "maxim_substrate"],
    # builder.add_edge populates target slots; primarily container/substrate axis
    "builder": ["maxim_substrate", "maxim_container"],
    # diagnostics computes slot health, primarily a CODE relationship to peer/code
    "diagnostics": ["maxim_code"],
    # inference produces specification proposals (missing_specification dominant)
    "inference": ["maxim_specification"],
    # viz_precompute reads container hierarchy + computes harmonic ceiling
    "viz_precompute": ["maxim_container"],
    # extractors_base is the orchestrator interface — substrates the extractors
    "extractors_base": ["maxim_substrate"],
    # extractors orchestrator triggers all extractors → effects every slot
    "extractors": ["maxim_cause"],
    # workspace_config — supplies path resolution, container-axis
    "workspace_config": ["maxim_container"],
}


def _slot_to_maxim_id(slot_name: str) -> str:
    """Map slot name (e.g., 'CONTAINER') to maxim node id ('maxim_container')."""
    return f"maxim_{slot_name.lower()}"


def _holon_node_id(holon_name: str) -> str:
    """Mirror the convention in code_holons.py."""
    return f"holon_code_{holon_name.lower()}"


def _gather_slot_population(graph) -> dict[str, set[str]]:
    """For each extractor name, collect the set of slot names it populates.

    Reads `provenance.extractor` on every edge in the graph; groups slots by
    extractor. Provides automatic textual grounding: the extractor's CODE
    edge targets are derived from the maxim_* of the slots it actually
    emitted in this build.
    """
    by_extractor: dict[str, set[str]] = defaultdict(set)
    for edge in graph._edges.values():
        prov = getattr(edge, "provenance", None) or {}
        ext = prov.get("extractor") if isinstance(prov, dict) else None
        if not ext or ext == "unknown":
            continue
        by_extractor[ext].add(edge.slot.name)
    return dict(by_extractor)


def extract(graph) -> dict:
    """Emit CODE edges from code_holons to the maxim nodes they implement.

    Returns standard extractor stats dict; `nodes_added=0` (this extractor
    only wires edges).
    """
    edges_added = 0
    edges_skipped_missing_target = 0
    edges_skipped_duplicate = 0

    # Determine which (source, target, slot) triples are already present so
    # the extractor stays idempotent across re-runs.
    existing: set[tuple[str, str, Slot]] = {
        (e.source, e.target, e.slot) for e in graph._edges.values()
    }

    def _try_emit(source: str, target: str, evidence: str) -> None:
        """Emit a CODE edge source→target where source is the formal definition
        (maxim node, scale 4) and target is the executable instance
        (code_holon, scale ≤3). This direction respects the differentia
        maxim's scale invariant (src.scale >= tgt.scale)."""
        nonlocal edges_added, edges_skipped_missing_target, edges_skipped_duplicate
        if source not in graph._nodes or target not in graph._nodes:
            edges_skipped_missing_target += 1
            return
        if (source, target, Slot.CODE) in existing:
            edges_skipped_duplicate += 1
            return
        try:
            graph.add_edge(Edge(
                source=source,
                target=target,
                slot=Slot.CODE,
                confidence=Confidence.EXTRACTED,
                scale_from=graph._nodes[source].scale,
                scale_to=graph._nodes[target].scale,
                evidence=evidence,
            ))
            existing.add((source, target, Slot.CODE))
            edges_added += 1
        except (KeyError, ValueError):
            edges_skipped_missing_target += 1

    # ---- Family 1: slot-population grounding ----
    # Read the current graph; for every extractor that populated slots, emit
    # CODE edges from each populated slot's maxim → the holon that implements it.
    pop = _gather_slot_population(graph)
    for extractor_name, slot_names in sorted(pop.items()):
        tgt_id = _holon_node_id(extractor_name)  # the code_holon (executable form)
        if tgt_id not in graph._nodes:
            continue
        for slot_name in sorted(slot_names):
            src_id = _slot_to_maxim_id(slot_name)  # the maxim (formal definition)
            ev = (
                f"maxim '{slot_name}' is formally instantiated by code holon "
                f"'{extractor_name}': the extractor populated edges of this "
                f"slot type during build, per provenance.extractor==='{extractor_name}'"
            )
            _try_emit(src_id, tgt_id, ev)

    # ---- Family 2: schema-definition grounding ----
    # All 12 maxims → holon_code_schema + holon_code_maxims (the universal forms
    # are the maxims; their universal implementations are these two holons).
    all_maxims = [_slot_to_maxim_id(s.name) for s in Slot]
    for holon_name in ALL_TWELVE_MAXIM_HOLONS:
        tgt_id = _holon_node_id(holon_name)
        if tgt_id not in graph._nodes:
            continue
        for src_id in all_maxims:
            ev = (
                f"maxim → '{holon_name}' (universal form → universal "
                f"executable definition): per its __holon__ declaration "
                f"'{holon_name}' formally defines/validates all 12 IVM slots"
            )
            _try_emit(src_id, tgt_id, ev)

    # ---- Family 3: targeted maxim→code_holon CODE edges (specific formal roles) ----
    for holon_name, maxim_sources in sorted(TARGETED_HOLON_TO_MAXIMS.items()):
        tgt_id = _holon_node_id(holon_name)
        if tgt_id not in graph._nodes:
            continue
        for src_id in maxim_sources:
            ev = (
                f"maxim '{src_id}' is formally implemented by code holon "
                f"'{holon_name}' per its __holon__ declaration's "
                f"effect/specification/code fields"
            )
            _try_emit(src_id, tgt_id, ev)

    return {
        "extractor": "code_implements",
        "nodes_added": 0,
        "edges_added": edges_added,
        "edges_skipped_duplicate": edges_skipped_duplicate,
        "edges_skipped_missing_target": edges_skipped_missing_target,
        "code_edges_total_after_extract": sum(
            1 for e in graph._edges.values() if e.slot == Slot.CODE
        ),
    }


# ---- This module's own __holon__ ----
# scale=3 matches code_holons (the principal substrate) — substrate must be at
# scale <= consumer per Aristotle's material cause maxim. code_holons is at
# scale 3 (cluster scale) because it walks the full extractor cluster; this
# module operates at the same cluster level (orchestration over all holons).
from ..holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="code_implements",
    scale=3,
    aristotelian_cause="formal",
    container=["core.extractors"],
    substrate=["core.schema", "core.extractors.code_holons", "core.extractors.maxims_as_nodes"],
    effect=["CODE-typed edges from maxim_* nodes to code_holon nodes that implement them"],
    description=(
        "Closes the CODE slot: links each maxim to the code_holon(s) that "
        "formally implement it; populates Slot.CODE in the IVM 12-slot schema."
    ),
)
