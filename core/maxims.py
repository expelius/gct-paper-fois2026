"""Maxims module — Aristotelian/Boethian maximae propositiones as first-class objects.

In medieval dialectical logic (Boethius, De topicis differentiis), each topos
(locus) has an associated MAXIM — a universal proposition that grounds the
type of inference made from that topos.

Examples:
  Topic: from genus           Maxim: "What is true of the genus is true of the species"
  Topic: from contraries      Maxim: "Contraries cannot inhere in the same subject simultaneously"
  Topic: from cause           Maxim: "Wherever the cause is removed, the effect is removed"

For the graph, maxims function as:
  1. VALIDATION RULES: detect edges that violate the maxim
  2. INFERENCE RULES: propose missing edges implied by the maxim
  3. REPORTING: when describing the graph, cite which maxims are operative

Each of the 12 IVM slots has 1-2 associated maxims that govern proper use.
"""
from __future__ import annotations

import re as _re_helpers
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, TYPE_CHECKING

from .schema import Confidence, Edge, Layer, Node, Slot

if TYPE_CHECKING:
    from .builder import TensegrityGraph


# --------------------------- Anteriority helpers ----------------------------
# Tolerance for sub-second clock collisions when validating temporal-order
# maxims. Node creation in the build pipeline uses ``datetime.now()`` as the
# default ``active_since`` and consecutive ``add_node`` calls can register
# within microseconds of each other; without an epsilon, the validator would
# fire on essentially-simultaneous timestamps. 2 seconds is well above the
# observed collision window (sub-millisecond) yet far below any meaningful
# lineage gap (always >= 1 day in EXPERIMENTS-LOG.md).
_ANTERIORITY_EPSILON_SECONDS = 2.0

_DID_SUFFIX_RE = _re_helpers.compile(r"^(D-\d+)([a-z]+|v\d*)$")


def _parse_iso_strict(value) -> Optional[datetime]:
    """Parse ``active_since`` strictly as ISO 8601, returning ``None`` on
    failure.

    The temporal-order validators previously used raw string comparison on
    ``active_since``, which silently produced spurious violations when one of
    the endpoints had a non-ISO date such as ``"post-D-097"``, ``"~2026-04"``
    or ``"QUEUED"`` (string ordering puts ``"2026-..."`` before any letter).
    Returning None on parse failure forces those edges to be skipped — the
    correct behaviour, since we cannot say anything about temporal order
    without a valid timestamp.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _is_suffix_lineage(child_id: str, parent_id: str) -> bool:
    """True iff ``child_id`` is a suffix-extension of ``parent_id`` per the
    project's D-ID convention (e.g., ``D-309c`` extends ``D-309``;
    ``D-103v`` extends ``D-103``).

    The lineage convention encodes ordering deterministically — the suffix
    entry is by definition a later refinement of the parent. When the
    convention contradicts a near-identical timestamp, the convention wins.
    """
    if not (isinstance(child_id, str) and isinstance(parent_id, str)):
        return False
    m = _DID_SUFFIX_RE.match(child_id)
    if not m:
        return False
    return m.group(1) == parent_id


# --------------------------- Maxim object ----------------------------------


@dataclass
class Maxim:
    """A universal proposition associated with a slot."""
    slot: Slot
    classical_name: str         # e.g., "Genus", "Efficient cause"
    latin_form: str             # e.g., "Quod genus est, est in specie"
    english_form: str           # e.g., "What is true of the genus is true of the species"
    validation_rule: Optional[Callable] = None  # graph, edge → list of violations
    inference_rule: Optional[Callable] = None   # graph, edge → list of proposed edges

    def to_dict(self) -> dict:
        return {
            "slot": self.slot.name,
            "slot_number": self.slot.number,
            "classical_name": self.classical_name,
            "latin_form": self.latin_form,
            "english_form": self.english_form,
            "has_validation_rule": self.validation_rule is not None,
            "has_inference_rule": self.inference_rule is not None,
        }


# --------------------------- Validation rules ------------------------------


def _validate_container(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Genus maxim: container must be at higher (>=) scale than contained."""
    violations = []
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if src and tgt and src.scale < tgt.scale:
        violations.append(
            f"genus violation: {edge.source} (scale {src.scale}) declared as "
            f"CONTAINER of {edge.target} (scale {tgt.scale}) but is at lower scale"
        )
    return violations


def _validate_substrate(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Material cause maxim: substrate is at lower (<=) scale than what it enables."""
    violations = []
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if src and tgt and src.scale > tgt.scale:
        violations.append(
            f"material cause violation: {edge.source} (scale {src.scale}) declared as "
            f"SUBSTRATE of {edge.target} (scale {tgt.scale}) but is at higher scale"
        )
    return violations


def _validate_predecessor(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Anteriority maxim: in edge X->Y[PREDECESSOR], target Y is the predecessor
    of source X, so Y must exist prior in time to X. A violation arises when the
    alleged predecessor (target) is actually later than its successor (source) —
    i.e. ``tgt.active_since > src.active_since`` (equivalently, the implemented
    test ``src.active_since < tgt.active_since``).

    Robustness clauses (added 2026-05-02 to fix the D-309c clock-collision):
      * Skip when either active_since cannot be parsed as ISO datetime — string
        comparison on garbage like "post-D-097" was producing spurious hits.
      * Tolerate sub-second differences when the source id is a suffix-extension
        of the target id (project convention: D-101c is a follow-up of D-101).
        The suffix encodes ordering deterministically; clock collisions during
        node registration must not override it.
    """
    violations = []
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return violations
    src_dt = _parse_iso_strict(src.active_since)
    tgt_dt = _parse_iso_strict(tgt.active_since)
    if src_dt is None or tgt_dt is None:
        return violations  # cannot validate without two valid timestamps
    if src_dt >= tgt_dt:
        return violations  # well-formed (or equal): not a violation
    # src_dt < tgt_dt — alleged predecessor (target) is later than source.
    # Apply suffix-id tie-breaker: if source id extends target id (e.g.,
    # D-309c extends D-309), the lineage convention overrides timestamp.
    delta = (tgt_dt - src_dt).total_seconds()
    if delta <= _ANTERIORITY_EPSILON_SECONDS and _is_suffix_lineage(edge.source, edge.target):
        return violations
    violations.append(
        f"anteriority violation: {edge.target} (active_since {tgt.active_since}) "
        f"declared as PREDECESSOR of {edge.source} (active_since {src.active_since}) "
        f"but exists later"
    )
    return violations


def _validate_peer_contradictory(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Contraries maxim: contraries should not also be peer-coherent simultaneously."""
    violations = []
    # Check if there's also a PEER_COHERENT edge between same pair
    for other_eid, other_edge in graph._edges.items():
        if (other_edge.source == edge.source and
            other_edge.target == edge.target and
            other_edge.slot == Slot.PEER_COHERENT):
            violations.append(
                f"contraries-coherent contradiction: {edge.source}↔{edge.target} "
                f"declared both PEER_CONTRADICTORY and PEER_COHERENT — Aristotle: "
                f"contraries cannot inhere simultaneously"
            )
    return violations


# NOTE on reciprocal-pair rules (round 7 cleanup, 2026-04-28):
#
# An earlier version of this module had four "reciprocal-pair" validators
# (_validate_cause_effect_pair, _validate_effect_cause_pair,
#  _validate_specification_pair, _validate_instantiation_pair) and three
# "reciprocal-pair" inference rules. They all checked: "for edge X→Y[slot=A],
# does an explicit edge Y→X[slot=reciprocal(A)] exist?" — and produced
# hundreds of "violations" / "missing edge" proposals.
#
# Round-7 review correctly identified these as SPURIOUS. The IVM slot system
# already enforces reciprocity automatically: when builder.add_edge() inserts
# an edge X→Y[A], it populates Y's slot A AND X's slot reciprocal(A) with the
# SAME edge_id (see TensegrityGraph.add_edge → _reciprocal_slot). The
# "reciprocal relationship" lives in the slot bin, not in a second edge.
# Asking for a second explicit edge demands redundancy the system doesn't need
# (and which would corrupt the saturation/VE metrics if added).
#
# So those rules are removed. The remaining validators all check things the
# slot system does NOT auto-enforce: scale ordering, anteriority of
# timestamps, confidence-vs-modality, and cross-axis category checks.


# ----- The 7 additional rules (round 7) -----


def _validate_successor(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Anteriority maxim (mirror): in edge X->Y[SUCCESSOR], target Y is the
    successor of source X, so Y.active_since must be >= X.active_since.

    Same robustness clauses as ``_validate_predecessor`` (skip on unparseable
    timestamps; tolerate sub-second collisions when target id is a suffix
    extension of source id, since the lineage convention overrides clock).
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    src_dt = _parse_iso_strict(src.active_since)
    tgt_dt = _parse_iso_strict(tgt.active_since)
    if src_dt is None or tgt_dt is None:
        return []
    if tgt_dt >= src_dt:
        return []
    delta = (src_dt - tgt_dt).total_seconds()
    if delta <= _ANTERIORITY_EPSILON_SECONDS and _is_suffix_lineage(edge.target, edge.source):
        return []
    return [
        f"successor anteriority violation: {edge.target} (active_since {tgt.active_since}) "
        f"declared as SUCCESSOR of {edge.source} (active_since {src.active_since}) "
        f"but exists earlier"
    ]


def _validate_peer_coherent_same_scale(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """A similibus maxim: similars cluster within scale.

    Aristotle's strict reading is same-scale only — that's the STRICT_VIOLATION.
    A one-scale jump (Δ=1) is plausibly a fudge by an extractor that conflated
    "uses the same vocabulary" with "is structurally similar"; we downgrade to
    WARNING. Larger jumps (Δ>=2) are almost certainly category errors that
    should have used CONTAINER/SUBSTRATE on the vertical axis.

    Returns violation messages tagged with severity prefix so consumers can
    triage. (Severity convention: lines starting with [STRICT] are
    non-negotiable; [WARN] is informational.)
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    delta = abs(src.scale - tgt.scale)
    if delta == 0:
        return []
    if delta == 1:
        return [
            f"[WARN] peer-coherent one-scale-jump: {edge.source} (scale {src.scale}) "
            f"PEER_COHERENT with {edge.target} (scale {tgt.scale}); strict Aristotelian "
            f"similars are same-scale, but Δ=1 may reflect vocabulary overlap rather "
            f"than category error"
        ]
    return [
        f"[STRICT] peer-coherent cross-scale: {edge.source} (scale {src.scale}) "
        f"PEER_COHERENT with {edge.target} (scale {tgt.scale}, Δ={delta}); "
        f"this is almost certainly an extractor error that should have used "
        f"CONTAINER/SUBSTRATE on the vertical axis"
    ]


def _validate_code(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Differentia maxim: code (essential definition) cannot come from a finer-grained instance.

    Edge X → Y[CODE] means Y receives its definitional differentia from X.
    X must be at scale >= Y's scale (the form is at-or-above the instance in the holarchy).
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    if src.scale < tgt.scale:
        return [
            f"code-from-instance violation: {edge.target} (scale {tgt.scale}) declared "
            f"as receiving CODE (essential definition) from {edge.source} (scale {src.scale}) — "
            f"a definition cannot be drawn from a finer-grained instance"
        ]
    return []


def _validate_thermo(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Accident maxim — refined per round 7 review.

    Original rule conflated *accidens praedicabile* (Porphyry's logical accident:
    a predicable that doesn't define the species' essence) with epistemic
    uncertainty. Round-7 counter-example: "the measured AR of HNC is 0.42" is
    BOTH an accident (could have been otherwise) AND a measurement (legitimately
    EXTRACTED). So the original rule fired too often.

    Refined check: only flag THERMO edges with EXTRACTED confidence when the
    target is a STRUCTURAL or kind-level node (not a measurement). Heuristic:
    if target.layer is THERMODYNAMIC, the THERMO assertion IS a measurement and
    should keep its EXTRACTED confidence. If target.layer is STRUCTURAL,
    asserting an accident (THERMO) with measurement-grade certainty is the
    real epistemological irony — that's what we flag.
    """
    if edge.confidence != Confidence.EXTRACTED:
        return []
    tgt = graph._nodes.get(edge.target)
    if not tgt:
        return []
    if tgt.layer == Layer.THERMODYNAMIC:
        return []   # measurement of an accident at a measurement node — fine
    return [
        f"accident-as-certain violation: {edge.source}→{edge.target} declared THERMO "
        f"(accidental attribute) on a {tgt.layer.value} target with EXTRACTED confidence; "
        f"an accident on a structural/kind-level entity should be AMBIGUOUS or INFERRED, "
        f"not measurement-grade certain"
    ]


# Removed in round 7 cleanup: _validate_effect_cause_pair,
# _validate_specification_pair, _validate_instantiation_pair,
# _infer_cause_implies_effect, _infer_specification_implies_instantiation.
# See module-level note at the top about why reciprocal-pair checks against
# explicit second edges are spurious in this codebase.


# ----- Round 7b: validators for slots that previously had no rule, but the
# checks are NOT reciprocal-pair (they check things the slot system does not
# auto-enforce: scale ordering on the type axis, same-scale on the lateral
# negative axis, and causal-chain cycles).


def _validate_specification_direction(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Forma dat esse rei: the form is at-or-above the instance abstractly.

    Edge X→Y[SPECIFICATION]: target Y receives its form from X (Y is told
    "your form is X"). For the form to genuinely BE more abstract than the
    instance, the form's scale should be >= the instance's. In this codebase
    the convention is `use → concept` with slot=SPECIFICATION; concept (target)
    is the form. So `target.scale >= source.scale` is the well-formed case.
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    if tgt.scale < src.scale:
        return [
            f"specification direction violation: {edge.source} (scale {src.scale}) "
            f"→ {edge.target} (scale {tgt.scale}) declares the latter as form/eidos, "
            f"but a form should be at-or-above the instance abstractly (target.scale >= source.scale)"
        ]
    return []


def _validate_instantiation_direction(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Hoc aliquid: the individual is at-or-below its form abstractly (mirror).

    Edge X→Y[INSTANTIATION]: target Y receives the relation in INSTANTIATION
    slot. Convention: form (source) → instance (target). So `source.scale >=
    target.scale` is the well-formed case (form is at-or-above instance).
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    if src.scale < tgt.scale:
        return [
            f"instantiation direction violation: {edge.source} (scale {src.scale}) "
            f"→ {edge.target} (scale {tgt.scale}) declares the former as form, but "
            f"a form should be at-or-above the instance (source.scale >= target.scale)"
        ]
    return []


def _validate_peer_contradictory_same_scale(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """Contraria simul... maxim mirror on the lateral negative axis.

    Same-scale is required for genuine contraries: 'red' and 'green' are
    contraries because both are colors (same scale). 'red' and 'molecule'
    are not contraries — they belong to different categories. Cross-scale
    PEER_CONTRADICTORY is almost always a category error masquerading as
    opposition. Mirrors the peer-coherent rule with the same severity tiers.
    """
    src = graph._nodes.get(edge.source)
    tgt = graph._nodes.get(edge.target)
    if not (src and tgt):
        return []
    delta = abs(src.scale - tgt.scale)
    if delta == 0:
        return []
    if delta == 1:
        return [
            f"[WARN] peer-contradictory one-scale-jump: {edge.source} (scale {src.scale}) "
            f"PEER_CONTRADICTORY with {edge.target} (scale {tgt.scale}); contraries should "
            f"share a category (same scale)"
        ]
    return [
        f"[STRICT] peer-contradictory cross-scale: {edge.source} (scale {src.scale}) "
        f"PEER_CONTRADICTORY with {edge.target} (scale {tgt.scale}, Δ={delta}); not "
        f"contraries — different categories; the relation likely belongs on the vertical "
        f"or causal axis, not lateral"
    ]


def _validate_cause_no_self_loop(graph: "TensegrityGraph", edge: Edge) -> list[str]:
    """No node causes itself directly.

    Aristotle: a thing cannot be its own efficient cause (would require
    being and not-being simultaneously). Self-loops on CAUSE are paradoxical
    in the strict efficient-cause sense; flag them. (Causa sui in Spinoza is
    a different doctrine — and would warrant a different slot if we ever
    wanted to encode it.)
    """
    if edge.source == edge.target:
        return [
            f"[STRICT] efficient-cause self-loop: {edge.source} declared as CAUSE "
            f"of itself; nothing can be its own efficient cause without paradox "
            f"(causa sui requires a distinct ontological framework)"
        ]
    return []


# --------------------------- Inference rules -------------------------------


def _infer_genus_implies_specification(graph: "TensegrityGraph", edge: Edge) -> list[dict]:
    """If A is GENUS of B, then likely B has SPECIFICATION pointing to some form."""
    if edge.slot != Slot.CONTAINER:
        return []
    target_node = graph._nodes.get(edge.target)
    if not target_node:
        return []
    has_spec = bool(target_node._slots_populated[Slot.SPECIFICATION])
    if not has_spec:
        return [{
            "type": "missing_specification",
            "node": edge.target,
            "rationale": (
                f"{edge.target} has CONTAINER ({edge.source}) but no SPECIFICATION — "
                f"Porphyry: every species under a genus has a differentia/form"
            ),
        }]
    return []


# _infer_predecessor_implies_successor removed in round 7 cleanup — same
# reciprocal-pair issue; the slot system already populates SUCCESSOR via
# automatic reciprocity when a PREDECESSOR edge is added.


# --------------------------- Maxim registry --------------------------------


MAXIMS: dict[Slot, Maxim] = {
    Slot.SUCCESSOR: Maxim(
        slot=Slot.SUCCESSOR,
        classical_name="A posteriori (from time, posterior)",
        latin_form="Quod sequitur in tempore",
        english_form="What follows in time depends on what preceded for its possibility",
        validation_rule=_validate_successor,
    ),
    Slot.PREDECESSOR: Maxim(
        slot=Slot.PREDECESSOR,
        classical_name="A priori (from time, prior)",
        latin_form="Quod praecedit, conditio est sequentis",
        english_form="What precedes in time is the condition of what follows",
        validation_rule=_validate_predecessor,
    ),
    Slot.SUBSTRATE: Maxim(
        slot=Slot.SUBSTRATE,
        classical_name="Material cause (causa materialis)",
        latin_form="Ex qua materia, sublata materia tollitur effectum",
        english_form="From which it is made; remove the matter, remove the effect",
        validation_rule=_validate_substrate,
    ),
    Slot.CONTAINER: Maxim(
        slot=Slot.CONTAINER,
        classical_name="Genus (Porphyry's Isagoge)",
        latin_form="Quod de genere praedicatur, de specie praedicatur",
        english_form="What is predicated of the genus is predicated of the species",
        validation_rule=_validate_container,
        inference_rule=_infer_genus_implies_specification,
    ),
    Slot.PEER_COHERENT: Maxim(
        slot=Slot.PEER_COHERENT,
        classical_name="From similars (a similibus)",
        latin_form="Quod uni simili convenit, alteri convenire potest",
        english_form="What suits one of two similars may suit the other",
        validation_rule=_validate_peer_coherent_same_scale,
    ),
    Slot.PEER_CONTRADICTORY: Maxim(
        slot=Slot.PEER_CONTRADICTORY,
        classical_name="From contraries (a contrariis)",
        latin_form="Contraria simul in eodem subjecto inesse non possunt",
        english_form="Contraries cannot inhere in the same subject simultaneously",
        # Two checks in one slot: also-coherent contradiction (logical), and
        # cross-scale category error (ontological). The dispatcher composes
        # them by chaining results.
        validation_rule=lambda g, e: (
            _validate_peer_contradictory(g, e) +
            _validate_peer_contradictory_same_scale(g, e)
        ),
    ),
    Slot.CODE: Maxim(
        slot=Slot.CODE,
        classical_name="Differentia + Definition (essential form)",
        latin_form="Differentia est qua una species ab alia distinguitur",
        english_form="The differentia is that by which one species is distinguished from another",
        validation_rule=_validate_code,
    ),
    Slot.THERMO: Maxim(
        slot=Slot.THERMO,
        classical_name="Accident (Porphyry, contingent attribute)",
        latin_form="Accidens potest adesse aut abesse sine corruptione subjecti",
        english_form="An accident can be present or absent without destroying the subject",
        validation_rule=_validate_thermo,
    ),
    Slot.CAUSE: Maxim(
        slot=Slot.CAUSE,
        classical_name="Efficient cause (causa efficiens)",
        latin_form="Sublata causa, tollitur effectus",
        english_form="When the cause is removed, the effect is removed",
        # No reciprocal-pair validator: the slot system already populates
        # the source's EFFECT slot bin when a CAUSE edge is added (see
        # builder.add_edge → _reciprocal_slot). The valid non-reciprocal
        # check is: nothing can be its own efficient cause.
        validation_rule=_validate_cause_no_self_loop,
    ),
    Slot.EFFECT: Maxim(
        slot=Slot.EFFECT,
        classical_name="From effect (ab effectu)",
        latin_form="Per effectus cognoscuntur causae",
        english_form="Causes are known through their effects",
    ),
    Slot.SPECIFICATION: Maxim(
        slot=Slot.SPECIFICATION,
        classical_name="Formal cause / Eidos (Aristotle)",
        latin_form="Forma dat esse rei",
        english_form="The form gives being to the thing",
        validation_rule=_validate_specification_direction,
    ),
    Slot.INSTANTIATION: Maxim(
        slot=Slot.INSTANTIATION,
        classical_name="Individual / Hypostasis (Aristotle, this-something)",
        latin_form="Hoc aliquid, individuum non praedicatur de pluribus",
        english_form="This-something — the individual cannot be predicated of many",
        validation_rule=_validate_instantiation_direction,
    ),
}


# --------------------------- Apply maxims ----------------------------------


import re as _re


def _parse_severity(message: str) -> tuple[str, str]:
    """Extract leading severity tag from a violation message.

    Convention: validators may prefix messages with '[STRICT] ' or '[WARN] '
    to signal severity. Default (no prefix) is 'VIOLATION' — the standard
    must-fix case. Returns (severity, message_without_prefix).
    """
    m = _re.match(r"^\[(STRICT|WARN|INFO)\]\s+(.*)", message, _re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return "VIOLATION", message


def _build_reciprocal_index(graph: "TensegrityGraph") -> dict:
    """Build a one-shot (source, target, slot) → edge_id index.

    Currently unused by any rule (round 7 cleanup removed the rules that
    needed it). Kept for future rules that genuinely require a fast
    reverse-lookup, e.g., a future "this CAUSE chain forms a cycle" check.
    """
    idx = {}
    for eid, e in graph._edges.items():
        idx[(e.source, e.target, e.slot)] = eid
    return idx


def validate_graph(graph: "TensegrityGraph") -> list[dict]:
    """Apply all maxim validation rules.

    Returns a list of violation dicts. Each entry includes:
      - edge_id, slot, maxim
      - violation (the message text with any severity tag stripped)
      - severity ('STRICT' / 'WARN' / 'VIOLATION' / 'INFO')

    Validators that cannot run (e.g., missing timestamps) are silently
    skipped — see `validate_graph_with_coverage` for a variant that tracks
    unable-to-validate counts.
    """
    violations = []
    for eid, edge in graph._edges.items():
        maxim = MAXIMS.get(edge.slot)
        if not (maxim and maxim.validation_rule):
            continue
        for raw in maxim.validation_rule(graph, edge):
            severity, msg = _parse_severity(raw)
            violations.append({
                "edge_id": eid,
                "slot": edge.slot.name,
                "maxim": maxim.classical_name,
                "severity": severity,
                "violation": msg,
            })
    return violations


def validate_graph_with_coverage(graph: "TensegrityGraph") -> dict:
    """Variant that distinguishes 'checked + passed' from 'unable to check'.

    Some validators (predecessor/successor anteriority, container scale)
    require that both endpoints carry the relevant fields (active_since,
    scale). When fields are missing the rule returns [] (no violation), but
    semantically the rule was UNABLE to validate. This variant counts those
    cases distinctly so coverage metrics are honest.

    Returns dict with:
      - violations: same as validate_graph
      - n_checked:  edges where the validator ran AND all required fields present
      - n_unable:   edges where the validator existed but couldn't run
      - n_no_rule:  edges whose slot has no validator
    """
    violations = validate_graph(graph)
    n_checked = n_unable = n_no_rule = 0
    for eid, edge in graph._edges.items():
        maxim = MAXIMS.get(edge.slot)
        if not (maxim and maxim.validation_rule):
            n_no_rule += 1
            continue
        # Heuristic: the validator was "able" to run if both endpoints exist.
        # For temporal rules we additionally require active_since on both.
        src = graph._nodes.get(edge.source)
        tgt = graph._nodes.get(edge.target)
        if not (src and tgt):
            n_unable += 1
            continue
        if edge.slot in (Slot.SUCCESSOR, Slot.PREDECESSOR):
            if not (src.active_since and tgt.active_since):
                n_unable += 1
                continue
        n_checked += 1
    return {
        "violations": violations,
        "n_checked": n_checked,
        "n_unable": n_unable,
        "n_no_rule": n_no_rule,
    }


def infer_missing_edges(graph: "TensegrityGraph") -> list[dict]:
    """Apply all maxim inference rules; return list of proposed missing edges."""
    proposals = []
    for eid, edge in graph._edges.items():
        maxim = MAXIMS.get(edge.slot)
        if maxim and maxim.inference_rule:
            for prop in maxim.inference_rule(graph, edge):
                proposals.append({
                    "from_edge_id": eid,
                    "from_slot": edge.slot.name,
                    "maxim": maxim.classical_name,
                    "proposed": prop,
                })
    return proposals


def maxim_summary() -> list[dict]:
    """Return list of all maxims (for documentation / report)."""
    return [m.to_dict() for m in MAXIMS.values()]


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='maxims',
    scale=1,
    aristotelian_cause='final',
    container=['core'],
    substrate=['core.schema', 'core.builder'],
    cause=['enrich_with_maxims.py post-build'],
    effect=['violation/proposal lists per node/edge'],
    specification=['12 Boethian/Aristotelian maxims as validation+inference rules'],
    code='MAXIMS registry + validate_graph + infer_missing_edges',
    description='External validators for the IVM slot relationships',
)
