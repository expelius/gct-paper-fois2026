"""compute_paper_numbers.py — single-source-of-truth for every numerical
claim in §5 of the Tensegrity Knowledge Graph paper.

Run from the publication/ directory:

    python compute_paper_numbers.py                       # default: phase-9 (paper §5)
    python compute_paper_numbers.py --snapshot phase14    # extensibility demo (§7.1)

Default reads the canonical phase-9 snapshot
(`../tensegrity_graph_phase9_complete.json`) — the frozen reference snapshot
that all numerical claims in §5 of `PAPER_DRAFT.md` / `gct_paper_main.tex`
are anchored to. Reviewers should run this verbatim to verify the paper's
§5 empirical claims.

The optional `--snapshot phase14` flag reads
`../tensegrity_graph_phase14_complete.json`, which differs from phase-9
only in adding the CODE-edge wirer extractor (`code_implements`) that
closes Slot.CODE by linking each maxim node to the code holon(s) that
formally implement it. Phase-14 is the empirical artefact backing §7.1's
schema-extensibility argument.

Important: this script reads the pre-computed `aristotelian_completeness` and
`ve_score_harmonic` fields stored on each node by `enrich_with_maxims.py`,
rather than recomputing from scratch. The pre-computed values ARE the source
of truth; re-derivation from the raw graph would inevitably drift due to
implementation details of the canonical enrichment pipeline.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

sys.stdout.reconfigure(encoding="utf-8")

SNAPSHOTS = {
    "phase9":     Path(__file__).resolve().parent.parent / "tensegrity_graph_phase9_complete.json",
    "phase14":    Path(__file__).resolve().parent.parent / "tensegrity_graph_phase14_complete.json",
    # Second-corpus empirical demonstration of domain-independence (§6.4).
    # Built by `publication/biomedical_instantiation.py`.
    "biomedical": Path(__file__).resolve().parent.parent / "tensegrity_graph_biomedical.json",
}
DEFAULT_SNAPSHOT = "phase9"

CANON_SLOTS = [
    ("SPECIFICATION",       "STRUT"),
    ("PEER_COHERENT",       "STRUT"),
    ("EFFECT",              "CABLE"),
    ("CONTAINER",           "STRUT"),
    ("CAUSE",               "STRUT"),
    ("SUBSTRATE",           "CABLE"),
    ("INSTANTIATION",       "CABLE"),
    ("PREDECESSOR",         "STRUT"),
    ("CODE",                "STRUT"),
    ("SUCCESSOR",           "CABLE"),
    ("PEER_CONTRADICTORY",  "CABLE"),
    ("THERMO",              "CABLE"),
]


def load_snapshot(path: Path):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode("utf-8")), sha


def compute_components(nodes, edges):
    parent = {n["id"]: n["id"] for n in nodes}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in parent and t in parent:
            union(s, t)
    sizes = sorted(Counter(find(n["id"]) for n in nodes).values(), reverse=True)
    singletons = sum(1 for s in sizes if s == 1)
    return len(sizes), sizes[0] if sizes else 0, singletons


def infer_type(node):
    """Infer node type from id prefix.

    Covers three corpora:
    - phase9 / phase14 (neural-architecture): D-*, *_section_*, P*, concept_*, etc.
    - biomedical (§6.4 second-corpus demo): BIO-EXP-*, PATHWAY-*, DISEASE-*, CL-*, NCT*, PAPER-*
    """
    nid = node.get("id", "")
    prov_raw = node.get("provenance", "") or ""
    prov = prov_raw if isinstance(prov_raw, str) else (prov_raw.get("extractor", "") if isinstance(prov_raw, dict) else "")
    prov = (prov or "").lower()
    # Biomedical corpus (§6.4) — patterns match actual IDs in tensegrity_graph_biomedical.json
    if nid.startswith("BIO-EXP-"):            return "experiment"
    if nid.startswith("PATHWAY-") or nid.startswith("DISEASE-"): return "concept"
    if nid.startswith("CL-"):                 return "concept"   # cell line as substrate concept
    if nid.startswith("PREREG-NCT"):          return "prereg_prediction_referenced"
    if "_section_" in nid and nid.startswith("PAPER-"): return "paper_section"
    if nid.startswith("PAPER-"):              return "paper"
    if nid.startswith("CODE-"):               return "code_holon"
    if nid.startswith("FREE-ENERGY-"):        return "other"
    # Neural-architecture corpus (phase9 / phase14)
    if nid.startswith("D-"):                  return "experiment"
    if "_section_" in nid:                    return "paper_section"
    if nid.startswith("P-") or nid in {"P1","P2","P3","P4","P5","P6","P7","P8","P9","P-OMEGA","P4-LIQUID-TENSEGRITY"}:
        return "paper"
    if "concepto_" in nid or nid.startswith("HNC") or nid.startswith("LT-") or nid.startswith("NESS-"):
        return "concept"
    if "code_holon" in prov or nid.startswith("CH-"):
        return "code_holon"
    if "cross_cut" in prov or nid.startswith("CC-"):
        return "cross_cut"
    if nid.startswith("PREREG-") or nid.startswith("OSF-"):
        return "prereg_prediction_referenced"
    return "other"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", choices=sorted(SNAPSHOTS), default=DEFAULT_SNAPSHOT,
                        help=f"Which snapshot to verify (default: {DEFAULT_SNAPSHOT}).")
    args = parser.parse_args()

    snapshot_path = SNAPSHOTS[args.snapshot]
    if not snapshot_path.exists():
        print(f"ERROR: snapshot not found at {snapshot_path}", file=sys.stderr)
        sys.exit(2)

    snap, sha = load_snapshot(snapshot_path)
    nodes, edges = snap["nodes"], snap["edges"]

    section_label = {
        "phase9":     "§5 Empirical Evaluation",
        "phase14":    "§7.1 Extensibility demo (phase-14)",
        "biomedical": "§6.4 Second-Corpus Evaluation (biomedical)",
    }.get(args.snapshot, args.snapshot)
    print(f"# {section_label} — Verified Numbers")
    print()
    print(f"**Snapshot:** `{snapshot_path.name}`")
    print(f"**SHA-256:** `{sha[:16]}...{sha[-16:]}`")
    print()

    # -------------------------------------------------------------------------
    print("## Graph Statistics")
    print()
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Total nodes | {len(nodes):,} |")
    print(f"| Total edges | {len(edges):,} |")
    layers = Counter(n.get("layer", "?") for n in nodes)
    structural = [n for n in nodes if n.get("layer") == "structural"]
    print(f"| Structural nodes | {len(structural):,} |")
    print(f"| Functional nodes | {layers.get('functional', 0):,} |")
    print(f"| Thermodynamic nodes | {layers.get('thermodynamic', 0):,} |")
    n_components, largest, singletons = compute_components(nodes, edges)
    print(f"| Connected components (β₀) | {n_components} |")
    print(f"| Largest component | {largest} ({100 * largest / len(nodes):.1f}%) |")
    print(f"| Singleton components | {singletons} |")
    print()

    # -------------------------------------------------------------------------
    print("## §5.1 Aristotelian Completeness Distribution")
    print()
    print("(Read from pre-computed `aristotelian_completeness` field on each structural node.)")
    print()

    def ac_score(node):
        ac = node.get("aristotelian_completeness")
        if isinstance(ac, dict):
            return ac.get("completeness", 0.0)
        return float(ac) if ac is not None else 0.0

    ac_values = [ac_score(n) for n in structural]
    bucket_count = Counter()
    for ac in ac_values:
        # bucket by 0.25 increments
        b = round(ac * 4) / 4
        bucket_count[b] += 1

    n_struct = len(structural)
    print("| Causes documented | Count | Percentage |")
    print("|---|---|---|")
    for b in [0.00, 0.25, 0.50, 0.75, 1.00]:
        c = bucket_count.get(b, 0)
        causes = int(b * 4)
        print(f"| {causes}/4 (AC = {b:.2f}) | {c} | {100 * c / n_struct:.1f}% |")
    print(f"| **Mean AC** | **{mean(ac_values):.3f}** | --- |")
    print()

    # AC by inferred node type
    print("AC by node type:")
    print()
    type_groups = {}
    for n in structural:
        t = infer_type(n)
        type_groups.setdefault(t, []).append(ac_score(n))
    print("| Node type | n | Mean AC |")
    print("|---|---|---|")
    for t, vals in sorted(type_groups.items(), key=lambda kv: -mean(kv[1]) if kv[1] else 0):
        print(f"| {t} | {len(vals)} | {mean(vals):.3f} |")
    print()

    # -------------------------------------------------------------------------
    print("## §5.2 Boethian Maxim Engine")
    print()
    proposals  = snap.get("maxims_proposals", [])
    violations = snap.get("maxims_violations", [])
    by_type = Counter(p.get("type", "?") for p in proposals)
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Total proposals generated | {len(proposals)} |")
    print(f"| Violations detected | {len(violations)} |")
    print(f"| Dominant proposal type | {by_type.most_common(1)[0][0]} ({100 * by_type.most_common(1)[0][1] / len(proposals):.0f}%) |")
    print()

    # -------------------------------------------------------------------------
    print("## §5.3 Slot Distribution")
    print()
    slot_counts = Counter(e.get("slot", "?") for e in edges)
    print("| Slot | Type | Count | % of edges |")
    print("|---|---|---|---|")
    for slot, mech in CANON_SLOTS:
        c = slot_counts.get(slot, 0)
        pct = 100 * c / len(edges) if edges else 0
        print(f"| {slot} | {mech} | {c} | {pct:.1f}% |")
    occupied = sum(1 for s, _ in CANON_SLOTS if slot_counts.get(s, 0) > 0)
    print()
    print(f"**{occupied}/12 slots occupied** ({len(CANON_SLOTS) - occupied} unoccupied: {[s for s,_ in CANON_SLOTS if slot_counts.get(s,0)==0]})")
    print()

    # -------------------------------------------------------------------------
    print("## §5.4 VE Score Distribution")
    print()
    ve_values = [n.get("ve_score_harmonic", 0.0) for n in structural]
    god_threshold = 0.5
    god_nodes = [(n["id"], n.get("ve_score_harmonic", 0.0))
                 for n in structural if n.get("ve_score_harmonic", 0.0) >= god_threshold]
    god_nodes.sort(key=lambda kv: -kv[1])
    top6 = sorted(structural, key=lambda n: -n.get("ve_score_harmonic", 0.0))[:6]

    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Structural nodes | {len(structural)} |")
    print(f"| God nodes (VE ≥ 0.5) | {len(god_nodes)} ({100 * len(god_nodes) / len(structural):.1f}%) |")
    print(f"| Mean VE | {mean(ve_values):.3f} |")
    if top6:
        print(f"| Max VE node | {top6[0]['id']} ({top6[0].get('ve_score_harmonic', 0.0):.3f}) |")
    print()
    print("Top 6 god nodes:")
    for n in top6:
        print(f"  - {n['id']:24} VE_h = {n.get('ve_score_harmonic', 0.0):.3f}")
    print()

    # -------------------------------------------------------------------------
    print("## §5.5 Wittgenstein Family Resemblance Coverage")
    print()
    print("(Reads the canonical pre-computed `viz_wittgenstein_neighbors` field;")
    print(" partitions by node-id classifier; reports both family-layer and full-snapshot denominators.)")
    print()

    fam = snap.get("viz_wittgenstein_neighbors", {}) or {}

    def classify_for_fam(nid):
        # Biomedical corpus (§6.4)
        if nid.startswith("BIO-EXP-"):                      return "experiment"
        if nid.startswith("PATHWAY-") or nid.startswith("DISEASE-") or nid.startswith("CL-"):
                                                            return "concept"
        if "_section_" in nid and nid.startswith("PAPER-"): return "paper_section"
        if nid.startswith("PAPER-"):                        return "paper"
        # Neural-architecture corpus (phase9 / phase14)
        if nid.startswith("D-"):                            return "experiment"
        if "_section_" in nid:                              return "paper_section"
        if nid.startswith("concept_"):                      return "concept"
        if (nid.startswith("P") and nid not in {"PREREG"}
                and "_section_" not in nid
                and not nid.startswith("concept_")):        return "paper"
        return "other"

    in_layer  = Counter()
    with_fam  = Counter()
    fr_scores = []

    for nid, nbrs in fam.items():
        t = classify_for_fam(nid)
        in_layer[t] += 1
        if nbrs:
            with_fam[t] += 1
            for nb in nbrs:
                if isinstance(nb, dict) and "score" in nb:
                    fr_scores.append(nb["score"])
                elif isinstance(nb, (list, tuple)) and len(nb) >= 2:
                    try:
                        fr_scores.append(float(nb[1]))
                    except (TypeError, ValueError):
                        pass

    snapshot_totals = Counter()
    for n in nodes:
        t = classify_for_fam(n["id"])
        snapshot_totals[t] += 1

    if fr_scores:
        print(f"FR score statistics: min = {min(fr_scores):.3f}, mean = {mean(fr_scores):.3f}, max = {max(fr_scores):.3f}")
        print()
    print("| Node type | With family | In family layer | Snapshot total | Family-layer coverage | Snapshot coverage |")
    print("|---|---|---|---|---|---|")
    for t in ("experiment", "concept", "paper", "paper_section"):
        wf   = with_fam.get(t, 0)
        il   = in_layer.get(t, 0)
        tot  = snapshot_totals.get(t, 0)
        flc  = f"{100 * wf / il:.0f}%" if il else "—"
        snc  = f"{100 * wf / tot:.0f}%" if tot else "—"
        print(f"| {t} | {wf} | {il} | {tot} | {flc} | {snc} |")
    print()
    print("Note: Family-layer coverage is the proportion of family-eligible nodes that have at least one similar counterpart;")
    print("snapshot coverage is the same numerator over the full type partition (some nodes are excluded from the family")
    print("layer by `viz_precompute.py` for insufficient connectivity, e.g. recently-registered ghost experiments).")
    print()

    print("---")
    print("End of report. Compare each row above against the corresponding table in §5 of PAPER_DRAFT.md / gct_paper_main.tex.")


if __name__ == "__main__":
    main()
