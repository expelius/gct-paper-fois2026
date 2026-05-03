"""Specialized node-type factories — MethodologicalUnit, ResearchPattern,
ReviewerComment, OperationalDistinction, Creaon, Genon, Environ.

These don't subclass Node; they're factory functions that produce Nodes
with the right metadata + scale + layer conventions for each type.

Adopted from Idea2Story (Xu et al. 2026, arxiv 2601.20833):
  - MethodologicalUnit = "core methodological unit" (their term)
  - ResearchPattern    = "reusable research pattern" (their term)
  - ReviewerComment    = peer-review feedback as persistent graph node

Added 2026-05-01 — JCC/PJC framework absorption:
  - OperationalDistinction = compute unit from Judgment-Conditioned Computation
    (Patel 2026) + Pattern-to-Judgment Computation (Patel 2026b). A difference
    that, under an explicit criterion, changes the route, evidence requirement,
    paper claim, or stopping condition of the project.

Added 2026-05-01 — Allen & Giampietro (2014) absorption:
  - Creaon  = input portal of a holon (Allen/Patten & Auble 1980). The filter
              through which external signal enters the holon. Rate-independent
              (structural) — it's part of the holon's coded plan, not its
              thermodynamic behavior. In HNC: the EMA bottleneck receiving s_{k-1}.
  - Genon   = output portal of a holon. The point through which the holon emits
              its narrative to its context. In HNC: the prediction head emitting
              tokens; also the genon from s_k → s_{k+1}.
  - Environ = the environment holon surrounding a focal holon, split into:
              input environ (feeds the creaon — matter/energy and information)
              and output environ (receives from the genon — the world that
              reacts to the holon's narrative).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .schema import Layer, Node


# --------------------------- MethodologicalUnit ----------------------------


def make_methodological_unit(
    unit_id: str,
    label: str,
    method_class: str,  # e.g., "statistical_test", "training_protocol", "sampling"
    description: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create a MethodologicalUnit node (Idea2Story-inspired).

    A reusable methodological template that multiple D-XXX experiments
    might INSTANTIATE. Lives at scale s1 (section/unit).

    Examples:
      - "Bootstrap CI with N=10000 iter, percentile method"
      - "Mixed-effects model with random intercept per seed"
      - "Pre-registered freeze with falsification rules"

    These get reused across experiments; tracking them as nodes lets us
    answer "which experiments share this methodology?".
    """
    metadata = {
        "node_type": "methodological_unit",
        "method_class": method_class,
        "description": description,
        "reusable": True,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=unit_id,
        label=label,
        scale=1,
        layer=Layer.STRUCTURAL,
        metadata=metadata,
    )


# --------------------------- ResearchPattern -------------------------------


def make_research_pattern(
    pattern_id: str,
    label: str,
    god_node_id: str,
    members: list[str],
    typical_use_cases: Optional[list[str]] = None,
    pattern_signature: Optional[dict] = None,
) -> Node:
    """Create a ResearchPattern node (Idea2Story-inspired).

    A pre-composed reusable pattern centered on a god-node + its IVM
    neighborhood. Materialized as a single Node at scale s3 (cluster/family).

    Use case: Idea2Story's "intent alignment" — when user says "I want to
    test X", search for ResearchPattern nodes whose typical_use_cases match,
    instead of generating from scratch.
    """
    metadata = {
        "node_type": "research_pattern",
        "god_node_id": god_node_id,
        "members": members,
        "typical_use_cases": typical_use_cases or [],
        "pattern_signature": pattern_signature or {},
        "n_members": len(members),
        "composed_at": datetime.now().isoformat(),
    }
    return Node(
        id=pattern_id,
        label=label,
        scale=3,
        layer=Layer.STRUCTURAL,
        metadata=metadata,
    )


# --------------------------- ReviewerComment -------------------------------


def make_reviewer_comment(
    comment_id: str,
    paper_section_node_id: str,
    severity: str,  # "Critical" | "Important" | "Suggestion"
    review_round: int,
    comment_text: str,
    reviewer_id: str = "internal",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create a ReviewerComment node (Idea2Story uses peer-review feedback).

    A thermodynamic holon attached to a paper section. Persists peer-review
    findings as graph state instead of ephemeral output, enabling tracking
    of "comment X was addressed by edit Y".

    severity: "Critical" — must-fix (blocks submission)
              "Important" — should-fix (improves quality)
              "Suggestion" — could-fix (optional)
    """
    if severity not in ("Critical", "Important", "Suggestion"):
        raise ValueError(f"invalid severity: {severity}")
    metadata = {
        "node_type": "reviewer_comment",
        "severity": severity,
        "review_round": review_round,
        "comment_text": comment_text,
        "reviewer_id": reviewer_id,
        "addressed": False,  # main context updates when fixed
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=comment_id,
        label=f"Reviewer comment [{severity}, round {review_round}]",
        scale=0,  # atomic — single observation
        layer=Layer.THERMODYNAMIC,
        structural_ref=paper_section_node_id,
        metadata=metadata,
    )


# --------------------------- OperationalDistinction ------------------------

def make_operational_distinction(
    distinction_id: str,
    label: str,
    option_a: str,
    option_b: str,
    judgment_state: str,  # "AMBIGUOUS" | "MISSING_EVIDENCE" | "CONTRADICTORY" | "STABLE"
    stabilized_by: Optional[list[str]] = None,  # D-ID list that stabilize this distinction
    contradicted_by: Optional[list[str]] = None,  # D-ID list that contradict
    paper_claims_unlocked: Optional[list[str]] = None,  # e.g. ["P4.§5.1", "P7.abstract"]
    description: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create an OperationalDistinction node (JCC/PJC-inspired, 2026-05-01).

    An OperationalDistinction is the epistemic unit from Judgment-Conditioned
    Computation (Patel 2026): a difference that, under an explicit criterion,
    changes the route, evidence requirement, paper claim, or stopping condition.
    It is NOT a hypothesis (which is a falsifiable prediction) — it is the
    abstract distinction that a hypothesis is *about*.

    Role in the graph:
      - Hypothesis nodes INSTANTIATE a distinction (slot: INSTANTIATION)
      - Experiment D-IDs STABILIZE or CONTRADICT a distinction (slot: CAUSE/PEER_CONTRADICTORY)
      - Paper sections DEPEND_ON a distinction being STABLE (slot: SUBSTRATE)

    This creates a new traversal: "which experiments have been run to stabilize
    THIS distinction?" and "which distinctions remain AMBIGUOUS/MISSING_EVIDENCE
    across the entire project?" — queries not answerable from hypothesis nodes alone.

    judgment_state mirrors the JCC taxonomy:
      STABLE   — distinction is resolved (at least one D-ID in OK status covers it)
      AMBIGUOUS — multiple readings exist, no experiment has resolved the choice
      MISSING_EVIDENCE — no D-ID has been run targeting this distinction
      CONTRADICTORY — D-IDs exist but disagree on the verdict

    Examples:
      - "HNC vs GRU basin rigidity under κ-loss" (STABLE — D-228 confirmed HNC 20.5×)
      - "Substrate-independence of κ-ETF basin" (STABLE — D-234 confirmed ≥5× on 6 substrates)
      - "LLM universality of ETF de-centroide" (STABLE — D-283/D-302/D-304 confirmed)
      - "Cloth mesh IVM-fundamentalness" (AMBIGUOUS — D-Cloth confirmed triangular 89%, but D-107-109 pending)
    """
    if judgment_state not in ("STABLE", "AMBIGUOUS", "MISSING_EVIDENCE", "CONTRADICTORY"):
        raise ValueError(f"invalid judgment_state: {judgment_state}")

    metadata = {
        "node_type": "operational_distinction",
        "option_a": option_a,
        "option_b": option_b,
        "judgment_state": judgment_state,
        "stabilized_by": stabilized_by or [],
        "contradicted_by": contradicted_by or [],
        "paper_claims_unlocked": paper_claims_unlocked or [],
        "description": description,
        "jcc_reference": "Patel (2026) JCC + Pattern-to-Judgment Computation",
        "created_at": datetime.now().isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=distinction_id,
        label=label,
        scale=1,  # section-level — a distinction spans multiple experiments but below paper
        layer=Layer.STRUCTURAL,  # epistemic objects are structurally defined (rate-independent)
        # Note: FUNCTIONAL was initially considered (judgment_state transitions) but
        # validate_node requires FUNCTIONAL/THERMO nodes to have structural_ref.
        # OperationalDistinctions ARE their own structural reference — their identity
        # comes from their slot pattern (Wittgenstein fingerprint), not a parent node.
        metadata=metadata,
    )


def get_unstabilized_distinctions(nodes: list) -> list:
    """Return all OperationalDistinction nodes NOT in STABLE state.

    Utility function for querying the graph: which distinctions remain
    unresolved across the entire project? This is the KG equivalent of
    the JCC 'compute follows unresolved distinction' principle.
    """
    return [
        n for n in nodes
        if (
            isinstance(n, object)
            and hasattr(n, "metadata")
            and n.metadata.get("node_type") == "operational_distinction"
            and n.metadata.get("judgment_state") != "STABLE"
        )
    ]


# ======================== Allen 2014 Holon Portal Types ========================
# Source: Allen & Giampietro, Ecological Modelling 293 (2014) 31–41
#         Patten & Auble (1980) — creaon/genon/taxon/environ vocabulary
# ============================================================================


def make_creaon(
    creaon_id: str,
    parent_holon_id: str,
    label: str,
    signal_types: Optional[list[str]] = None,  # ["matter_energy", "information"]
    description: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create a Creaon node — the input portal of a holon.

    The creaon is the filter through which external signal enters the holon.
    Allen/Patten & Auble (1980): the creaon sees the input signal coming in
    through the filter of the holon surface. It is rate-independent (structural)
    — it is part of the holon's coded plan that constrains what can enter.

    The creaon exists at scale 0 (atomic, below the holon it serves). It
    receives edges via SUBSTRATE slot from its parent holon (the holon's
    material surface), and via CAUSE slot from the input environ node.

    signal_types: which channels this creaon admits. Following Forrester/Allen:
        "matter_energy" — rate-dependent flux (raw inputs)
        "information"   — rate-independent codes (context, constraints)
    Both may coexist — Fig. 6 in Allen 2014 shows dual input environs.

    In HNC research context:
        Experiment creaon = dataset + experimental conditions
        HNC s_k creaon    = EMA bottleneck receiving from s_{k-1}
    """
    metadata = {
        "node_type": "creaon",
        "parent_holon_id": parent_holon_id,
        "signal_types": signal_types or ["matter_energy", "information"],
        "description": description,
        "allen_reference": "Allen & Giampietro (2014) Fig. 1b, Fig. 6; Patten & Auble (1980)",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=creaon_id,
        label=label or f"Creaon of {parent_holon_id}",
        scale=0,  # atomic — below the holon it serves
        layer=Layer.STRUCTURAL,  # rate-independent; part of the coded plan
        structural_ref=parent_holon_id,  # parent holon IS the structural reference
        metadata=metadata,
    )


def make_genon(
    genon_id: str,
    parent_holon_id: str,
    label: str,
    narrative_type: str = "model",  # "model" | "narrative" — Allen 2014 §4
    description: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create a Genon node — the output portal of a holon.

    The genon is the point through which the holon emits its narrative to the
    world. Allen/Patten & Auble (1980): the genon captures the output signal
    that is to be integrated for the environment.

    narrative_type captures the crucial Allen 2014 §4 distinction:
        "model"     — internally consistent output; fixed in parameter space;
                      requires narrow scope. Appropriate for results, metrics,
                      rejection-rule verdicts.
        "narrative" — may contain tensions/inconsistency; ranges across levels;
                      appropriate for paper abstracts, theoretical claims,
                      cross-level explanations.
    This distinction is non-trivial: a claim that tries to be a model but
    spans too many levels becomes incoherent. A claim acknowledged as
    narrative can legitimately contain Holling-style inconsistencies.

    In HNC research context:
        Experiment genon  = results JSON, paper-section output
        HNC s_k genon     = representation at scale k passed to s_{k+1} and
                            ultimately to the prediction head
    """
    metadata = {
        "node_type": "genon",
        "parent_holon_id": parent_holon_id,
        "narrative_type": narrative_type,
        "description": description,
        "allen_reference": "Allen & Giampietro (2014) Fig. 1b, §4 Models and Narratives",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=genon_id,
        label=label or f"Genon of {parent_holon_id}",
        scale=0,
        layer=Layer.STRUCTURAL,
        structural_ref=parent_holon_id,
        metadata=metadata,
    )


def make_environ(
    environ_id: str,
    focal_holon_id: str,
    label: str,
    direction: str,  # "input" | "output"
    signal_channel: str = "both",  # "matter_energy" | "information" | "both"
    description: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create an Environ node — the environment surrounding a focal holon.

    Allen/Patten & Auble (1980): the environ comes in two forms:
        Input environ  — the part of the environment that feeds the creaon.
                         Allen Fig. 6: SPLIT into matter/energy channel AND
                         information channel (two distinct input environs).
        Output environ — the part of the environment that receives from the genon.
                         The world that reacts to the holon's narrative.

    The environ is another holon at a higher level (Allen Fig. 1a: "the
    environment is treated as simply another holon"). Its level relative to
    the focal holon depends on whether it's providing context (higher) or
    receiving output (same or higher).

    In HNC research context:
        Input environ  of experiment = dataset + literature + experimental context
        Output environ of experiment = paper section + KG update + reviewer response
        Input environ  of HNC        = raw byte stream (matter_energy) + task
                                       framing (information)
        Output environ of HNC        = user/benchmark (receives predictions)
    """
    if direction not in ("input", "output"):
        raise ValueError(f"direction must be 'input' or 'output', got {direction!r}")
    metadata = {
        "node_type": "environ",
        "focal_holon_id": focal_holon_id,
        "direction": direction,
        "signal_channel": signal_channel,
        "description": description,
        "allen_reference": "Allen & Giampietro (2014) Fig. 1c–1d, Fig. 6; Patten & Auble (1980)",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=environ_id,
        label=label or f"{direction.title()} environ of {focal_holon_id}",
        scale=2,  # context-level — environ is at higher level than focal holon
        layer=Layer.STRUCTURAL,
        metadata=metadata,
    )


# ======================== Epistemic Frontier Register (EFR) Node Type ========
# Source: DLL architecture — Zuluaga-Monroy & Zuluaga-Monroy (2026)
#         Bateson (1972) deutero-learning + Latour "matters of concern"
# =============================================================================


def make_efr_node(
    efr_id: str,
    claim: str,
    frontier_type: str,          # "transitional" | "methodological" | "ontological" | "undecidable"
    judgment_state: str = "MISSING_EVIDENCE",
    open_since: str = "",
    stabilization_attempts: list | None = None,
    stabilization_blocker: str = "",
    estimated_cost: str = "unknown",  # "low" | "medium" | "high" | "extreme"
    connected_papers: list | None = None,
    claims_unlocked: list | None = None,
    collaboration_opportunity: bool = False,
    dissolution_candidate: bool = False,
    notes: str = "",
    extra_metadata: Optional[dict] = None,
) -> Node:
    """Create an Epistemic Frontier Register node.

    EFR nodes represent claims that have been *investigated but not stabilised*
    — not because data is temporarily absent (that would be a QUEUED D-ID)
    but because the claim sits on the project's epistemic frontier.

    Four frontier types:
      "transitional"   — data could resolve it; not collected yet
      "methodological" — current methods cannot resolve it; needs innovation
      "ontological"    — IVM 12-slot schema cannot express the relation cleanly
      "undecidable"    — question has no resolution conditions; candidate for
                         Wittgensteinian dissolution/reformulation

    Design choice: scale=2 (hypothesis level), layer=STRUCTURAL.
    EFR nodes are coded blueprints of open questions — they describe a structure
    of ignorance, which is itself rate-independent (the question persists
    regardless of when it's observed).

    These nodes implement Bateson's Learning III at the knowledge level:
    the graph knowing what it doesn't know about itself.
    """
    _valid_types = ("transitional", "methodological", "ontological", "undecidable")
    if frontier_type not in _valid_types:
        raise ValueError(f"frontier_type must be one of {_valid_types}, got {frontier_type!r}")

    metadata = {
        "node_type":               "epistemic_frontier",
        "claim":                   claim,
        "frontier_type":           frontier_type,
        "judgment_state":          judgment_state,
        "open_since":              open_since,
        "stabilization_attempts":  stabilization_attempts or [],
        "stabilization_blocker":   stabilization_blocker,
        "estimated_cost":          estimated_cost,
        "connected_papers":        connected_papers or [],
        "claims_unlocked":         claims_unlocked or [],
        "collaboration_opportunity": collaboration_opportunity,
        "dissolution_candidate":   dissolution_candidate,
        "notes":                   notes,
        "allen_reference":         (
            "EFR implements 'matters of concern' (Latour) as KG nodes; "
            "frontier_type taxonomy from DLL architecture (2026)"
        ),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Node(
        id=efr_id,
        label=f"EFR[{frontier_type}]: {claim[:60]}",
        scale=2,
        layer=Layer.STRUCTURAL,
        active_since=open_since or None,
        metadata=metadata,
    )


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='node_types',
    scale=0,
    aristotelian_cause='formal',
    container=['core'],
    substrate=['core.schema'],
    description=(
        'Node-type factory functions: MethodologicalUnit, ResearchPattern, '
        'ReviewerComment, OperationalDistinction, Creaon, Genon, Environ, EFR'
    ),
)
