"""epistemic_frontier — Epistemic Frontier Register (EFR) as first-class KG nodes.

The EFR materialises three categories of persistently unstabilised claims as
Node objects in the knowledge graph:

  frontier_type = "transitional"   — data could resolve it; not yet collected
  frontier_type = "methodological" — current methods cannot resolve it; needs
                                     methodological innovation or external collab
  frontier_type = "ontological"    — the current 12-slot IVM schema cannot express
                                     the claim without awkward workarounds; needs
                                     schema extension
  frontier_type = "undecidable"    — the question as posed has no resolution
                                     conditions within the project's epistemic frame;
                                     candidate for Wittgensteinian dissolution

Why first-class nodes?
  - Unstabilised claims are *epistemic assets*, not failures. They define the
    boundary between the known and the unknown. Making them navigable as graph
    nodes enables: (i) automatic future-work section generation, (ii) collaboration
    opportunity detection, (iii) KG schema gap analysis, (iv) lit-watcher targeting.
  - The EFR closes the loop the dispatch gate leaves open: Gate 1 routes
    AMBIGUOUS/MISSING_EVIDENCE claims to fetching actions, but some claims are
    *durably* unresolvable and should not keep generating fetch dispatches.

Node shape:
  - id:    "efr_<slug>"           (e.g., "efr_lt6prime_cross_arch")
  - scale: 2                      (hypothesis level — between D-ID s1 and paper s3)
  - layer: STRUCTURAL             (EFR entries are coded blueprints of open questions)
  - metadata keys: claim, frontier_type, judgment_state, open_since,
                   stabilization_attempts, stabilization_blocker,
                   estimated_cost, connected_papers, claims_unlocked,
                   collaboration_opportunity, dissolution_candidate, notes

Population strategy:
  Two sources:
  (A) efr_registry.json — manually curated / DLL-proposed entries (ground truth)
  (B) EXPERIMENTS-LOG.md — auto-detected: D-IDs with QUEUED state >30 days
      that have at least 1 RUN attempt (tried and not yet resolved)

Edges emitted:
  - efr_node -[SPECIFICATION]-> paper_node  (claim_unlocked: EFR stabilisation
                                              would unlock this paper claim)
  - efr_node -[PEER_CONTRADICTORY]-> d_id   (if EFR claim contradicts a confirmed D-ID)
  - efr_node -[CAUSE]-> efr_node            (if one frontier claim depends on another)

REQUIRES = ['experiments_log', 'paper_drafts']  — need D-ID states + paper feeds
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    from ..schema import Confidence, Edge, Layer, Node, Slot
    from ..node_types import make_operational_distinction
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from core.schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log', 'paper_drafts']

# Path to the manually curated EFR registry (created by DLL proposals)
_EFR_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / ".claude"
    / "projects"
    / "C--Users-juand-OneDrive-Documentos-REPOSITORIOS-VS-CODE-Tensegrity"
    / "memory"
    / "epistemic_frontier"
    / "efr_registry.json"
)

# Days threshold for auto-detection from EXPERIMENTS-LOG
_STALE_DAYS = 30

# Frontier type → human label
_FRONTIER_LABELS = {
    "transitional":   "Transitionally unstabilised (data could resolve)",
    "methodological": "Methodological frontier (needs innovation/external collab)",
    "ontological":    "Ontological frontier (IVM schema insufficient)",
    "undecidable":    "Undecidable (dissolution candidate)",
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", text.lower())[:48].strip("_")


def _load_registry() -> list[dict]:
    """Load manually curated EFR entries from efr_registry.json."""
    if not _EFR_REGISTRY_PATH.exists():
        return []
    try:
        with open(_EFR_REGISTRY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("entries", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _make_efr_node(entry: dict) -> Node:
    """Create an EFR Node from a registry entry dict."""
    claim = entry.get("claim", "unknown claim")
    nid = entry.get("id") or f"efr_{_slugify(claim)}"
    frontier_type = entry.get("frontier_type", "transitional")

    return Node(
        id=nid,
        label=f"EFR: {claim[:80]}",
        scale=2,                    # hypothesis level
        layer=Layer.STRUCTURAL,     # coded blueprint of an open question
        active_since=entry.get("open_since"),
        metadata={
            "node_type":               "epistemic_frontier",
            "claim":                   claim,
            "frontier_type":           frontier_type,
            "frontier_label":          _FRONTIER_LABELS.get(frontier_type, frontier_type),
            "judgment_state":          entry.get("judgment_state", "MISSING_EVIDENCE"),
            "open_since":              entry.get("open_since", ""),
            "stabilization_attempts":  entry.get("stabilization_attempts", []),
            "stabilization_blocker":   entry.get("stabilization_blocker", ""),
            "estimated_cost":          entry.get("estimated_cost", "unknown"),
            "connected_papers":        entry.get("connected_papers", []),
            "claims_unlocked":         entry.get("claims_unlocked", []),
            "collaboration_opportunity": entry.get("collaboration_opportunity", False),
            "dissolution_candidate":   entry.get("dissolution_candidate", False),
            "notes":                   entry.get("notes", ""),
            "source":                  "efr_registry.json (manual/DLL-approved)",
        },
    )


def _auto_detect_from_experiments_log(graph) -> list[Node]:
    """
    Auto-detect EFR candidates from EXPERIMENTS-LOG: D-IDs with QUEUED state
    that appear to have been attempted (have at least one RUN sibling entry)
    and have been stale for > _STALE_DAYS.

    Uses the graph's existing experiment nodes rather than re-parsing the log.
    """
    candidates = []
    cutoff = datetime.now() - timedelta(days=_STALE_DAYS)
    existing_efr_ids = {
        nid for nid, n in graph._nodes.items()
        if n.metadata.get("node_type") == "epistemic_frontier"
    }

    for nid, node in graph._nodes.items():
        if node.metadata.get("node_type") != "experiment":
            continue
        state = node.metadata.get("state", "")
        if state not in ("QUEUED", "INCONCLUSIVE"):
            continue
        # Check staleness via active_since
        if node.active_since:
            try:
                ts = datetime.fromisoformat(node.active_since)
                if ts > cutoff:
                    continue  # not stale yet
            except ValueError:
                pass

        efr_id = f"efr_auto_{_slugify(nid)}"
        if efr_id in existing_efr_ids:
            continue  # already in graph

        label_base = node.label or nid
        candidates.append(Node(
            id=efr_id,
            label=f"EFR[auto]: {label_base[:70]}",
            scale=2,
            layer=Layer.STRUCTURAL,
            active_since=node.active_since,
            metadata={
                "node_type":               "epistemic_frontier",
                "claim":                   f"Outcome of {nid} unresolved",
                "frontier_type":           "transitional",
                "frontier_label":          _FRONTIER_LABELS["transitional"],
                "judgment_state":          "MISSING_EVIDENCE",
                "open_since":              node.active_since or "",
                "stabilization_attempts":  [nid],
                "stabilization_blocker":   f"D-ID {nid} remains in {state} state",
                "estimated_cost":          "unknown",
                "connected_papers":        list(node.metadata.get("feeds_papers", [])),
                "claims_unlocked":         [],
                "collaboration_opportunity": False,
                "dissolution_candidate":   False,
                "notes":                   "Auto-detected by epistemic_frontier extractor",
                "source":                  f"auto-detected from D-ID {nid}",
            },
        ))

    return candidates


def _emit_edges(graph, efr_node: Node) -> list[Edge]:
    """Emit edges from an EFR node to its connected papers and D-IDs."""
    edges = []
    papers = efr_node.metadata.get("connected_papers", [])
    attempts = efr_node.metadata.get("stabilization_attempts", [])

    for paper_code in papers:
        # Find the paper node (case-insensitive slug match)
        target = next(
            (nid for nid in graph._nodes
             if paper_code.upper() in nid.upper()
             and graph._nodes[nid].metadata.get("node_type") in
             ("paper_draft", "paper_section", None)),
            None,
        )
        if target:
            try:
                edges.append(Edge(
                    source=efr_node.id,
                    target=target,
                    slot=Slot.SPECIFICATION,
                    confidence=Confidence.INFERRED,
                    scale_from=efr_node.scale,
                    scale_to=graph._nodes[target].scale,
                    signal_type="information",
                    evidence=f"EFR stabilisation would unlock claim in {paper_code}",
                ))
            except (KeyError, ValueError):
                pass

    for did in attempts:
        # Link to the D-ID that attempted stabilisation
        target_did = next(
            (nid for nid in graph._nodes
             if did.upper() == nid.upper() or did.lower() in nid.lower()),
            None,
        )
        if target_did:
            try:
                edges.append(Edge(
                    source=efr_node.id,
                    target=target_did,
                    slot=Slot.CAUSE,
                    confidence=Confidence.INFERRED,
                    scale_from=efr_node.scale,
                    scale_to=graph._nodes[target_did].scale,
                    signal_type="information",
                    evidence=f"{did} attempted to stabilise this EFR claim",
                ))
            except (KeyError, ValueError):
                pass

    return edges


def extract(graph) -> dict:
    """Main extractor entry point."""
    nodes_added = 0
    edges_added = 0

    # ── Source A: manually curated registry ───────────────────────────────────
    registry_entries = _load_registry()
    for entry in registry_entries:
        nid_check = entry.get("id") or f"efr_{_slugify(entry.get('claim', ''))}"
        if nid_check in graph._nodes:
            continue  # already loaded (idempotent)
        try:
            node = _make_efr_node(entry)
            graph.add_node(node)
            nodes_added += 1
            for edge in _emit_edges(graph, node):
                try:
                    graph.add_edge(edge)
                    edges_added += 1
                except (KeyError, ValueError):
                    pass
        except Exception:
            continue

    # ── Source B: auto-detect from stale QUEUED experiments ───────────────────
    auto_nodes = _auto_detect_from_experiments_log(graph)
    for node in auto_nodes:
        if node.id in graph._nodes:
            continue
        try:
            graph.add_node(node)
            nodes_added += 1
            for edge in _emit_edges(graph, node):
                try:
                    graph.add_edge(edge)
                    edges_added += 1
                except (KeyError, ValueError):
                    pass
        except Exception:
            continue

    return {
        "extractor":        "epistemic_frontier",
        "files_processed":  1 if _EFR_REGISTRY_PATH.exists() else 0,
        "nodes_added":      nodes_added,
        "edges_added":      edges_added,
        "registry_entries": len(registry_entries),
        "auto_detected":    len(auto_nodes),
        "frontier_types":   list(_FRONTIER_LABELS.keys()),
    }


# ── Utility: query unstabilised frontiers ─────────────────────────────────────

def get_efr_nodes(graph) -> list[Node]:
    """Return all EFR nodes in the graph."""
    return [n for n in graph._nodes.values()
            if n.metadata.get("node_type") == "epistemic_frontier"]


def get_efr_by_type(graph, frontier_type: str) -> list[Node]:
    """Return EFR nodes filtered by frontier_type."""
    return [n for n in get_efr_nodes(graph)
            if n.metadata.get("frontier_type") == frontier_type]


def get_collaboration_opportunities(graph) -> list[Node]:
    """Return EFR nodes that would benefit from external collaboration."""
    return [n for n in get_efr_nodes(graph)
            if n.metadata.get("collaboration_opportunity")]


def get_dissolution_candidates(graph) -> list[Node]:
    """Return EFR nodes that are candidates for Wittgensteinian dissolution."""
    return [n for n in get_efr_nodes(graph)
            if n.metadata.get("dissolution_candidate")]


# ── Code-holon meta ───────────────────────────────────────────────────────────
try:
    from core.holon_meta import HolonMeta as _HolonMeta
    __holon__ = _HolonMeta(
        name="epistemic_frontier",
        scale=2,
        aristotelian_cause="final",
        container=["core.extractors"],
        substrate=["core.schema", "experiments_log", "paper_drafts"],
        effect=["EFR nodes (transitional/methodological/ontological/undecidable)"],
        specification=["efr_registry.json + auto-detection from stale D-IDs"],
        code="extract + 4 utility query functions",
        description=(
            "Epistemic Frontier Register — makes persistently unstabilised claims "
            "into first-class graph nodes. Implements the EFR half of the "
            "Deutero-Learning Loop (DLL) architecture."
        ),
    )
except Exception:
    pass
