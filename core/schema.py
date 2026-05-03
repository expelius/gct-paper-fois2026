"""Schema canónico — 12-slot IVM holonic graph.

Pure framework: Allen (hierarchy theory) + Fuller (IVM/cuboctahedron) +
classical tensegrity (Snelson struts/cables) + Whitehead (process) +
Wittgenstein (use over essence) + Aristotle (predicables, four causes).

The 12 slots correspond to the 12 directions of the cuboctahedron's
nearest-neighbor lattice. Each slot is a distinct relational ROLE —
universal across all holon types.
"""
from __future__ import annotations

import hashlib
import json as _json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# --------------------------- Slots (Fuller IVM 12 directions) ---------------

class Slot(Enum):
    """The 12 directional slots, organized in 6 polar axes.

    Each slot also carries:
      - classical_name: Aristotelian/Porphyrian/Boethian relation type
      - aristotelian_cause: which of the 4 causes this slot most-relates-to
        (None for lateral peer slots — dialectical, not causal)
    """
    SUCCESSOR = (1, "temporal", "+", "cable",
                 "A posteriori (from time, posterior)", "efficient")
    PREDECESSOR = (2, "temporal", "-", "strut",
                   "A priori (from time, prior)", "efficient")
    SUBSTRATE = (3, "vertical", "+", "cable",
                 "Material cause / Constituent", "material")
    CONTAINER = (4, "vertical", "-", "strut",
                 "Genus (Porphyry's Isagoge)", "final")
    PEER_COHERENT = (5, "lateral", "+", "strut",
                     "From similars (a similibus)", None)
    PEER_CONTRADICTORY = (6, "lateral", "-", "cable",
                          "From contraries (a contrariis)", None)
    CODE = (7, "halves", "+", "strut",
            "Differentia + Definition (essential form)", "formal")
    THERMO = (8, "halves", "-", "cable",
              "Accident (Porphyry, contingent attribute)", "material")
    CAUSE = (9, "causal", "+", "strut",
            "Efficient cause (causa efficiens)", "efficient")
    EFFECT = (10, "causal", "-", "cable",
              "From effect (ab effectu)", "final")
    SPECIFICATION = (11, "type", "+", "strut",
                     "Formal cause / Eidos (Aristotle)", "formal")
    INSTANTIATION = (12, "type", "-", "cable",
                     "Individual / Hypostasis (this-something)", "material")

    def __init__(self, number: int, axis: str, polarity: str, mechanical: str,
                 classical_name: str = "", aristotelian_cause: Optional[str] = None):
        self.number = number
        self.axis = axis
        self.polarity = polarity
        self.mechanical = mechanical  # "strut" or "cable"
        self.classical_name = classical_name
        # One of: "material", "formal", "efficient", "final", or None
        self.aristotelian_cause = aristotelian_cause

    @classmethod
    def all_slots(cls) -> list["Slot"]:
        return list(cls)

    @classmethod
    def struts(cls) -> list["Slot"]:
        return [s for s in cls if s.mechanical == "strut"]

    @classmethod
    def cables(cls) -> list["Slot"]:
        return [s for s in cls if s.mechanical == "cable"]

    @classmethod
    def by_cause(cls, cause: str) -> list["Slot"]:
        """Return slots associated with a given Aristotelian cause."""
        return [s for s in cls if s.aristotelian_cause == cause]


# --------------------------- Confidence (extraction quality) ----------------

class Confidence(Enum):
    EXTRACTED = "EXTRACTED"   # found directly in source
    INFERRED = "INFERRED"     # reasonable inference, fallible
    AMBIGUOUS = "AMBIGUOUS"   # flagged for review — typically prestress signal


# --------------------------- Layers (Allen's two halves + role) -------------

class Layer(Enum):
    STRUCTURAL = "structural"        # rate-independent code (slow)
    FUNCTIONAL = "functional"        # role-dependent (medium, can switch)
    THERMODYNAMIC = "thermodynamic"  # rate-dependent observable (fast)


# --------------------------- Edge ------------------------------------------

@dataclass
class Edge:
    source: str
    target: str
    slot: Slot
    confidence: Confidence
    scale_from: int = 0
    scale_to: int = 0
    evidence: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    history: list[dict] = field(default_factory=list)

    # Whitehead — negative prehension. When True, this edge represents an
    # EXPLICIT EXCLUSION (paper deliberately doesn't cite, experiment excludes
    # confound, claim explicitly doesn't apply). Negative prehensions are
    # invisible in standard citation graphs but carry diagnostic value:
    # gaps-by-design vs gaps-by-oversight.
    negative_prehension: bool = False

    # Allen & Giampietro (2014) — Forrester diagram signal type.
    # In Forrester-type network diagrams, SOLID arrows carry matter/energy
    # (rate-dependent flux) and DOTTED arrows carry information/code
    # (rate-independent symbols). This distinction is fundamental in hierarchy
    # theory: the two signal types have different causalitities and cannot be
    # composed as if equivalent.
    #   "matter_energy"  — rate-dependent flux (e.g., dataset → experiment,
    #                       result JSON → analysis); driven by thermodynamics
    #   "information"    — rate-independent code (e.g., pre-reg → experiment
    #                       constraints, theory → claim); works via constraint
    #   "auto"           — inferred from slot at build time (default)
    # Slots that default to matter_energy: CAUSE, EFFECT, SUCCESSOR, PREDECESSOR
    # Slots that default to information:   CODE, SPECIFICATION, INSTANTIATION
    # Mixed slots (CONTAINER, SUBSTRATE, PEER_*): context-dependent → use "auto"
    signal_type: str = "auto"  # "matter_energy" | "information" | "auto"

    # Allen/Zellmer et al. (2006) — essence of equivalence class.
    # For PEER_COHERENT edges (a similibus — from similars), this field names
    # the property that makes source and target similar. Without it, the
    # equivalence class is implicit and the "essence" cannot be retrieved.
    # Example: essence="κ-ETF basin rigidity under λ≥0.5" for two D-IDs that
    # both confirm LT-2'. Empty string means no essence declared (acceptable
    # for machine-generated edges; required for human-curated edges).
    essence: str = ""  # property explaining PEER_COHERENT equivalence

    # Provenance — which extractor / build added this edge. Set automatically
    # by the builder via the with_provenance() context manager. Enables
    # surgical queries like "all edges added by cross_cuts.py in build X".
    provenance: dict = field(default_factory=dict)

    @property
    def mechanical_type(self) -> str:
        """Derived from slot — guarantees strut/cable invariant."""
        return self.slot.mechanical

    @property
    def prehension_type(self) -> str:
        """Whitehead's prehension classification."""
        return "negative" if self.negative_prehension else "positive"

    def switch_role(self, new_slot: Slot, reason: str) -> None:
        """Track role-switching (strut↔cable transitions over time)."""
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "from_slot": self.slot.name,
            "from_mechanical": self.mechanical_type,
            "to_slot": new_slot.name,
            "to_mechanical": new_slot.mechanical,
            "reason": reason,
        })
        self.slot = new_slot

    def to_dict(self) -> dict:
        # Resolve "auto" signal_type at serialization time using slot heuristics
        resolved_signal = self.signal_type
        if resolved_signal == "auto":
            _matter_slots = {
                "CAUSE", "EFFECT", "SUCCESSOR", "PREDECESSOR",
                "SUBSTRATE", "THERMO",
            }
            _info_slots = {
                "CODE", "SPECIFICATION", "INSTANTIATION",
            }
            slot_name = self.slot.name
            if slot_name in _matter_slots:
                resolved_signal = "matter_energy"
            elif slot_name in _info_slots:
                resolved_signal = "information"
            else:
                resolved_signal = "auto"   # CONTAINER, PEER_* — leave as "auto"
        return {
            "source": self.source,
            "target": self.target,
            "slot": self.slot.name,
            "slot_number": self.slot.number,
            "mechanical_type": self.mechanical_type,
            "prehension_type": self.prehension_type,
            "negative_prehension": self.negative_prehension,
            "confidence": self.confidence.value,
            "scale_from": self.scale_from,
            "scale_to": self.scale_to,
            "evidence": self.evidence,
            "signal_type": resolved_signal,      # Allen 2014 — matter/energy vs information
            "essence": self.essence,             # Allen/Zellmer 2006 — PEER_COHERENT essence
            "created_at": self.created_at,
            "history": self.history,
            "provenance": self.provenance,
        }


# --------------------------- Harmonic ceilings (Grant Projection Theorem) ---

# Per-node-type harmonic vertex ceiling (Platonic/Archimedean solids quantized
# vertex counts per Grant 2025). A holon at full equilibrium for its TYPE has
# `populated_slots == harmonic_ceiling[type]`, regardless of the IVM 12.
# Atomic claims are tetrahedral (4); sections/experiments octahedral (6);
# papers/pillars cuboctahedral (12); clusters dodecahedral (20).

HARMONIC_CEILING_BY_SCALE = {
    0: 4,    # atomic — tetrahedron
    1: 6,    # section/experiment — octahedron
    2: 12,   # paper/pre-reg/pillar — cuboctahedron (full IVM)
    3: 20,   # cluster/family — dodecahedron
    4: 30,   # project — icosidodecahedron (or higher polyhedral)
}


# --------------------------- Node ------------------------------------------

@dataclass
class Node:
    id: str
    label: str
    scale: int
    layer: Layer
    structural_ref: Optional[str] = None  # for functional/thermo, points to structural
    active_since: str = field(default_factory=lambda: datetime.now().isoformat())
    deprecated_since: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    # Provenance — which extractor / build added this node. Set by builder
    # via with_provenance() context manager.
    provenance: dict = field(default_factory=dict)

    # Slots populated as edges are added (computed, not stored as truth)
    # Stored at compute-time in the graph builder
    _slots_populated: dict[Slot, list[str]] = field(
        default_factory=lambda: {s: [] for s in Slot}
    )

    def populate_slot(self, slot: Slot, edge_id: str) -> None:
        if edge_id not in self._slots_populated[slot]:
            self._slots_populated[slot].append(edge_id)

    @property
    def ve_score(self) -> float:
        """Vector Equilibrium score: fraction of 12 slots with at least one edge.

        1.0 = perfect IVM equilibrium (all 12 directions populated).
        <0.3 = orphan / under-developed.
        Diagnostic, not target — deviation from 1.0 IS the signal.

        See ve_score_harmonic for type-relative version (Grant theorem).
        """
        populated = sum(1 for s in Slot if self._slots_populated[s])
        return populated / 12

    @property
    def ve_score_harmonic(self) -> float:
        """Type-relative VE score using Grant's harmonic vertex ceilings.

        For atomic claims (s0, tetrahedral): full equilibrium = 4 slots.
        For papers (s2, cuboctahedral): full equilibrium = 12 slots.
        Etc.

        Means an atomic claim with 4 populated slots has ve_score_harmonic=1.0
        (FULL equilibrium for its scale-type), even if absolute ve_score=0.333.

        Adopted from Grant Projection Theorem (2025): only certain harmonic
        vertex counts are stable. A holon "completes" at its scale's natural
        polyhedron, not arbitrarily at 12.
        """
        ceiling = HARMONIC_CEILING_BY_SCALE.get(self.scale, 12)
        populated = sum(1 for s in Slot if self._slots_populated[s])
        # Cap at 1.0 even if populated > ceiling (over-saturated for its type)
        return min(1.0, populated / ceiling)

    @property
    def saturation(self) -> float:
        """Total edges / 12. >1.0 = over-loaded, candidate for split."""
        total = sum(len(v) for v in self._slots_populated.values())
        return total / 12

    @property
    def prestress_local(self) -> int:
        """Count of populated cable slots with AMBIGUOUS|INFERRED confidence.

        High = narrative tension hotspot. NOT necessarily a bug — productive
        prestress is what gives the graph informational stiffness (Fuller).
        """
        # This requires edge confidence info; computed by graph builder
        # who has access to all edges. Stored here as a placeholder method.
        # The graph layer fills this via .compute_prestress().
        return self.metadata.get("prestress_local", 0)

    @property
    def asymmetry(self) -> float:
        """|#strut_slots populated - #cable_slots populated| / 12.

        >0.5 = unbalanced (mostly-code or mostly-thermo holon).
        Diagnostic of "raw" holons missing one half (Allen).
        """
        n_struts = sum(1 for s in Slot.struts() if self._slots_populated[s])
        n_cables = sum(1 for s in Slot.cables() if self._slots_populated[s])
        return abs(n_struts - n_cables) / 12

    @property
    def aristotelian_completeness(self) -> dict:
        """Aristotle's 4 causes diagnostic (added 2026-04-28).

        Returns count of populated cause-slots per cause + completeness ratio.
        A holon "fully understood" per Aristotle has all 4 causes populated.

        Material  : SUBSTRATE + INSTANTIATION + THERMO
        Formal    : CODE + SPECIFICATION
        Efficient : CAUSE + PREDECESSOR + SUCCESSOR
        Final     : CONTAINER + EFFECT
        (Lateral peer slots are dialectical, not causal — excluded.)
        """
        causes_populated = {}
        for cause in ("material", "formal", "efficient", "final"):
            slots_for_cause = Slot.by_cause(cause)
            populated = sum(1 for s in slots_for_cause if self._slots_populated[s])
            causes_populated[cause] = populated
        n_causes_active = sum(1 for c in causes_populated.values() if c > 0)
        return {
            "completeness": round(n_causes_active / 4, 3),
            "by_cause": causes_populated,
            "missing_causes": [
                c for c, n in causes_populated.items() if n == 0
            ],
        }

    def compute_idea_fingerprint(self, neighbor_layer_signature: list = None,
                                  neighbor_scale_signature: list = None) -> str:
        """Idea-as-pattern fingerprint (Wittgenstein use-over-essence).

        Identity emerges from PATTERN of relations, not from label string.
        Two nodes with same fingerprint = same idea even with different labels;
        same label, different fingerprint = label drift / homonymy.

        Caller supplies neighbor signatures (computed at graph level since
        Node alone doesn't know its neighbors).
        """
        slot_signature = tuple(sorted(
            (s.number, len(self._slots_populated[s])) for s in Slot
        ))
        layers_sig = tuple(sorted(neighbor_layer_signature or []))
        scales_sig = tuple(sorted(neighbor_scale_signature or []))
        payload = _json.dumps([
            self.scale, self.layer.value,
            slot_signature, layers_sig, scales_sig,
        ])
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "scale": self.scale,
            "layer": self.layer.value,
            "structural_ref": self.structural_ref,
            "harmonic_ceiling": HARMONIC_CEILING_BY_SCALE.get(self.scale, 12),
            "ve_score": round(self.ve_score, 3),
            "ve_score_harmonic": round(self.ve_score_harmonic, 3),
            "saturation": round(self.saturation, 3),
            "prestress_local": self.prestress_local,
            "asymmetry": round(self.asymmetry, 3),
            "aristotelian_completeness": self.aristotelian_completeness,
            "slots": {
                f"{s.number}_{s.name.lower()}": list(self._slots_populated[s])
                for s in Slot
            },
            "slot_classical_names": {
                f"{s.number}_{s.name.lower()}": s.classical_name
                for s in Slot if self._slots_populated[s]
            },
            "active_since": self.active_since,
            "deprecated_since": self.deprecated_since,
            "metadata": self.metadata,
            "provenance": self.provenance,
        }


# --------------------------- Validation ------------------------------------

def validate_edge(edge: Edge) -> list[str]:
    """Return list of validation errors (empty if valid)."""
    errors = []
    if edge.source == edge.target:
        errors.append(f"self-loop: {edge.source}")
    if edge.scale_from < 0 or edge.scale_from > 4:
        errors.append(f"invalid scale_from: {edge.scale_from}")
    if edge.scale_to < 0 or edge.scale_to > 4:
        errors.append(f"invalid scale_to: {edge.scale_to}")
    return errors


def validate_node(node: Node) -> list[str]:
    errors = []
    if node.scale < 0 or node.scale > 4:
        errors.append(f"invalid scale: {node.scale}")
    if node.layer != Layer.STRUCTURAL and node.structural_ref is None:
        errors.append(
            f"functional/thermo node {node.id} must have structural_ref"
        )
    return errors


# --------------------------- Polarity invariant check ----------------------

def _check_polarity_invariant():
    """Sanity check: 6 struts + 6 cables, alternating across 6 polar axes."""
    struts = Slot.struts()
    cables = Slot.cables()
    assert len(struts) == 6, f"expected 6 struts, got {len(struts)}"
    assert len(cables) == 6, f"expected 6 cables, got {len(cables)}"
    axes = set(s.axis for s in Slot)
    assert len(axes) == 6, f"expected 6 polar axes, got {len(axes)}"
    # Per axis, one strut and one cable
    for axis in axes:
        slots_in_axis = [s for s in Slot if s.axis == axis]
        mechs = [s.mechanical for s in slots_in_axis]
        assert "strut" in mechs and "cable" in mechs, (
            f"axis {axis} not strut+cable polarized"
        )


_check_polarity_invariant()  # raises at import time if schema drifts


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='schema',
    scale=0,
    aristotelian_cause='formal',
    container=['core'],
    effect=['Node, Edge, Slot, Layer types consumed by all extractors'],
    peer_coherent=['holon_meta'],
    specification=['12-slot IVM cuboctahedron + 5 scales + 3 layers'],
    code='Node, Edge, Slot, Layer dataclasses + validate_*',
    description='Pure schema layer — types and invariants for the holonic graph',
)
