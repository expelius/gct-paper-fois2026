"""Diagnostics module — Whitehead + Wittgenstein integrations.

Surgical analysis functions on top of the v2 graph. Pure framework
applications, not contaminated by project-specific results.

Whitehead contributions (process philosophy):
  - Concrescence detection (many-prehension synthesis events)
  - Negative prehension counting (explicit exclusions)
  - Symbolic reference auditing (thermo→structural bridges)
  - Misplaced concreteness alarm (code-heavy, thermo-empty holons)
  - Society construction from functional uses (Tier 3a)

Wittgenstein contributions (language games):
  - Family resemblance scoring (slot+neighborhood Jaccard)
  - Language game classifier (empirical/theoretical/editorial/pragmatic)
  - Drift detection via low family resemblance among same-label uses

Each function takes a TensegrityGraph and returns analysis results;
no mutation of the graph itself (audit-only).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from .schema import Confidence, Edge, Layer, Node, Slot

if TYPE_CHECKING:
    from .builder import TensegrityGraph


# ============================================================================
# WITTGENSTEIN: Family resemblance + language games
# ============================================================================


def family_resemblance(graph: "TensegrityGraph", node_a_id: str, node_b_id: str) -> dict:
    """Wittgenstein's family resemblance score between two functional holons.

    Computed as weighted Jaccard over (a) slot-population patterns and
    (b) neighborhood overlap. Ranges 0.0 (no resemblance) to 1.0 (identical).

    Diagnostic interpretation:
      - >0.7  : same society (Whitehead) — candidate for consolidation
      - 0.3-0.7: genuine related-but-distinct uses — typical healthy
      - <0.3  : drift detected — same label being used in incompatible ways
    """
    if node_a_id not in graph._nodes or node_b_id not in graph._nodes:
        return {"score": 0.0, "error": "node not found"}
    node_a = graph._nodes[node_a_id]
    node_b = graph._nodes[node_b_id]

    # Slot Jaccard: which slots are populated in each
    slots_a = {s for s in Slot if node_a._slots_populated[s]}
    slots_b = {s for s in Slot if node_b._slots_populated[s]}
    slot_union = slots_a | slots_b
    slot_jaccard = (
        len(slots_a & slots_b) / len(slot_union) if slot_union else 0.0
    )

    # Neighborhood Jaccard: which other nodes are connected
    neighbors_a = set(graph.G.successors(node_a_id)) | set(graph.G.predecessors(node_a_id))
    neighbors_b = set(graph.G.successors(node_b_id)) | set(graph.G.predecessors(node_b_id))
    neigh_union = neighbors_a | neighbors_b
    neigh_jaccard = (
        len(neighbors_a & neighbors_b) / len(neigh_union) if neigh_union else 0.0
    )

    score = 0.5 * slot_jaccard + 0.5 * neigh_jaccard
    return {
        "score": round(score, 3),
        "slot_jaccard": round(slot_jaccard, 3),
        "neighborhood_jaccard": round(neigh_jaccard, 3),
        "interpretation": (
            "same_society" if score > 0.7
            else "drift_detected" if score < 0.3
            else "genuine_related"
        ),
    }


def detect_label_drift(graph: "TensegrityGraph", min_uses: int = 2) -> list[dict]:
    """Find nodes sharing label but with low family resemblance.

    Wittgenstein: same word, different language games = drift.
    Returns groups where the same label has uses with mutual resemblance < 0.3.
    """
    by_label: dict[str, list[str]] = defaultdict(list)
    for nid, n in graph._nodes.items():
        # Strip role-suffix to find canonical label
        # e.g., "HNC[as evidence for LT]" → "HNC"
        canonical = n.label.split("[")[0].strip()
        by_label[canonical].append(nid)

    drifts = []
    for label, node_ids in by_label.items():
        if len(node_ids) < min_uses:
            continue
        # Pairwise resemblance
        scores = []
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                fr = family_resemblance(graph, node_ids[i], node_ids[j])
                scores.append(((node_ids[i], node_ids[j]), fr["score"]))
        low_resemblance = [(pair, s) for pair, s in scores if s < 0.3]
        if low_resemblance:
            drifts.append({
                "label": label,
                "n_uses": len(node_ids),
                "low_resemblance_pairs": low_resemblance,
                "mean_score": round(sum(s for _, s in scores) / len(scores), 3),
            })
    return drifts


# ----- Language games (Wittgenstein) ----------------------------------------

def classify_language_game(graph: "TensegrityGraph", node_id: str) -> dict:
    """Classify a holon's dominant language game by slot signature.

    Four canonical games detected by which slots dominate the populated set:
      - empirical : THERMO + EFFECT + INSTANTIATION dominant
      - theoretical: CODE + SPECIFICATION + CONTAINER dominant
      - editorial : SUCCESSOR + PREDECESSOR + PEER_COHERENT dominant
      - pragmatic : SUBSTRATE + CONTAINER + mixed

    Returns dict with primary game + scores for each.
    """
    if node_id not in graph._nodes:
        return {"error": "node not found"}
    node = graph._nodes[node_id]

    # Count edges in each slot
    slot_counts = {s: len(node._slots_populated[s]) for s in Slot}

    games = {
        "empirical": (
            slot_counts[Slot.THERMO]
            + slot_counts[Slot.EFFECT]
            + slot_counts[Slot.INSTANTIATION]
        ),
        "theoretical": (
            slot_counts[Slot.CODE]
            + slot_counts[Slot.SPECIFICATION]
            + slot_counts[Slot.CONTAINER]
        ),
        "editorial": (
            slot_counts[Slot.SUCCESSOR]
            + slot_counts[Slot.PREDECESSOR]
            + slot_counts[Slot.PEER_COHERENT]
        ),
        "pragmatic": (
            slot_counts[Slot.SUBSTRATE]
            + slot_counts[Slot.CAUSE]
            + slot_counts[Slot.PEER_CONTRADICTORY]
        ),
    }
    total = sum(games.values()) or 1
    normalized = {k: round(v / total, 3) for k, v in games.items()}
    primary = max(normalized, key=normalized.get)
    # Game alignment ratio: how dominant is primary?
    sorted_scores = sorted(normalized.values(), reverse=True)
    dominance = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
    return {
        "primary_game": primary,
        "scores": normalized,
        "dominance": round(dominance, 3),
        "interpretation": (
            "clear" if dominance > 0.3
            else "mixed" if dominance > 0.1
            else "ambiguous"
        ),
    }


# ============================================================================
# WHITEHEAD: Concrescence + negative prehensions + misplaced concreteness
# ============================================================================


def detect_concrescence_events(
    graph: "TensegrityGraph",
    time_window_days: int = 7,
    min_prehensions: int = 3,
) -> list[dict]:
    """Find nodes that synthesized multiple prior prehensions in a short window.

    Whitehead's concrescence: many → one. A new actual occasion that
    incorporates ≥N prior occasions within a short time window.

    Diagnostic of: synthesis events (R-pivot adoptions, new D-XXX combining
    prior experiments, paper merges).
    """
    cutoff = datetime.now() - timedelta(days=time_window_days)
    events = []
    for nid, node in graph._nodes.items():
        try:
            created = datetime.fromisoformat(node.active_since)
        except (ValueError, TypeError):
            continue
        if created < cutoff:
            continue
        in_edges = list(graph.G.in_edges(nid, keys=True))
        out_edges = list(graph.G.out_edges(nid, keys=True))
        n_prehensions = len(in_edges) + len(out_edges)
        if n_prehensions >= min_prehensions:
            sources = list({e[0] for e in in_edges} | {e[1] for e in out_edges})
            events.append({
                "occasion": nid,
                "label": node.label,
                "scale": node.scale,
                "n_prehensions": n_prehensions,
                "synthesized_from": sources,
                "timestamp": node.active_since,
            })
    return sorted(events, key=lambda e: -e["n_prehensions"])


def negative_prehension_summary(graph: "TensegrityGraph") -> dict:
    """Count and categorize negative prehensions (Whitehead's explicit exclusions).

    Useful for: tracking gaps-by-design vs gaps-by-oversight.
    """
    neg_edges = [
        e for e in graph._edges.values() if e.negative_prehension
    ]
    by_slot = defaultdict(int)
    for e in neg_edges:
        by_slot[e.slot.name] += 1
    by_confidence = defaultdict(int)
    for e in neg_edges:
        by_confidence[e.confidence.value] += 1
    return {
        "total_negative_prehensions": len(neg_edges),
        "by_slot": dict(by_slot),
        "by_confidence": dict(by_confidence),
        "examples": [
            {"source": e.source, "target": e.target, "slot": e.slot.name, "evidence": e.evidence}
            for e in neg_edges[:5]
        ],
    }


def detect_misplaced_concreteness(
    graph: "TensegrityGraph",
    code_threshold: int = 3,
    thermo_threshold: int = 0,
) -> list[dict]:
    """Whitehead's misplaced concreteness: treating an abstraction as a thing.

    Diagnostic: structural holon with many code-face slots populated
    (CODE, SPECIFICATION, PREDECESSOR, CAUSE, CONTAINER, PEER_COHERENT —
    the strut slots) but NO thermodynamic counterpart linkage.

    Means: the concept is heavily defined but not behaviorally backed.
    Suspected over-formalization.
    """
    code_slots = [Slot.CODE, Slot.SPECIFICATION, Slot.PREDECESSOR,
                  Slot.CAUSE, Slot.CONTAINER, Slot.PEER_COHERENT]
    thermo_slots = [Slot.THERMO, Slot.INSTANTIATION, Slot.SUCCESSOR,
                    Slot.EFFECT, Slot.SUBSTRATE, Slot.PEER_CONTRADICTORY]
    suspects = []
    for nid, node in graph._nodes.items():
        if node.layer != Layer.STRUCTURAL:
            continue
        n_code = sum(len(node._slots_populated[s]) for s in code_slots)
        n_thermo = sum(len(node._slots_populated[s]) for s in thermo_slots)
        if n_code >= code_threshold and n_thermo <= thermo_threshold:
            # Check for thermo-layer counterpart
            has_thermo_counterpart = any(
                n.layer == Layer.THERMODYNAMIC and n.structural_ref == nid
                for n in graph._nodes.values()
            )
            if not has_thermo_counterpart:
                suspects.append({
                    "node": nid,
                    "label": node.label,
                    "n_code_slots": n_code,
                    "n_thermo_slots": n_thermo,
                    "diagnosis": "heavily defined, no behavioral backing",
                })
    return suspects


def audit_symbolic_reference(graph: "TensegrityGraph") -> dict:
    """Whitehead's symbolic reference audit — thermo nodes need structural bridge.

    A thermodynamic observation without symbolic reference to a structural
    concept is "naked data" — observable but not interpretable. Symbol
    bridges presentational immediacy (thermo) to causal efficacy (structural).
    """
    thermo_nodes = [
        n for n in graph._nodes.values() if n.layer == Layer.THERMODYNAMIC
    ]
    naked = [
        n for n in thermo_nodes
        if n.structural_ref is None or n.structural_ref not in graph._nodes
    ]
    bridged = [n for n in thermo_nodes if n not in naked]
    return {
        "total_thermodynamic": len(thermo_nodes),
        "bridged_count": len(bridged),
        "naked_count": len(naked),
        "naked_nodes": [
            {"id": n.id, "label": n.label, "missing_ref": n.structural_ref}
            for n in naked[:10]
        ],
        "interpretation": (
            "all observations interpreted" if not naked
            else f"{len(naked)} naked observation(s) — need symbolic anchoring"
        ),
    }


# ============================================================================
# TIER 3a: Society construction from functional uses (Whitehead + Wittgenstein)
# ============================================================================


def consolidate_societies(
    graph: "TensegrityGraph",
    resemblance_threshold: float = 0.7,
    min_uses: int = 2,
) -> list[dict]:
    """Construct structural societies from clusters of functional uses.

    Reverses the layer priority: instead of structural → functional spawned,
    structural EMERGES as the family-resemblance cluster of functional uses.

    For each label appearing in ≥min_uses functional holons, compute
    pairwise resemblance; cluster nodes with mutual score ≥threshold;
    each cluster proposes a structural society meta-node.

    Output is a PROPOSAL — does not mutate the graph. User reviews and
    materializes societies via builder.materialize_society().

    Whitehead's society: thread of actual occasions sharing defining
    characteristic. Wittgenstein's family resemblance: overlapping
    similarities, not essential definition.
    """
    # Group nodes by canonical label (strip role suffixes)
    by_label: dict[str, list[str]] = defaultdict(list)
    for nid, n in graph._nodes.items():
        if n.layer != Layer.FUNCTIONAL:
            continue
        canonical = n.label.split("[")[0].strip()
        by_label[canonical].append(nid)

    societies = []
    for label, node_ids in by_label.items():
        if len(node_ids) < min_uses:
            continue
        # Build adjacency: i resembles j if score >= threshold
        n = len(node_ids)
        adj = [[False] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                fr = family_resemblance(graph, node_ids[i], node_ids[j])
                if fr["score"] >= resemblance_threshold:
                    adj[i][j] = adj[j][i] = True
        # Find connected components in resemblance graph
        seen = [False] * n
        clusters = []
        for i in range(n):
            if seen[i]:
                continue
            cluster = []
            stack = [i]
            while stack:
                k = stack.pop()
                if seen[k]:
                    continue
                seen[k] = True
                cluster.append(node_ids[k])
                for m in range(n):
                    if adj[k][m] and not seen[m]:
                        stack.append(m)
            clusters.append(cluster)

        # Propose a society for each cluster
        for cluster in clusters:
            if len(cluster) >= min_uses:
                societies.append({
                    "label": label,
                    "members": cluster,
                    "proposed_structural_id": f"society_{label.lower().replace(' ', '_')}",
                    "n_members": len(cluster),
                    "rationale": (
                        f"{len(cluster)} functional uses of '{label}' "
                        f"with mutual family resemblance ≥{resemblance_threshold}"
                    ),
                })
    return societies


# ============================================================================
# TIER 3b: Event-first API (radical Whitehead)
# ============================================================================


def edge_centered_view(graph: "TensegrityGraph") -> dict:
    """Edge-first view: edges as primary actual occasions, nodes as patterns.

    Doesn't refactor the graph — provides an alternative READING where
    each edge is an event of prehension, and node identity is the
    stable pattern of edge participation.

    Returns:
      - events: list of edges as Whitehead actual occasions
      - patterns: groups of nodes with identical participation signatures
    """
    events = [
        {
            "occasion_id": eid,
            "subject": e.source,         # the prehending occasion
            "object": e.target,          # what is prehended
            "subjective_form": e.slot.name,  # how it's grasped
            "polarity": "negative" if e.negative_prehension else "positive",
            "confidence": e.confidence.value,
            "timestamp": e.created_at,
        }
        for eid, e in graph._edges.items()
    ]

    # Compute participation signatures: which slots each node appears in
    sigs: dict[str, tuple] = {}
    for nid, n in graph._nodes.items():
        sig_in = tuple(sorted(
            (s.name, len(n._slots_populated[s])) for s in Slot
        ))
        sigs[nid] = sig_in

    # Cluster nodes by identical signature → these form Whitehead "patterns"
    pattern_groups: dict[tuple, list[str]] = defaultdict(list)
    for nid, sig in sigs.items():
        pattern_groups[sig].append(nid)
    patterns = [
        {
            "signature_hash": hash(sig),
            "members": members,
            "n_members": len(members),
        }
        for sig, members in pattern_groups.items() if len(members) >= 2
    ]

    return {
        "n_events": len(events),
        "n_patterns": len(patterns),
        "patterns_sample": patterns[:5],
        "view": "edge_first_whitehead",
    }


# ============================================================================
# Top-level diagnostic report
# ============================================================================


def full_diagnostic_report(graph: "TensegrityGraph") -> dict:
    """Run all diagnostics — Tier 1, 2, 3 — and return consolidated output."""
    return {
        # Tier 1 — Wittgenstein
        "wittgenstein": {
            "label_drift": detect_label_drift(graph),
            "language_games": {
                nid: classify_language_game(graph, nid)
                for nid in list(graph._nodes.keys())[:20]  # sample to keep output bounded
            },
        },
        # Tier 1 — Whitehead
        "whitehead": {
            "concrescence_events": detect_concrescence_events(graph),
            "negative_prehensions": negative_prehension_summary(graph),
        },
        # Tier 2
        "tier_2": {
            "misplaced_concreteness_suspects": detect_misplaced_concreteness(graph),
            "symbolic_reference_audit": audit_symbolic_reference(graph),
        },
        # Tier 3
        "tier_3": {
            "society_proposals": consolidate_societies(graph),
            "edge_first_view": edge_centered_view(graph),
        },
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='diagnostics',
    scale=1,
    aristotelian_cause='final',
    container=['core'],
    substrate=['core.schema', 'core.builder'],
    effect=['structural quality reports'],
    description='Quality/health diagnostics over the graph',
)
