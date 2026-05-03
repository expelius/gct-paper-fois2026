"""enrich_with_maxims.py — add maxim violations + inference proposals to a snapshot.

Reads an existing `tensegrity_graph_*.json`, reconstructs the in-memory
TensegrityGraph, applies the maxim layer (`validate_graph`, `infer_missing_edges`),
and writes back an enriched JSON with two new top-level keys:

    "maxims_violations": [ {edge_id, slot, maxim, violation, source_node, target_node}, ... ]
    "maxims_proposals":  [ {from_edge_id, from_slot, maxim, proposed:{...}, focus_node}, ... ]
    "maxims_summary":    { n_violations, n_proposals, by_slot, by_proposal_type, by_node }

Each entry carries a `focus_node` field so consumers (carousel inspector,
query_graph.py) can index quickly.

Usage:
    python enrich_with_maxims.py [path-to-snapshot.json [...]]
    python enrich_with_maxims.py            # enriches all phase{1,2}*.json in cwd

Designed to be re-runnable: overwrites the maxims_* keys in-place; never
modifies nodes/edges. Idempotent.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.builder import TensegrityGraph
from core.maxims import infer_missing_edges, validate_graph_with_coverage
from core.schema import Confidence, Edge, Layer, Node, Slot
from core.viz_precompute import enrich_viz


def reconstruct(graph_dict: dict) -> TensegrityGraph:
    g = TensegrityGraph()
    for n in graph_dict["nodes"]:
        try:
            g.add_node(Node(
                id=n["id"], label=n["label"], scale=n["scale"],
                layer=Layer(n["layer"]), structural_ref=n.get("structural_ref"),
                metadata=n.get("metadata", {}),
            ))
        except Exception:
            pass
    for e in graph_dict["edges"]:
        try:
            g.add_edge(Edge(
                source=e["source"], target=e["target"],
                slot=Slot[e["slot"]], confidence=Confidence[e["confidence"]],
                scale_from=e.get("scale_from", 1), scale_to=e.get("scale_to", 1),
                evidence=e.get("evidence", ""),
            ))
        except Exception:
            pass
    return g


def _apply_manual_edges(data: dict) -> int:
    """Inject edges from manual_edges.json that the extractor missed.

    The extractor's regex requires 'P1.§section' (with dot); many LOG entries
    use 'P1 §future' (no dot) for not-yet-existing sections.  This function
    patches the snapshot with the correct CAUSE edges grounded in the LOG,
    keyed by source+target to remain idempotent on repeated runs.

    Returns the number of edges actually added (0 on idempotent re-runs).
    """
    manual_path = Path(__file__).parent / "manual_edges.json"
    if not manual_path.exists():
        return 0

    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    entries = manual.get("edges", [])
    if not entries:
        return 0

    node_ids = {n["id"] for n in data.get("nodes", [])}
    existing = {(e["source"], e["target"], e.get("slot")) for e in data.get("edges", [])}

    added = 0
    for entry in entries:
        src, tgt, slot = entry["source"], entry["target"], entry.get("slot", "CAUSE")
        if src not in node_ids or tgt not in node_ids:
            continue          # skip if either endpoint missing from this snapshot
        key = (src, tgt, slot)
        if key in existing:
            continue          # already present — idempotent
        data.setdefault("edges", []).append({
            "source": src, "target": tgt,
            "slot": slot,
            "confidence": "MEDIUM",
            "scale_from": 1, "scale_to": 2,
            "evidence": entry.get("_log", "manual_edges.json patch"),
        })
        existing.add(key)
        added += 1

    return added


def enrich(path: Path) -> dict:
    """Enrich the snapshot at `path` in-place; return summary stats."""
    data = json.loads(path.read_text(encoding="utf-8"))

    # Patch missing experiment→paper edges before all downstream computation
    n_patched = _apply_manual_edges(data)
    if n_patched:
        print(f"    [manual_edges] +{n_patched} edges injected")

    g = reconstruct(data)

    coverage = validate_graph_with_coverage(g)
    raw_violations = coverage["violations"]
    raw_proposals = infer_missing_edges(g)

    # Resolve per-edge to per-node so consumers can index quickly.
    edges_by_id = dict(zip(
        [f"e{i}" for i in range(len(data["edges"]))],
        data["edges"],
    ))
    # The reconstructed graph reuses our edge ID convention (e0, e1, ...).
    # Map each violation back to source/target.
    violations_out = []
    for v in raw_violations:
        eid = v["edge_id"]
        e = edges_by_id.get(eid, {})
        violations_out.append({
            "edge_id": eid,
            "slot": v["slot"],
            "maxim": v["maxim"],
            "severity": v.get("severity", "VIOLATION"),
            "violation": v["violation"],
            "source_node": e.get("source"),
            "target_node": e.get("target"),
            # focus_node = the node the violation is "about" — by convention
            # for asymmetry/scale/anteriority, it's the source (the one that
            # declared the malformed edge).
            "focus_node": e.get("source"),
        })

    proposals_out = []
    for p in raw_proposals:
        eid = p["from_edge_id"]
        e = edges_by_id.get(eid, {})
        prop = p["proposed"]
        focus = (
            prop.get("node")
            or prop.get("from_node")
            or prop.get("to_node")
            or e.get("source")
        )
        proposals_out.append({
            "from_edge_id": eid,
            "from_slot": p["from_slot"],
            "maxim": p["maxim"],
            "type": prop.get("type"),
            "rationale": prop.get("rationale"),
            "focus_node": focus,
        })

    # Summary aggregates
    violations_by_slot = Counter(v["slot"] for v in violations_out)
    violations_by_severity = Counter(v["severity"] for v in violations_out)
    proposals_by_type = Counter(p["type"] for p in proposals_out)
    by_node = defaultdict(lambda: {
        "violations": 0, "proposals": 0,
        "strict": 0, "warn": 0,        # severity breakdown per node
    })
    for v in violations_out:
        if v["focus_node"]:
            by_node[v["focus_node"]]["violations"] += 1
            sev = v.get("severity", "VIOLATION")
            if sev == "STRICT":
                by_node[v["focus_node"]]["strict"] += 1
            elif sev == "WARN":
                by_node[v["focus_node"]]["warn"] += 1
    for p in proposals_out:
        if p["focus_node"]:
            by_node[p["focus_node"]]["proposals"] += 1

    summary = {
        "n_violations": len(violations_out),
        "n_proposals": len(proposals_out),
        "by_slot": dict(violations_by_slot),
        "by_severity": dict(violations_by_severity),
        "by_proposal_type": dict(proposals_by_type),
        "n_nodes_with_findings": len(by_node),
        # Coverage: distinguishes "checked & passed" from "couldn't check"
        "coverage": {
            "n_checked": coverage["n_checked"],
            "n_unable_to_validate": coverage["n_unable"],
            "n_no_rule_for_slot": coverage["n_no_rule"],
        },
    }

    data["maxims_violations"] = violations_out
    data["maxims_proposals"] = proposals_out
    data["maxims_summary"] = summary
    data["maxims_by_node"] = dict(by_node)

    # Pre-compute viz-layer derivations (components / citation web / dominant
    # polyhedron) so the carousel reads them rather than recomputing in JS,
    # and so the CLI and viz agree on the same numbers.
    data.update(enrich_viz(data))

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(p) for p in argv]
    else:
        here = Path(__file__).parent
        targets = sorted(here.glob("tensegrity_graph_*.json"))

    if not targets:
        print("no snapshot files found", file=sys.stderr)
        return 1

    for t in targets:
        if not t.exists():
            print(f"  [skip] {t} not found")
            continue
        size_before = t.stat().st_size
        s = enrich(t)
        size_after = t.stat().st_size
        print(f"  enriched {t.name}")
        print(f"    {s['n_violations']} violations / {s['n_proposals']} proposals "
              f"/ {s['n_nodes_with_findings']} nodes touched")
        print(f"    by_slot: {s['by_slot']}")
        print(f"    by_severity: {s.get('by_severity', {})}")
        print(f"    by_proposal_type: {s['by_proposal_type']}")
        cov = s.get('coverage', {})
        print(f"    coverage: checked={cov.get('n_checked')}, "
              f"unable={cov.get('n_unable_to_validate')}, "
              f"no_rule={cov.get('n_no_rule_for_slot')}")
        print(f"    size: {size_before:>9} → {size_after:>9} bytes "
              f"(+{(size_after - size_before) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
