"""holonic-graph — IVM-schema knowledge graph with self-referential code holons.

PUBLIC API (use from external projects):

    from core import (
        # ---- Schema (the 12-slot IVM cuboctahedron + 5 scales + 3 layers) ----
        Slot, Confidence, Layer, Node, Edge, HARMONIC_CEILING_BY_SCALE,

        # ---- Graph builder ----
        TensegrityGraph,                  # the holonic graph state
        HolonicGraph,                     # alias — recommended for new projects

        # ---- Maxim layer (12 Boethian/Aristotelian validators + inference) ----
        MAXIMS,                           # registry: dict[Slot, Maxim]
        validate_graph,                   # → list of violations
        validate_graph_with_coverage,     # → {violations, n_checked, n_unable, n_no_rule}
        infer_missing_edges,              # → list of inference proposals
        maxim_summary,                    # → list of maxim metadata dicts

        # ---- Code-holon self-annotation ----
        HolonMeta,                        # decorate modules with __holon__ = HolonMeta(...)

        # ---- Extractor framework ----
        run_all,                          # run all registered extractors with provenance stamping
        build_extractor_order,            # topological sort over REQUIRES declarations
    )

QUICKSTART:

    from core import HolonicGraph, Node, Edge, Layer, Slot, Confidence, validate_graph

    g = HolonicGraph()
    with g.with_provenance("my_extractor"):
        g.add_node(Node(id="paper_p1", label="Paper P1", scale=2, layer=Layer.STRUCTURAL))
        g.add_node(Node(id="d_001",    label="D-001",    scale=1, layer=Layer.STRUCTURAL))
        g.add_edge(Edge(source="paper_p1", target="d_001",
                        slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED))

    # Validate against the 12 maxims
    for v in validate_graph(g):
        print(v["maxim"], "—", v["violation"])

    # Save snapshot
    g.save("my_graph.json")

For the full Tensegrity research instrument (with extractors for paper drafts,
experiment logs, OSF pre-registrations, etc.), see the project's main README.
"""

# ---- Schema ----
from .schema import (
    Slot, Confidence, Layer, Node, Edge, HARMONIC_CEILING_BY_SCALE,
    validate_node, validate_edge,
)

# ---- Graph ----
from .builder import TensegrityGraph
HolonicGraph = TensegrityGraph    # canonical alias for non-Tensegrity uses

# ---- Maxims ----
from .maxims import (
    MAXIMS,
    Maxim,
    validate_graph,
    validate_graph_with_coverage,
    infer_missing_edges,
    maxim_summary,
)

# ---- Holon meta (code-as-holon self-annotation) ----
from .holon_meta import HolonMeta

# ---- Extractor framework ----
from .extractors._base import build_extractor_order, ExtractorModule
from .extractors import run_all, EXTRACTORS_IN_ORDER

# ---- Viz pre-compute (for consumers building their own UI) ----
from .viz_precompute import (
    enrich_viz,
    compute_connected_components,
    compute_citation_edges,
    compute_dominant_polyhedron,
)

__version__ = "0.1.0"

__all__ = [
    # Schema
    "Slot", "Confidence", "Layer", "Node", "Edge", "HARMONIC_CEILING_BY_SCALE",
    "validate_node", "validate_edge",
    # Graph
    "TensegrityGraph", "HolonicGraph",
    # Maxims
    "MAXIMS", "Maxim", "validate_graph", "validate_graph_with_coverage",
    "infer_missing_edges", "maxim_summary",
    # Holon meta
    "HolonMeta",
    # Extractors
    "build_extractor_order", "ExtractorModule", "run_all", "EXTRACTORS_IN_ORDER",
    # Viz pre-compute
    "enrich_viz", "compute_connected_components",
    "compute_citation_edges", "compute_dominant_polyhedron",
    # Version
    "__version__",
]


# ---- This package's own __holon__ (top-level core) ----
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="core",
    scale=3,
    aristotelian_cause="formal",
    description="Holonic knowledge graph package — schema + builder + maxims + extractors + holon-meta self-annotation",
    container=[],   # top-level — no parent module
)
