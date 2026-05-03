"""HolonMeta — declarative IVM-slot annotation for code modules.

This module enables the maximalist move: organizing the project's CODE itself
as IVM holons. Each module declares a `__holon__ = HolonMeta(...)` block at
the top describing its 12-slot relations to other modules. The
`code_holons.py` extractor then reads all these declarations and emits them
as nodes+edges into the knowledge graph, where the same maxim-validation
machinery that audits research data also audits the code's structural
coherence.

Usage in a module:

    from core.holon_meta import HolonMeta

    __holon__ = HolonMeta(
        name="experiments_log",
        scale=3,                                          # code-cluster scale
        container="core.extractors",                      # genus / Porfirio
        substrate=["core.schema", "core.builder"],        # material cause
        code="extract(graph) -> dict",                    # essential differentia
        cause=["core.extractors.run_all"],                # what triggers it
        effect=["D-XXX nodes at structural/s1"],          # what it produces
        peer_coherent=["prereg", "cross_cuts"],           # similar modules
        specification="ExtractorModule protocol",         # formal interface
        aristotelian_cause="material",
    )

The 12 slots correspond to the IVM cuboctahedron axes (see core/schema.py).
Empty/missing slots are tolerated — extracted as "no declaration" rather
than "no relation".

Convention: `name` is the short-name (last `.`-separated component of the
module path); the full module path is auto-derived from the file location.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class HolonMeta:
    """Declarative IVM-slot meta for a code module.

    Field-type asymmetry — INTENTIONAL (round-8 review #7 documented):

      RELATIONAL slots (10) — container, substrate, cause, effect,
      peer_coherent, peer_contradictory, specification, instantiation,
      successor, predecessor — are `list[str]` because they reference OTHER
      holons by name. Even slots that are conceptually singular (a holon
      typically has one CONTAINER / genus) can have multiple targets in
      practice (multiple inheritance / multiple parents). __post_init__
      coerces single strings to lists for ergonomics.

      SELF-DESCRIPTIVE fields (2) — code, thermo — are `str` because they
      describe THIS holon's own essence and state, not relations to others.
      `code` = the essential differentia (one-line interface signature);
      `thermo` = runtime-state description. They're not edges; they're
      annotations.

    The asymmetry reflects a real semantic distinction, not a typing oversight.
    """
    name: str
    scale: int                                       # 0..4 (atomic..project)
    # ---- Relational slots (each = list[str], targets named by holon name) ----
    container: list[str] = field(default_factory=list)
    substrate: list[str] = field(default_factory=list)
    cause: list[str] = field(default_factory=list)
    effect: list[str] = field(default_factory=list)
    peer_coherent: list[str] = field(default_factory=list)
    peer_contradictory: list[str] = field(default_factory=list)
    specification: list[str] = field(default_factory=list)
    instantiation: list[str] = field(default_factory=list)
    successor: list[str] = field(default_factory=list)
    predecessor: list[str] = field(default_factory=list)
    # ---- Self-descriptive (each = str, describes THIS holon, not a relation) ----
    code: str = ""                                   # essential differentia (one-line interface)
    thermo: str = ""                                 # runtime state description
    # ---- Annotations ----
    # Aristotelian cause this module is PRIMARILY associated with.
    # One of: "material", "formal", "efficient", "final", or "" (no commitment)
    aristotelian_cause: str = ""
    # Optional human-readable description (one sentence)
    description: str = ""

    def __post_init__(self):
        # Allow callers to pass single strings for slots that are conceptually
        # singular (container, specification) — wrap in list for uniformity.
        for attr in ("container", "substrate", "cause", "effect",
                     "peer_coherent", "peer_contradictory",
                     "specification", "instantiation",
                     "successor", "predecessor"):
            v = getattr(self, attr)
            if isinstance(v, str):
                setattr(self, attr, [v] if v else [])

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def all_slot_relations(self) -> dict[str, list[str]]:
        """Return all 12 slot-relation lists as a single dict."""
        return {
            "successor": self.successor,
            "predecessor": self.predecessor,
            "substrate": self.substrate,
            "container": self.container,
            "peer_coherent": self.peer_coherent,
            "peer_contradictory": self.peer_contradictory,
            "code": [self.code] if self.code else [],
            "thermo": [self.thermo] if self.thermo else [],
            "cause": self.cause,
            "effect": self.effect,
            "specification": self.specification,
            "instantiation": self.instantiation,
        }
