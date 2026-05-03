"""Pre-computation of viz-layer data into the snapshot JSON.

The carousel currently computes things like connected components, citation
filament edges, and dominant-attractor-per-snapshot in JavaScript at load
time. This module moves that computation to Python (build time) and bakes
the results into the snapshot JSON as top-level keys:

    "viz_components": [{nodes: [...], centroid: [..], radius: ..}, ...]
    "viz_citation_edges": [{source, target, source_type, target_type}, ...]
    "viz_dominant_polyhedron": "octahedron"
    "viz_polyhedron_rules": [...]    (the rule list itself, for the carousel
                                      JS to read instead of hardcoding)

This way:
  - The CLI (`query_graph.py`) and the carousel agree on the same numbers
  - The carousel renders faster (no client-side union-find)
  - Tests can assert on these properties
  - The polyhedron-picking heuristic is a single source of truth (JSON)

Called from `enrich_with_maxims.py` post-build.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

# Load the polyhedron rules once at import time
_RULES_PATH = Path(__file__).parent / "polyhedron_rules.json"
_POLYHEDRON_RULES = json.loads(_RULES_PATH.read_text(encoding="utf-8"))["rules"]


PAPER_TYPES = {"paper", "paper_section", "pillar"}
CITED_TYPES = {
    "experiment", "concept", "external_reference", "json_result",
    "cross_cut", "rpivot", "prereg_prediction",
}


def compute_connected_components(graph_dict: dict) -> list[dict]:
    """Union-find over the graph's edges.

    Returns a list of components, each:
        {nodes: [id...], size: int, sample_label: str}
    Sorted by size descending.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for n in graph_dict["nodes"]:
        parent[n["id"]] = n["id"]
    for e in graph_dict["edges"]:
        if e["source"] in parent and e["target"] in parent:
            union(e["source"], e["target"])

    buckets: dict[str, list[str]] = defaultdict(list)
    for nid in parent:
        buckets[find(nid)].append(nid)

    label_lookup = {n["id"]: n.get("label", "")[:40] for n in graph_dict["nodes"]}
    out = []
    for root, nodes in buckets.items():
        out.append({
            "root": root,
            "nodes": nodes,
            "size": len(nodes),
            "sample_label": label_lookup.get(nodes[0], ""),
        })
    out.sort(key=lambda c: -c["size"])
    return out


def compute_citation_edges(graph_dict: dict) -> list[dict]:
    """Identify the subset of edges that constitute citations: paper-y source
    to cited-y target. Returned as a flat list with type annotations the
    carousel uses to color the filaments."""
    type_lookup = {n["id"]: (n.get("metadata", {}) or {}).get("node_type", "")
                   for n in graph_dict["nodes"]}
    out = []
    for e in graph_dict["edges"]:
        st = type_lookup.get(e["source"], "")
        tt = type_lookup.get(e["target"], "")
        if st in PAPER_TYPES and tt in CITED_TYPES:
            out.append({
                "source": e["source"], "target": e["target"],
                "source_type": st, "target_type": tt,
                "slot": e["slot"],
            })
    return out


def compute_dominant_polyhedron(graph_dict: dict) -> dict:
    """Counts holons per polyhedron type using the same heuristic as
    `pickPolyhedronForHolon` in viz/polyhedra.js. Returns the dominant type
    + share + secondary, matching the dominantPolyhedronOf() behavior the
    carousel currently does in JS."""
    counts: dict[str, int] = defaultdict(int)
    for n in graph_dict["nodes"]:
        if n.get("layer") != "structural":
            continue
        poly = _pick_polyhedron(n)
        counts[poly] += 1
    if not counts:
        return {"name": "cuboctahedron", "count": 0, "share": 0, "transitional": False}

    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    primary, primary_count = ranked[0]
    secondary = ranked[1] if len(ranked) > 1 else None
    total = sum(counts.values())
    primary_share = primary_count / total
    if primary_share < 0.6 and secondary and secondary[1] / primary_count > 0.75:
        return {
            "name": "jitterbug:0.5", "count": primary_count + secondary[1],
            "share": primary_share, "transitional": True,
            "primary": primary, "secondary": secondary[0],
            "all_counts": dict(counts),
        }
    return {
        "name": primary, "count": primary_count,
        "share": primary_share, "transitional": False,
        "all_counts": dict(counts),
    }


def _matches_when(when: dict, node_attrs: dict) -> bool:
    """Evaluate whether a rule's `when` clause matches the node's attributes.

    Supported keys in `when`:
        scale_eq, scale_in, ve_min, ve_max, prestress_min, prestress_max,
        saturation_min, saturation_max
    Empty dict {} matches anything (used for ultimate_fallback rule).
    """
    s = node_attrs["scale"]
    v = node_attrs["ve"]
    p = node_attrs["ps"]
    sat = node_attrs["sat"]
    if "scale_eq" in when and s != when["scale_eq"]: return False
    if "scale_in" in when and s not in when["scale_in"]: return False
    if "ve_min" in when and v < when["ve_min"]: return False
    if "ve_max" in when and v > when["ve_max"]: return False
    if "prestress_min" in when and p < when["prestress_min"]: return False
    if "prestress_max" in when and p > when["prestress_max"]: return False
    if "saturation_min" in when and sat < when["saturation_min"]: return False
    if "saturation_max" in when and sat > when["saturation_max"]: return False
    return True


def _pick_polyhedron(node: dict) -> str:
    """Apply the declarative polyhedron rules from polyhedron_rules.json.

    First matching rule wins. The JSON file is the single source of truth —
    update it to adjust polyhedron picking; both this Python implementation
    and the JS carousel (when it adopts the JSON) stay in sync automatically.
    """
    node_attrs = {
        "scale": node.get("scale", 1),
        "ve": node.get("ve_score_harmonic", node.get("ve_score", 0)) or 0,
        "ps": node.get("prestress_local", 0) or 0,
        "sat": node.get("saturation", 0) or 0,
    }
    for rule in _POLYHEDRON_RULES:
        if _matches_when(rule.get("when", {}), node_attrs):
            return rule["pick"]
    return "octahedron"   # should never reach (ultimate_fallback covers it)


def compute_porphyrian_relations(graph_dict: dict) -> dict[str, dict]:
    """Per-node taxonomic relations baked into the snapshot for fast carousel overlays.

    For each STRUCTURAL node, compute its genera (CONTAINER parents) and
    species (CONTAINER children). The carousel renders Porphyrian overlays
    on click without round-tripping to Python.
    """
    out: dict[str, dict] = {}
    for n in graph_dict["nodes"]:
        if n.get("layer") != "structural":
            continue
        nid = n["id"]
        genera = []
        species = []
        for e in graph_dict["edges"]:
            if e.get("slot") != "CONTAINER":
                continue
            if e["target"] == nid:
                genera.append(e["source"])
            elif e["source"] == nid:
                species.append(e["target"])
        if genera or species:
            out[nid] = {
                "genera": list(dict.fromkeys(genera))[:8],
                "species": list(dict.fromkeys(species))[:20],
            }
    return out


def compute_wittgenstein_neighbors(graph_dict: dict, top_k: int = 5) -> dict[str, list]:
    """Per-CONCEPT family-resemblance neighbors baked into the snapshot.

    Reuses `core.wittgenstein_search.family_resemblance` to precompute the
    top-K family neighbors of each curated concept. The carousel renders
    family-resemblance pulse rings on concept clicks.
    """
    try:
        from .wittgenstein_search import family_resemblance
    except ImportError:
        return {}
    out: dict[str, list] = {}
    for n in graph_dict["nodes"]:
        md = n.get("metadata") or {}
        if md.get("node_type") != "concept":
            continue
        try:
            results = family_resemblance(graph_dict, n["id"],
                                         measure="cosine", top_k=top_k,
                                         min_score=0.3)
            if results:
                out[n["id"]] = [
                    {"id": r["concept_id"], "score": r["score"]}
                    for r in results
                ]
        except Exception:
            continue
    return out


def compute_wittgenstein_neighbors_by_neighborhood(
    graph_dict: dict,
    target_types: set | None = None,
    top_k: int = 5,
) -> dict[str, list]:
    """Family resemblance via neighbor-set Jaccard for experiment / paper / paper_section.

    Extends the document co-occurrence method (concept-only) to the three
    most semantically meaningful non-concept node types.  Two nodes are
    'family' if they share many graph neighbors — operationalized per type:

    - experiment: full undirected neighbor set (concepts + sections + results).
      Threshold 0.15, min_neighbors=2.  Captures shared conceptual substrate.

    - paper: project to EXPERIMENT-type neighbors only before Jaccard.
      Threshold 0.10, min_neighbors=1.  Avoids the container-section dilution
      problem (each paper's ~10 unique paper_section children would otherwise
      dominate the union and collapse Jaccard to near zero).

    - paper_section: full neighbor set. Threshold 0.15, min_neighbors=2.

    Computed within-type (experiments vs. experiments, etc.).
    Complexity: O(n²) per type — tractable at current scale.
    """
    if target_types is None:
        target_types = {"experiment", "paper", "paper_section"}

    node_type_map = {
        n["id"]: (n.get("metadata") or {}).get("node_type", "")
        for n in graph_dict["nodes"]
    }

    # Full undirected neighbor sets
    neighbors: dict[str, set] = defaultdict(set)
    for e in graph_dict["edges"]:
        s, t = e.get("source"), e.get("target")
        if s and t:
            neighbors[s].add(t)
            neighbors[t].add(s)

    def _paper_exp_neighbors(nid: str) -> set:
        """Experiments reachable from a paper in 1 or 2 hops.

        1-hop: experiment directly connected to paper (e.g. via paper_drafts
               extractor citation edges: D-101 --CAUSE--> P1).
        2-hop: paper --CONTAINER--> section --CAUSE--> experiment.
               Needed for root paper nodes (P0, P2, P4…) whose experiments
               connect through section intermediaries, not directly.
        """
        result: set = set()
        for nb in neighbors.get(nid, set()):
            nt = node_type_map.get(nb, "")
            if nt == "experiment":
                result.add(nb)
            elif nt == "paper_section":
                for nb2 in neighbors.get(nb, set()):
                    if node_type_map.get(nb2, "") == "experiment":
                        result.add(nb2)
        return result

    # Per-type parameters: (min_neighbors, min_score, neighbor_fn)
    TYPE_CONFIG = {
        "experiment":    (1, 0.15, lambda nid: neighbors[nid]),
        "paper":         (1, 0.10, _paper_exp_neighbors),
        "paper_section": (2, 0.15, lambda nid: neighbors[nid]),
    }

    # Group candidates by type
    groups: dict[str, list] = defaultdict(list)
    for n in graph_dict["nodes"]:
        nt = node_type_map.get(n["id"], "")
        if nt not in target_types:
            continue
        cfg = TYPE_CONFIG.get(nt)
        if cfg is None:
            continue
        min_nb, _, nb_fn = cfg
        if len(nb_fn(n["id"])) >= min_nb:
            groups[nt].append(n["id"])

    out: dict[str, list] = {}
    for nt, members in groups.items():
        min_nb, min_score, nb_fn = TYPE_CONFIG[nt]
        for nid in members:
            nb_a = nb_fn(nid)
            if not nb_a:
                continue
            scores = []
            for oid in members:
                if oid == nid:
                    continue
                nb_b = nb_fn(oid)
                union_size = len(nb_a | nb_b)
                if union_size == 0:
                    continue
                score = len(nb_a & nb_b) / union_size
                if score >= min_score:
                    scores.append({"id": oid, "score": round(score, 4)})
            scores.sort(key=lambda x: -x["score"])
            if scores:
                out[nid] = scores[:top_k]

    return out


def compute_inherited_grounding(graph_dict: dict) -> dict[str, dict]:
    """Per-node inherited evidential grounding: experiment nodes that support
    a concept/paper/pillar via the actual epistemic chain in this graph.

    The real chain (verified by edge inspection 2026-04-30) is:
        concept_hnc  ←[PEER_COHERENT]─  P1
                          P1  ─[CONTAINER]→  P1_section_4
                               P1_section_4  ─[CAUSE]→  D-101

    So we need a MIXED-DIRECTION traversal:
      Step 1 (reverse): from concept/pillar, follow incoming PEER_COHERENT
                        edges to reach papers.
      Step 2 (forward): from papers, follow outgoing CONTAINER edges to
                        reach paper sections.
      Step 3 (forward): from sections, follow outgoing CAUSE/EFFECT edges to
                        reach experiment nodes.

    We also handle deeper chains (sections cite concepts directly via SPECIFICATION,
    experiments are also reached via SPECIFICATION from prereg nodes, etc.) by
    running additional passes with broader forward adjacency.

    Returns:
        dict: node_id → {
            "n_experiments":  int,    # experiment nodes reachable via this chain
            "experiment_ids": list,   # up to 20 IDs for carousel display
        }
    """
    node_type = {
        n["id"]: (n.get("metadata") or {}).get("node_type", "")
        for n in graph_dict["nodes"]
    }

    # Build adjacency indexes for the needed traversals
    # incoming_peer[concept_id] = [paper_ids that have PEER_COHERENT → concept]
    incoming_peer: dict[str, list[str]] = {}
    # forward_container[paper_id] = [section_ids it contains]
    forward_container: dict[str, list[str]] = {}
    # forward_cause[section_id] = [experiment_ids it caused/required]
    forward_cause_effect: dict[str, list[str]] = {}
    # incoming_spec[concept_id] = [section/paper_ids that SPECIFICATION → concept]
    incoming_spec: dict[str, list[str]] = {}
    # For wider net: any source → experiment via EFFECT
    forward_effect: dict[str, list[str]] = {}

    for e in graph_dict["edges"]:
        s, t, slot = e["source"], e["target"], e.get("slot", "")
        if slot == "PEER_COHERENT":
            incoming_peer.setdefault(t, []).append(s)
        elif slot == "CONTAINER":
            forward_container.setdefault(s, []).append(t)
        elif slot == "CAUSE":
            forward_cause_effect.setdefault(s, []).append(t)
        elif slot == "EFFECT":
            forward_effect.setdefault(s, []).append(t)
            # Also: experiment ─EFFECT→ paper_section means experiment feeds section
            # which is useful for going the other direction; we handle via reverse
        elif slot == "SPECIFICATION":
            incoming_spec.setdefault(t, []).append(s)

    def experiments_for_node(node_id: str) -> set[str]:
        """Return experiment IDs that ground this node via the actual edge chain."""
        exps: set[str] = set()
        nt = node_type.get(node_id, "")

        # ── Path A: concept/pillar ←PEER← paper ─CONTAINER→ section ─CAUSE→ experiment
        papers: set[str] = set()
        if nt in ("concept", "pillar") or "pillar" in node_id:
            papers.update(p for p in incoming_peer.get(node_id, [])
                          if node_type.get(p) in ("paper", "prereg_document"))

        # ── Path B: paper ─CONTAINER→ section ─CAUSE→ experiment  (paper node itself)
        if nt == "paper" or node_id.startswith(("P1", "P2", "P3", "P4", "P5",
                                                  "P6", "P7", "P8", "P9", "P-OMEGA")):
            papers.add(node_id)

        # ── Path C: paper_section directly
        sections: set[str] = set()
        if nt == "paper_section":
            sections.add(node_id)

        # Expand papers → sections via CONTAINER
        for p in papers:
            sections.update(s for s in forward_container.get(p, [])
                            if node_type.get(s) in ("paper_section", "experiment", ""))

        # From sections: reach experiments via CAUSE and EFFECT
        for sec in sections:
            for exp in forward_cause_effect.get(sec, []):
                if node_type.get(exp) == "experiment":
                    exps.add(exp)
            for exp in forward_effect.get(sec, []):
                if node_type.get(exp) == "experiment":
                    exps.add(exp)

        # ── Path D: cross_cut / memory nodes — use incoming PEER_COHERENT too
        if nt in ("cross_cut", "memory_entry"):
            for p in incoming_peer.get(node_id, []):
                secs = set(forward_container.get(p, []))
                for sec in secs:
                    for exp in forward_cause_effect.get(sec, []):
                        if node_type.get(exp) == "experiment":
                            exps.add(exp)

        return exps

    out: dict[str, dict] = {}
    TARGET_TYPES = {"concept", "paper", "paper_section", "pillar",
                    "cross_cut", "prereg_document"}
    for n in graph_dict["nodes"]:
        nt = (n.get("metadata") or {}).get("node_type", "")
        if n.get("layer") != "structural":
            continue
        if nt not in TARGET_TYPES and not any(
            n["id"].startswith(pfx) for pfx in ("P1", "P2", "P3", "P4", "P5",
                                                  "P6", "P7", "P8", "P9", "pillar",
                                                  "P-OMEGA", "CC-", "prereg_")
        ):
            continue
        exps = experiments_for_node(n["id"])
        if exps:
            out[n["id"]] = {
                "n_experiments":  len(exps),
                "experiment_ids": sorted(exps)[:20],
            }
    return out


def compute_temporal_decay(graph_dict: dict,
                           grounding: dict[str, dict],
                           decay_halflife_weeks: float = 6.0) -> dict[str, dict]:
    """Per-node temporal decay score based on the most recent experiment in the
    inherited grounding set.

    The operand is NOT node.active_since (which reflects node creation, not
    evidence freshness) but max(active_since) over the experiment_ids in the
    grounding set.  A concept with experiments from last week scores high;
    one whose most recent supporting experiment is from 6 months ago decays.

    Returns:
        dict: node_id → {
            "most_recent_experiment_date": str | None,   # ISO date of freshest experiment
            "weeks_since_last_evidence":   float | None,
            "temporal_decay_factor":       float,        # 0..1, exp(-weeks / halflife)
            "ve_score_decayed":            float,        # ve_score × decay_factor
        }

    decay_halflife_weeks: weeks at which decay factor = 0.5  (default: 6 weeks,
        matching the soul's 6-week editorial audit cadence).
    """
    import math
    from datetime import date, datetime

    def parse_date(s: str | None) -> date | None:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except ValueError:
                continue
        return None

    node_index = {n["id"]: n for n in graph_dict["nodes"]}
    today = date.today()
    out: dict[str, dict] = {}

    for nid, g in grounding.items():
        n = node_index.get(nid)
        ve = (n.get("ve_score_harmonic") or n.get("ve_score") or 0) if n else 0

        # Collect dates from experiment_ids
        exp_dates: list[date] = []
        for eid in g.get("experiment_ids", []):
            en = node_index.get(eid)
            if en:
                d = parse_date(en.get("active_since"))
                if d:
                    exp_dates.append(d)

        if exp_dates:
            most_recent = max(exp_dates)
            weeks_ago = (today - most_recent).days / 7.0
        else:
            most_recent = None
            # No experiments → use node's own active_since as fallback
            d = parse_date(n.get("active_since") if n else None)
            weeks_ago = (today - d).days / 7.0 if d else None

        if weeks_ago is not None:
            # Exponential decay: f(t) = 2^(-t/halflife) = exp(-t * ln2 / halflife)
            decay = math.exp(-weeks_ago * math.log(2) / decay_halflife_weeks)
            decay = max(0.0, min(1.0, decay))
        else:
            decay = 1.0   # unknown age → no penalty

        out[nid] = {
            "most_recent_experiment_date": most_recent.isoformat() if most_recent else None,
            "weeks_since_last_evidence":   round(weeks_ago, 1) if weeks_ago is not None else None,
            "temporal_decay_factor":       round(decay, 4),
            "ve_score_decayed":            round(ve * decay, 4),
        }
    return out


def enrich_viz(graph_dict: dict) -> dict:
    """Top-level entry: returns a dict to merge into the snapshot under
    top-level keys for the carousel to consume.
    """
    # Inherited grounding must be computed before temporal decay (it's the input)
    grounding = compute_inherited_grounding(graph_dict)
    temporal  = compute_temporal_decay(graph_dict, grounding)

    return {
        "viz_components": compute_connected_components(graph_dict),
        "viz_citation_edges": compute_citation_edges(graph_dict),
        "viz_dominant_polyhedron": compute_dominant_polyhedron(graph_dict),
        # Polyhedron rule list embedded so the carousel JS reads it from the
        # loaded snapshot (single source of truth).
        "viz_polyhedron_rules": _POLYHEDRON_RULES,
        # Per-node philosophical-search caches for click-time overlays
        "viz_porphyrian_relations": compute_porphyrian_relations(graph_dict),
        # Wittgenstein family = doc co-occurrence (concepts) MERGED WITH
        # neighborhood Jaccard (experiments / papers / paper_sections)
        "viz_wittgenstein_neighbors": {
            **compute_wittgenstein_neighbors(graph_dict, top_k=5),
            **compute_wittgenstein_neighbors_by_neighborhood(graph_dict, top_k=5),
        },
        # Evidential health metrics (2026-04-30)
        "viz_inherited_grounding": grounding,
        "viz_temporal_decay":      temporal,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='viz_precompute',
    scale=1,
    aristotelian_cause='final',
    container=['core'],
    substrate=['core.schema'],
    effect=['viz_components, viz_citation_edges, viz_dominant_polyhedron'],
    description='Pre-compute viz-layer derivations into snapshot JSON',
)
