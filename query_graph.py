"""query_graph.py — read-only query interface against a saved graph snapshot.

Usage:

    python query_graph.py <command> [args...] [--graph PATH]

Commands:
    summary                          — print top-level stats
    god-nodes [--top K]              — top-K nodes by VE_harmonic
    orphans [--threshold T]          — VE_score < T (under-developed)
    overloaded [--threshold T]       — saturation > T (>12 edges; split candidates)
    hot-frontiers [--ve V] [--ps P]  — high VE AND high prestress (research tension)
    asymmetric [--threshold T]       — pure-code or pure-thermo holons
    incomplete                       — Aristotelian completeness < 1.0
    by-scale <scale>                 — list nodes at a given scale (0..4)
    by-layer <layer>                 — list nodes in a layer (structural/functional/thermodynamic)
    by-type <node_type>              — list nodes by metadata.node_type
    find <substring>                 — fuzzy id/label match
    show <node_id>                   — full dump of a single node + its edges
    neighbors <node_id> [--hops N]   — N-hop neighborhood (default 1)
    concept <name>                   — find concept node + its functional uses
    experiment <D-XXX>               — show D-XXX node, its results JSONs, papers it feeds
    paper <P-id>                     — show paper, its sections, the D-IDs that feed it
    inversions                       — D-IDs whose status conflicts across paper drafts
    societies                        — concept clusters (Wittgenstein family resemblance)
    delta <other_graph.json>         — diff against another snapshot (added/removed/changed)
    health                           — overall health report (β₀, β₁, prestress, completeness)
    maxims                           — Boethian/Aristotelian maxim layer summary (violations + proposals)
    violations [--slot S] [--node N] — detailed maxim violations, optionally filtered by slot or focus node
    infer [--type T] [--node N]      — inference proposals (missing edges implied by maxims)
    maxim-instances <slot>           — every edge in the graph governed by a given maxim (i.e., where edge.slot == SLOT)
    family <concept_id> [--measure cosine|jaccard|kl] — Wittgensteinian family-resemblance search (no embeddings; uses concept-use overlap)
    family-clusters [--measure ...] [--threshold 0.4]  — concepts grouped by use-pattern overlap
    porphyrian <node_id>             — taxonomic profile: genera + species + siblings (genus tree)
    siblings <node_id>               — siblings under the same genus
    prehension <key=value> ...       — Whiteheadian feature search (e.g. scale=2 axis_tag=geometry)
    boecian <node_id> --slot SLOT    — search-as-maxim-application: hypothetical edges that pass the validator

Examples:

    python query_graph.py summary
    python query_graph.py god-nodes --top 20
    python query_graph.py concept HNC
    python query_graph.py experiment D-101
    python query_graph.py neighbors P-OMEGA --hops 2
    python query_graph.py delta tensegrity_graph_phase1_complete.json

Default graph path: tensegrity_graph_phase2_complete.json (in the current dir
or in knowledge-graph/).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Force UTF-8 stdout on Windows so Greek letters / unicode in node labels print
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

DEFAULT_GRAPH_NAMES = [
    "tensegrity_graph_phase12_complete.json",
    "tensegrity_graph_phase11_complete.json",
    "tensegrity_graph_phase10_complete.json",
    "tensegrity_graph_phase9_complete.json",
    "tensegrity_graph_phase8_complete.json",
    "tensegrity_graph_phase7_complete.json",
    "tensegrity_graph_phase6_complete.json",
    "tensegrity_graph_phase5_complete.json",
    "tensegrity_graph_phase4_complete.json",
    "tensegrity_graph_phase3_complete.json",
    "tensegrity_graph_phase2_complete.json",
    "tensegrity_graph_phase1_complete.json",
]


# ----------------------- Loading ------------------------------------------------


def find_graph_path(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise FileNotFoundError(f"--graph path not found: {explicit}")
    here = Path.cwd()
    candidates = [here] + list(here.parents)
    for base in candidates:
        kg = base / "knowledge-graph"
        if kg.is_dir():
            for name in DEFAULT_GRAPH_NAMES:
                p = kg / name
                if p.exists():
                    return p
        for name in DEFAULT_GRAPH_NAMES:
            p = base / name
            if p.exists():
                return p
    raise FileNotFoundError(
        "no graph snapshot found. Pass --graph PATH or run from "
        "the knowledge-graph/ folder."
    )


def load_graph(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index_nodes(graph: dict) -> dict[str, dict]:
    return {n["id"]: n for n in graph["nodes"]}


def index_edges_by_source(graph: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for e in graph["edges"]:
        out[e["source"]].append(e)
    return out


def index_edges_by_target(graph: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for e in graph["edges"]:
        out[e["target"]].append(e)
    return out


# ----------------------- Formatting --------------------------------------------


def fmt_node_short(n: dict) -> str:
    layer = n.get("layer", "?")[:5]
    scale = n.get("scale", "?")
    ve = n.get("ve_score_harmonic", n.get("ve_score", 0))
    label = n.get("label", "")[:78]
    return f"  [{n['id']:<28}] s{scale} {layer:<5} VE_h={ve:.2f}  {label}"


def fmt_edge(e: dict) -> str:
    return (
        f"    {e['source']:<28} --[{e['slot']:<20}]--> {e['target']:<28} "
        f"({e['mechanical_type']}, {e['confidence']})"
    )


# ----------------------- Commands ----------------------------------------------


def cmd_summary(g: dict, args) -> None:
    s = g["stats"]
    print(f"Schema version: {g.get('schema_version', '?')}")
    print(f"Nodes: {s['n_nodes']:>5}    Edges: {s['n_edges']:>5}")
    print(f"Struts: {s['n_struts']:>4}   Cables: {s['n_cables']:>3}   "
          f"ratio: {s['strut_cable_ratio']}")
    print(f"VE_h avg: {s['avg_ve_score_harmonic']}   max: {s['max_ve_score_harmonic']}")
    print(f"Prestress: total={s['total_prestress']}   avg={s['avg_prestress']}")
    print(f"Saturation: avg={s['avg_saturation']}   max={s['max_saturation']}")
    print(f"Topology: β₀={s['topology_beta_0_components']} components, "
          f"β₁={s['topology_beta_1_cycles']} cycles")
    print(f"\nScale distribution: {s['scale_distribution']}")
    print(f"Layer distribution: {s['layer_distribution']}")
    print(f"\nSlot usage (top 8):")
    for slot, count in sorted(s["slot_usage"].items(), key=lambda x: -x[1])[:8]:
        print(f"  {slot:<22} {count:>5}")


def cmd_god_nodes(g: dict, args) -> None:
    nodes = g["nodes"]
    ranked = sorted(
        nodes,
        key=lambda n: -(n.get("ve_score_harmonic", n.get("ve_score", 0))),
    )[: args.top]
    print(f"Top {args.top} nodes by VE_harmonic:")
    for n in ranked:
        print(fmt_node_short(n))


def cmd_orphans(g: dict, args) -> None:
    th = args.threshold
    nodes = [n for n in g["nodes"] if n.get("ve_score", 0) < th]
    print(f"{len(nodes)} nodes with VE < {th}:")
    for n in sorted(nodes, key=lambda n: n.get("ve_score", 0))[:50]:
        print(fmt_node_short(n))


def cmd_overloaded(g: dict, args) -> None:
    th = args.threshold
    nodes = [n for n in g["nodes"] if n.get("saturation", 0) > th]
    print(f"{len(nodes)} nodes with saturation > {th}:")
    for n in sorted(nodes, key=lambda n: -n.get("saturation", 0))[:30]:
        print(f"  [{n['id']:<28}] sat={n['saturation']:.2f}  {n.get('label', '')[:70]}")


def cmd_hot_frontiers(g: dict, args) -> None:
    ve_min = args.ve
    ps_min = args.ps
    out = []
    for n in g["nodes"]:
        ve = n.get("ve_score", 0)
        ps = n.get("prestress_local", 0)
        if ve >= ve_min and ps >= ps_min:
            out.append((n, ve * (ps + 1)))
    print(f"{len(out)} hot frontiers (VE>={ve_min}, prestress>={ps_min}):")
    for n, score in sorted(out, key=lambda x: -x[1])[:25]:
        print(f"  [{n['id']:<28}] VE={n['ve_score']:.2f} ps={n['prestress_local']} "
              f"score={score:.2f}  {n.get('label', '')[:60]}")


def cmd_asymmetric(g: dict, args) -> None:
    th = args.threshold
    nodes = [n for n in g["nodes"] if n.get("asymmetry", 0) > th]
    print(f"{len(nodes)} asymmetric nodes (|asym| > {th}):")
    for n in sorted(nodes, key=lambda n: -abs(n.get("asymmetry", 0)))[:30]:
        sign = "code-heavy" if n["asymmetry"] > 0 else "thermo-heavy"
        print(f"  [{n['id']:<28}] asym={n['asymmetry']:+.2f} ({sign})  "
              f"{n.get('label', '')[:60]}")


def cmd_incomplete(g: dict, args) -> None:
    incomplete = []
    for n in g["nodes"]:
        ac = n.get("aristotelian_completeness", {})
        comp = ac.get("completeness", 1.0)
        if comp < 1.0:
            incomplete.append((n, comp, ac.get("missing_causes", [])))
    print(f"{len(incomplete)} nodes with Aristotelian completeness < 1.0")
    print("(showing top 30 by missing-cause count)")
    for n, c, missing in sorted(incomplete, key=lambda x: (-len(x[2]), x[1]))[:30]:
        print(f"  [{n['id']:<28}] comp={c:.2f} missing={missing}  "
              f"{n.get('label', '')[:50]}")


def cmd_by_scale(g: dict, args) -> None:
    s = int(args.scale)
    nodes = [n for n in g["nodes"] if n.get("scale") == s]
    print(f"{len(nodes)} nodes at scale s{s}:")
    for n in sorted(nodes, key=lambda n: -n.get("ve_score_harmonic", 0))[:50]:
        print(fmt_node_short(n))


def cmd_by_layer(g: dict, args) -> None:
    layer = args.layer
    nodes = [n for n in g["nodes"] if n.get("layer") == layer]
    print(f"{len(nodes)} nodes in layer '{layer}':")
    for n in sorted(nodes, key=lambda n: -n.get("ve_score_harmonic", 0))[:50]:
        print(fmt_node_short(n))


def cmd_by_type(g: dict, args) -> None:
    nt = args.node_type
    nodes = [n for n in g["nodes"] if n.get("metadata", {}).get("node_type") == nt]
    print(f"{len(nodes)} nodes with node_type='{nt}':")
    for n in sorted(nodes, key=lambda n: -n.get("ve_score_harmonic", 0))[:50]:
        print(fmt_node_short(n))


def cmd_find(g: dict, args) -> None:
    q = args.substring.lower()
    nodes = [
        n for n in g["nodes"]
        if q in n["id"].lower() or q in n.get("label", "").lower()
    ]
    print(f"{len(nodes)} matches for '{q}':")
    for n in nodes[:50]:
        print(fmt_node_short(n))


def cmd_show(g: dict, args) -> None:
    nodes = index_nodes(g)
    by_src = index_edges_by_source(g)
    by_tgt = index_edges_by_target(g)
    n = nodes.get(args.node_id)
    if not n:
        print(f"node not found: {args.node_id}")
        return
    print(f"Node: {n['id']}")
    print(f"  label:   {n.get('label','')}")
    print(f"  scale:   {n.get('scale')}")
    print(f"  layer:   {n.get('layer')}")
    print(f"  VE:      {n.get('ve_score'):.3f}  VE_h: {n.get('ve_score_harmonic'):.3f}")
    print(f"  saturation: {n.get('saturation'):.2f}    "
          f"prestress: {n.get('prestress_local')}")
    print(f"  asymmetry:  {n.get('asymmetry'):+.2f}")
    ac = n.get("aristotelian_completeness", {})
    print(f"  Aristotelian: completeness={ac.get('completeness')} "
          f"missing={ac.get('missing_causes')}")
    md = n.get("metadata", {})
    if md:
        print(f"  metadata keys: {list(md.keys())}")
        nt = md.get("node_type")
        if nt:
            print(f"  node_type: {nt}")
    out_e = by_src.get(args.node_id, [])
    in_e = by_tgt.get(args.node_id, [])
    print(f"\nOutgoing edges ({len(out_e)}):")
    for e in out_e[:30]:
        print(fmt_edge(e))
    if len(out_e) > 30:
        print(f"    ... +{len(out_e)-30} more")
    print(f"\nIncoming edges ({len(in_e)}):")
    for e in in_e[:30]:
        print(fmt_edge(e))
    if len(in_e) > 30:
        print(f"    ... +{len(in_e)-30} more")


def cmd_neighbors(g: dict, args) -> None:
    nodes = index_nodes(g)
    by_src = index_edges_by_source(g)
    by_tgt = index_edges_by_target(g)
    if args.node_id not in nodes:
        print(f"node not found: {args.node_id}")
        return
    seen = {args.node_id}
    frontier = {args.node_id}
    layers = []
    for hop in range(args.hops):
        next_frontier = set()
        for nid in frontier:
            for e in by_src.get(nid, []):
                next_frontier.add(e["target"])
            for e in by_tgt.get(nid, []):
                next_frontier.add(e["source"])
        next_frontier -= seen
        seen |= next_frontier
        layers.append(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    print(f"Neighborhood of {args.node_id} ({args.hops} hops):")
    for i, layer in enumerate(layers, 1):
        print(f"\n  Hop {i}: {len(layer)} nodes")
        for nid in sorted(layer)[:25]:
            n = nodes.get(nid)
            if n:
                print(fmt_node_short(n))
        if len(layer) > 25:
            print(f"    ... +{len(layer)-25} more")


def cmd_concept(g: dict, args) -> None:
    name = args.name
    by_src = index_edges_by_source(g)
    by_tgt = index_edges_by_target(g)
    nodes = index_nodes(g)
    # Locate the concept structural node
    concept_id = None
    for n in g["nodes"]:
        if n.get("metadata", {}).get("node_type") == "concept":
            if (n.get("metadata", {}).get("canonical", "").lower() == name.lower()
                    or n["id"] == f"concept_{name.lower()}"
                    or name.lower() in n.get("label", "").lower()):
                concept_id = n["id"]
                break
    if not concept_id:
        print(f"no concept node matching '{name}'")
        return
    print(f"Concept: {concept_id}")
    cn = nodes[concept_id]
    print(f"  label: {cn.get('label')}")
    print(f"  axis: {cn.get('metadata', {}).get('axis_tag')}")
    print(f"  VE_h: {cn.get('ve_score_harmonic'):.2f}")
    # Functional uses: nodes whose structural_ref points to this concept
    uses = [n for n in g["nodes"] if n.get("structural_ref") == concept_id]
    print(f"\nFunctional uses ({len(uses)}):")
    for u in sorted(uses, key=lambda x: -x.get("metadata", {}).get("n_hits", 0))[:25]:
        nh = u.get("metadata", {}).get("n_hits", 0)
        doc = u.get("metadata", {}).get("in_document", "?")
        print(f"  {u['id']:<60} n_hits={nh:>3}  in={doc}")
    # Documents that PEER_COHERENT to this concept
    peers = [e for e in by_tgt.get(concept_id, []) if e["slot"] == "PEER_COHERENT"]
    if peers:
        print(f"\nDocuments mentioning concept ({len(peers)}):")
        for e in peers[:25]:
            print(f"  {e['source']:<40}  {e.get('evidence', '')[:60]}")


def cmd_experiment(g: dict, args) -> None:
    raw = args.did
    # Preserve case but normalize the D- prefix only. Canonical IDs use
    # uppercase "D-" + digits + lowercase suffix letter (e.g. "D-101c").
    m = re.match(r"^[Dd][- ]?(\d+)([a-zA-Z]?)$", raw)
    if m:
        did = f"D-{m.group(1)}{m.group(2).lower()}"
    else:
        did = raw
    nodes = index_nodes(g)
    by_src = index_edges_by_source(g)
    by_tgt = index_edges_by_target(g)
    n = nodes.get(did)
    if not n:
        print(f"experiment {did} not in graph")
        return
    print(f"Experiment {did}")
    md = n.get("metadata", {})
    print(f"  state:  {md.get('state', '?')}")
    print(f"  script: {md.get('script', '?')}")
    print(f"  carril: {md.get('carril', '?')}")
    print(f"  feeds:  {md.get('feeds_raw', '?')}")
    print(f"  result: {md.get('resultado_short', '?')[:200]}")
    # Papers it feeds (CONTAINER edges to paper sections)
    feeds = [e for e in by_src.get(did, []) if e["slot"] == "CONTAINER"]
    print(f"\nFeeds {len(feeds)} paper sections:")
    for e in feeds[:15]:
        print(f"  → {e['target']}")
    # Results JSONs (thermodynamic nodes pointing back via structural_ref)
    jsons = [m for m in g["nodes"]
             if m.get("structural_ref") == did
             and m.get("layer") == "thermodynamic"]
    print(f"\nResults JSONs ({len(jsons)}):")
    for j in jsons[:10]:
        print(f"  {j['id']:<60} {j.get('metadata', {}).get('source_file', '')[:60]}")
    # External refs that CAUSE this experiment
    causes = [e for e in by_tgt.get(did, []) if e["slot"] == "CAUSE"]
    if causes:
        print(f"\nExternal causes ({len(causes)}):")
        for e in causes[:10]:
            print(f"  ← {e['source']}  ({e.get('evidence', '')[:60]})")


def cmd_paper(g: dict, args) -> None:
    pid = args.pid.upper()
    nodes = index_nodes(g)
    by_src = index_edges_by_source(g)
    by_tgt = index_edges_by_target(g)
    n = nodes.get(pid)
    if not n:
        print(f"paper {pid} not in graph")
        return
    print(f"Paper {pid}")
    print(f"  label: {n.get('label')}")
    print(f"  VE_h: {n.get('ve_score_harmonic'):.2f}  saturation: "
          f"{n.get('saturation'):.2f}")
    # Sections (children via SUBSTRATE — incoming SUBSTRATE on paper means
    # paper IS substrate of section; outgoing CONTAINER means paper CONTAINS section)
    sections = []
    for e in by_src.get(pid, []):
        if e["slot"] == "CONTAINER":
            sections.append(e["target"])
    print(f"\nSections ({len(sections)}):")
    for sid in sorted(sections)[:30]:
        sn = nodes.get(sid)
        if sn:
            print(f"  {sid:<40} {sn.get('label', '')[:60]}")
    # D-IDs feeding this paper (incoming via paper section CONTAINER edges)
    feeders: set[str] = set()
    for sec_id in sections:
        for e in by_tgt.get(sec_id, []):
            if e["slot"] == "CONTAINER" and e["source"].startswith("D-"):
                feeders.add(e["source"])
    print(f"\nD-IDs feeding this paper ({len(feeders)}):")
    for did in sorted(feeders)[:40]:
        print(f"  {did}")


def cmd_inversions(g: dict, args) -> None:
    """Find D-IDs that appear with conflicting states across paper drafts."""
    print("(inversions detection placeholder — depends on enriched extractors)")
    # For now, just list D-XXX with state=FAIL or state=REFUTED
    refuted = [
        n for n in g["nodes"]
        if n.get("metadata", {}).get("node_type") == "experiment"
        and n.get("metadata", {}).get("state") in ("FAIL", "REFUTED", "SUPERSEDED")
    ]
    print(f"\n{len(refuted)} experiments with non-OK state:")
    for n in refuted[:30]:
        st = n.get("metadata", {}).get("state")
        print(f"  [{n['id']:<10}] {st:<10}  {n.get('label', '')[:80]}")


def cmd_societies(g: dict, args) -> None:
    """List concept clusters (Wittgenstein family resemblance societies)."""
    concept_nodes = [
        n for n in g["nodes"]
        if n.get("metadata", {}).get("node_type") == "concept"
    ]
    print(f"{len(concept_nodes)} curated concepts:\n")
    by_axis = defaultdict(list)
    for c in concept_nodes:
        axis = c.get("metadata", {}).get("axis_tag", "unknown")
        by_axis[axis].append(c)
    for axis in sorted(by_axis):
        print(f"  [{axis}] ({len(by_axis[axis])} concepts)")
        for c in sorted(by_axis[axis], key=lambda x: x["id"]):
            uses = sum(
                1 for n in g["nodes"]
                if n.get("structural_ref") == c["id"]
            )
            print(f"    {c['id']:<35} (used in {uses} docs)")
        print()


def cmd_delta(g: dict, args) -> None:
    other_path = Path(args.other)
    if not other_path.exists():
        print(f"comparison file not found: {other_path}")
        return
    other = load_graph(other_path)
    a_ids = {n["id"] for n in g["nodes"]}
    b_ids = {n["id"] for n in other["nodes"]}
    added = a_ids - b_ids
    removed = b_ids - a_ids
    common = a_ids & b_ids
    a_idx = index_nodes(g)
    b_idx = index_nodes(other)
    changed_ve = []
    for nid in common:
        a_ve = a_idx[nid].get("ve_score_harmonic", 0)
        b_ve = b_idx[nid].get("ve_score_harmonic", 0)
        if abs(a_ve - b_ve) >= 0.1:
            changed_ve.append((nid, b_ve, a_ve))
    print(f"Comparing current vs {other_path.name}")
    print(f"  Nodes:  {len(g['nodes'])} (current) vs {len(other['nodes'])} (other)")
    print(f"  Edges:  {len(g['edges'])} (current) vs {len(other['edges'])} (other)")
    print(f"  Added:    {len(added)}")
    print(f"  Removed:  {len(removed)}")
    print(f"  Δ VE_h≥0.1: {len(changed_ve)}")
    if added:
        print(f"\nSample added nodes (top 15):")
        for nid in sorted(added)[:15]:
            print(f"  + {nid}: {a_idx[nid].get('label', '')[:70]}")
    if removed:
        print(f"\nSample removed nodes (top 15):")
        for nid in sorted(removed)[:15]:
            print(f"  - {nid}: {b_idx[nid].get('label', '')[:70]}")
    if changed_ve:
        print(f"\nLargest VE_h changes (top 15):")
        for nid, before, after in sorted(
            changed_ve, key=lambda x: -abs(x[2] - x[1])
        )[:15]:
            print(f"  {nid:<30} VE_h: {before:.2f} → {after:.2f}")


def cmd_maxims(g: dict, args) -> None:
    """Top-level summary of the maxim layer for this snapshot."""
    summary = g.get("maxims_summary")
    if not summary:
        print("(no maxims data in snapshot — run `python enrich_with_maxims.py`)")
        return
    print("=" * 70)
    print("Boethian / Aristotelian maxim layer")
    print("=" * 70)
    print(f"  {summary['n_violations']:>4} violations across {len(summary['by_slot'])} slot(s)")
    for slot, n in sorted(summary["by_slot"].items(), key=lambda x: -x[1]):
        print(f"      {slot:<22} {n}")
    sev = summary.get("by_severity", {})
    if sev:
        print(f"  by severity:")
        for s_, n in sorted(sev.items(), key=lambda x: -x[1]):
            print(f"      {s_:<22} {n}")
    print(f"  {summary['n_proposals']:>4} inference proposals across {len(summary['by_proposal_type'])} type(s)")
    for t, n in sorted(summary["by_proposal_type"].items(), key=lambda x: -x[1]):
        print(f"      {t:<28} {n}")
    print(f"  {summary['n_nodes_with_findings']:>4} nodes have at least one finding")
    cov = summary.get("coverage", {})
    if cov:
        total = (cov.get("n_checked", 0) + cov.get("n_unable_to_validate", 0)
                 + cov.get("n_no_rule_for_slot", 0))
        print(f"  coverage: checked={cov.get('n_checked')} / "
              f"unable_to_validate={cov.get('n_unable_to_validate')} / "
              f"no_rule_for_slot={cov.get('n_no_rule_for_slot')} (total {total})")
    print()
    print("Run `query_graph.py violations [--severity STRICT|WARN]` for details, "
          "`infer` for proposals.")


def cmd_violations(g: dict, args) -> None:
    vs = g.get("maxims_violations") or []
    if not vs:
        print("(no maxim violations — graph is clean, or snapshot lacks enrichment)")
        return
    if args.slot:
        vs = [v for v in vs if v["slot"] == args.slot.upper()]
    if args.node:
        vs = [v for v in vs if v.get("focus_node") == args.node
              or v.get("source_node") == args.node
              or v.get("target_node") == args.node]
    if getattr(args, "severity", None):
        vs = [v for v in vs if v.get("severity", "VIOLATION") == args.severity.upper()]
    print(f"{len(vs)} violation(s)" + (f" matching slot={args.slot}" if args.slot else "")
          + (f" involving node={args.node}" if args.node else "")
          + (f" severity={args.severity.upper()}" if getattr(args, "severity", None) else "") + ":")
    for v in vs[:50]:
        sev = v.get("severity", "VIOLATION")
        print(f"  [{sev:<8}] [{v['slot']:<22}] {v['violation'][:110]}")
        print(f"             maxim: {v['maxim']}")
    if len(vs) > 50:
        print(f"    ... +{len(vs) - 50} more")


def cmd_infer(g: dict, args) -> None:
    ps = g.get("maxims_proposals") or []
    if not ps:
        print("(no inference proposals — graph is fully wired or lacks enrichment)")
        return
    if args.type:
        ps = [p for p in ps if p["type"] == args.type]
    if args.node:
        ps = [p for p in ps if p.get("focus_node") == args.node]
    print(f"{len(ps)} proposal(s)" + (f" of type={args.type}" if args.type else "")
          + (f" focused on node={args.node}" if args.node else "") + ":")
    for p in ps[:50]:
        print(f"  [{p['type']:<22}] focus={p.get('focus_node', '?'):<28} via {p['from_slot']}")
        print(f"      {(p.get('rationale') or '')[:120]}")
    if len(ps) > 50:
        print(f"    ... +{len(ps) - 50} more")


def cmd_maxim_instances(g: dict, args) -> None:
    """List all edges in the graph that instantiate a given maxim.

    Since each edge carries its slot, the set of "instances of maxim X" is
    exactly the set of edges with that slot. Maxim nodes themselves
    (`maxim_<slot>`) are looked up in node table and their metadata shown.
    """
    slot = args.slot.upper()
    # Look up the maxim node if it exists
    maxim_id = f"maxim_{slot.lower()}"
    nodes = index_nodes(g)
    m = nodes.get(maxim_id)
    if m:
        md = m.get("metadata", {})
        print(f"Maxim node: {maxim_id}")
        print(f"  classical:  {md.get('classical_name', '?')}")
        print(f"  latin:      {md.get('latin_form', '?')}")
        print(f"  english:    {md.get('english_form', '?')}")
        print(f"  axis:       {md.get('axis', '?')} ({md.get('polarity', '?')}, "
              f"{md.get('mechanical', '?')}, {md.get('aristotelian_cause', '?')})")
        print(f"  rules:      validation={md.get('has_validation_rule')}, "
              f"inference={md.get('has_inference_rule')}")
        print()
    else:
        print(f"(no maxim node found for slot={slot} — graph may pre-date maxims_as_nodes extractor)")
        print()
    # All edges of this slot — the actual instances
    instances = [e for e in g["edges"] if e.get("slot") == slot]
    print(f"{len(instances)} edge instance(s) of maxim {slot}:")
    for e in instances[:30]:
        print(f"  {e['source']:<30} → {e['target']:<30}  ({e.get('mechanical_type', '?')}, "
              f"{e.get('confidence', '?')})")
    if len(instances) > 30:
        print(f"    ... +{len(instances) - 30} more")


def cmd_family(g: dict, args) -> None:
    """Wittgensteinian family-resemblance search — semantic without embeddings.

    Two concepts are 'similar' to the extent their use-patterns overlap across
    the project's corpus. Each match is interpretable via the documents that
    use both concepts.
    """
    # Lazy import so the CLI doesn't pay startup cost for unused subcommands
    sys.path.insert(0, str(Path(__file__).parent))
    from core.wittgenstein_search import family_resemblance
    cid = args.concept
    if not cid.startswith("concept_"):
        cid = "concept_" + re.sub(r"[^a-z0-9]+", "_", cid.lower()).strip("_")
    results = family_resemblance(g, cid, measure=args.measure, top_k=args.top)
    if not results:
        print(f"(no family matches for '{cid}' — concept not found or no use-data)")
        return
    print(f"{len(results)} family-resemblance match(es) for {cid} (measure={args.measure}):")
    for r in results:
        print(f"  score={r['score']:.3f}  {r['canonical']:<28} "
              f"({r['n_shared_docs']}/{r['n_other_docs']} shared docs)")
        if r["shared_docs"]:
            print(f"      shared sample: {', '.join(d[:30] for d in r['shared_docs'][:3])}")


def cmd_family_clusters(g: dict, args) -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.wittgenstein_search import family_clusters
    clusters = family_clusters(g, measure=args.measure, threshold=args.threshold)
    print(f"{len(clusters)} cluster(s) with ≥2 members "
          f"(measure={args.measure}, threshold={args.threshold}):")
    for i, cluster in enumerate(clusters, 1):
        print(f"  Cluster {i} ({len(cluster)} members):")
        for m in cluster:
            print(f"    - {m['canonical']:<28} ({m['concept_id']})")


def cmd_porphyrian(g: dict, args) -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.porphyrian_search import porphyrian_summary
    s = porphyrian_summary(g, args.node_id)
    if "error" in s:
        print(f"  {s['error']}")
        return
    print(f"Porphyrian profile for {args.node_id}:")
    print(f"  label: {s['node']['label']}")
    print(f"  scale: s{s['node']['scale']}")
    print(f"  Genera ({len(s['genera'])}):")
    for g_ in s["genera"][:8]: print(f"    ↑ {g_['id']:<28} (scale s{g_['scale']})")
    print(f"  Species ({len(s['species'])}):")
    for sp in s["species"][:12]: print(f"    ↓ {sp['id']:<28} (scale s{sp['scale']})")
    print(f"  Siblings ({len(s['siblings'])}):")
    for sib in s["siblings"][:8]:
        print(f"    ↔ {sib['id']:<28} (n_shared_genera={sib['n_shared_genera']})")


def cmd_siblings(g: dict, args) -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.porphyrian_search import siblings_of
    out = siblings_of(g, args.node_id)
    print(f"{len(out)} sibling(s) of {args.node_id}:")
    for s in out[:30]:
        print(f"  {s['id']:<35} (s{s['scale']}, "
              f"shared genera: {','.join(g_[:20] for g_ in s['shared_genera'][:3])})")


def cmd_prehension(g: dict, args) -> None:
    """Whiteheadian search via key=value features.

    Usage: query_graph.py prehension scale=2 axis_tag=geometry
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from core.whitehead_search import prehension_search
    query = {}
    for kv in args.kv_pairs:
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        # Type-coerce common keys
        if k in ("scale", "scale_min", "scale_max"):
            query[k] = int(v)
        elif k in ("ve_min", "ve_max"):
            query[k] = float(v)
        elif k in ("label_contains", "label_excludes"):
            query[k] = v.split(",")
        else:
            query[k] = v
    results = prehension_search(g, query, top_k=args.top, min_score=0.5)
    print(f"{len(results)} prehension match(es) for query {query}:")
    for r in results:
        print(f"  score={r['score']:>5.2f}  {r['node_id']:<32} {r['label'][:40]}")
        print(f"      matched: {', '.join(r['matched'][:5])}")
        if r['negative_avoided']:
            print(f"      avoided: {', '.join(r['negative_avoided'][:3])}")


def cmd_boecian(g: dict, args) -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.boecian_search import maxim_search
    out = maxim_search(g, args.node_id, args.slot,
                       direction=args.direction, top_k=args.top,
                       require_no_violations=not args.allow_violations)
    print(f"{len(out)} candidate(s) for hypothetical "
          f"{'X→' if args.direction == 'incoming' else args.node_id + '→'}"
          f"{args.node_id if args.direction == 'incoming' else 'Y'}[{args.slot}]:")
    for r in out[:args.top]:
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue
        symbol = "✓" if r["would_pass"] else "✗"
        print(f"  {symbol} {r['candidate_id']:<32} (s{r['scale']}, {r['layer']}) "
              f"violations={r['n_violations']}, inferences={r['n_inferences_fired']}")


def cmd_health(g: dict, args) -> None:
    s = g["stats"]
    n_total = s["n_nodes"]
    print("=" * 70)
    print("Tensegrity graph health report")
    print("=" * 70)
    # Topology
    b0 = s["topology_beta_0_components"]
    b1 = s["topology_beta_1_cycles"]
    print(f"\nTopology:")
    print(f"  β₀ (components):  {b0}    "
          f"{'⚠ fragmented' if b0 > 30 else 'OK'}")
    print(f"  β₁ (cycles):      {b1}    "
          f"{'good — well-triangulated' if b1 > 100 else 'low — sparse'}")
    # Strut/cable balance
    sc = s["strut_cable_ratio"]
    print(f"\nMechanical balance:")
    print(f"  strut/cable ratio: {sc}    "
          f"{'⚠ strut-heavy (cables underused)' if sc > 5 else 'OK'}")
    # VE
    print(f"\nVector-equilibrium distribution:")
    print(f"  avg VE_h: {s['avg_ve_score_harmonic']}    "
          f"max: {s['max_ve_score_harmonic']}")
    god = sum(1 for n in g["nodes"] if n.get("ve_score_harmonic", 0) >= 0.5)
    orph = sum(1 for n in g["nodes"] if n.get("ve_score", 0) < 0.1)
    print(f"  god-nodes (VE_h≥0.5):  {god} ({100*god/n_total:.1f}%)")
    print(f"  orphans   (VE<0.1):    {orph} ({100*orph/n_total:.1f}%)")
    # Aristotelian completeness
    incomp = sum(
        1 for n in g["nodes"]
        if n.get("aristotelian_completeness", {}).get("completeness", 1) < 1
    )
    print(f"\nAristotelian causal completeness:")
    print(f"  incomplete nodes: {incomp} ({100*incomp/n_total:.1f}%)")
    # Saturation
    over = sum(1 for n in g["nodes"] if n.get("saturation", 0) > 1.0)
    print(f"\nLoad:")
    print(f"  overloaded (>12 edges): {over}")
    # Slot usage skew
    print(f"\nSlot usage:")
    used = s["slot_usage"]
    all_slots = [
        "SUCCESSOR", "PREDECESSOR", "SUBSTRATE", "CONTAINER",
        "PEER_COHERENT", "PEER_CONTRADICTORY", "CODE", "THERMO",
        "CAUSE", "EFFECT", "SPECIFICATION", "INSTANTIATION",
    ]
    unused = [s_ for s_ in all_slots if s_ not in used]
    if unused:
        print(f"  unused slots: {unused}")
    underused = [s_ for s_ in all_slots if used.get(s_, 0) < 5]
    if underused:
        print(f"  underused (<5):  {underused}")
    # Maxim layer (if enriched)
    msum = g.get("maxims_summary")
    if msum:
        print(f"\nBoethian/Aristotelian maxim layer:")
        print(f"  violations: {msum['n_violations']}    "
              f"({', '.join(f'{k}={v}' for k, v in msum.get('by_slot', {}).items())})")
        print(f"  inference proposals: {msum['n_proposals']}    "
              f"({', '.join(f'{k}={v}' for k, v in msum.get('by_proposal_type', {}).items())})")
        print(f"  nodes with findings: {msum['n_nodes_with_findings']} "
              f"({100 * msum['n_nodes_with_findings'] / n_total:.1f}%)")
    else:
        print(f"\nMaxim layer: not enriched in this snapshot (run `python enrich_with_maxims.py`)")
    print()


# ----------------------- CLI ---------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--graph", default=None,
                   help="Path to graph JSON (default: auto-discover)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("summary")
    sp = sub.add_parser("god-nodes")
    sp.add_argument("--top", type=int, default=15)
    sp = sub.add_parser("orphans")
    sp.add_argument("--threshold", type=float, default=0.1)
    sp = sub.add_parser("overloaded")
    sp.add_argument("--threshold", type=float, default=1.0)
    sp = sub.add_parser("hot-frontiers")
    sp.add_argument("--ve", type=float, default=0.4)
    sp.add_argument("--ps", type=int, default=2)
    sp = sub.add_parser("asymmetric")
    sp.add_argument("--threshold", type=float, default=0.5)
    sub.add_parser("incomplete")
    sp = sub.add_parser("by-scale"); sp.add_argument("scale")
    sp = sub.add_parser("by-layer"); sp.add_argument("layer")
    sp = sub.add_parser("by-type"); sp.add_argument("node_type")
    sp = sub.add_parser("find"); sp.add_argument("substring")
    sp = sub.add_parser("show"); sp.add_argument("node_id")
    sp = sub.add_parser("neighbors")
    sp.add_argument("node_id")
    sp.add_argument("--hops", type=int, default=1)
    sp = sub.add_parser("concept"); sp.add_argument("name")
    sp = sub.add_parser("experiment"); sp.add_argument("did")
    sp = sub.add_parser("paper"); sp.add_argument("pid")
    sub.add_parser("inversions")
    sub.add_parser("societies")
    sp = sub.add_parser("delta"); sp.add_argument("other")
    sub.add_parser("health")
    sub.add_parser("maxims")
    sp = sub.add_parser("violations")
    sp.add_argument("--slot", default=None, help="Filter by slot name (CAUSE, CONTAINER, ...)")
    sp.add_argument("--node", default=None, help="Filter by node id (focus / source / target)")
    sp.add_argument("--severity", default=None, help="Filter by severity (STRICT, WARN, VIOLATION, INFO)")
    sp = sub.add_parser("infer")
    sp.add_argument("--type", default=None, help="Filter by proposal type (missing_specification, ...)")
    sp.add_argument("--node", default=None, help="Filter by focus node id")
    sp = sub.add_parser("maxim-instances")
    sp.add_argument("slot", help="Slot name (CONTAINER, CAUSE, SUBSTRATE, ...)")
    sp = sub.add_parser("family")
    sp.add_argument("concept", help="Concept id or name (HNC, ETF, IVM, ...)")
    sp.add_argument("--measure", default="cosine", choices=["cosine", "jaccard", "kl"])
    sp.add_argument("--top", type=int, default=10)
    sp = sub.add_parser("family-clusters")
    sp.add_argument("--measure", default="jaccard", choices=["cosine", "jaccard", "kl"])
    sp.add_argument("--threshold", type=float, default=0.4)
    sp = sub.add_parser("porphyrian"); sp.add_argument("node_id")
    sp = sub.add_parser("siblings");   sp.add_argument("node_id")
    sp = sub.add_parser("prehension")
    sp.add_argument("kv_pairs", nargs="+",
                    help="key=value features (e.g. scale=2 axis_tag=geometry label_contains=jitterbug)")
    sp.add_argument("--top", type=int, default=12)
    sp = sub.add_parser("boecian")
    sp.add_argument("node_id")
    sp.add_argument("--slot", required=True,
                    help="Slot to test (CONTAINER, CAUSE, SUBSTRATE, ...)")
    sp.add_argument("--direction", default="outgoing", choices=["outgoing", "incoming"])
    sp.add_argument("--top", type=int, default=10)
    sp.add_argument("--allow-violations", action="store_true",
                    help="include candidates that would violate the maxim")

    args = p.parse_args(argv)

    try:
        graph_path = find_graph_path(args.graph)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    g = load_graph(graph_path)
    print(f"# graph: {graph_path}\n")

    cmd = args.command.replace("-", "_")
    handler = globals().get(f"cmd_{cmd}")
    if not handler:
        print(f"unknown command: {args.command}", file=sys.stderr)
        return 2
    handler(g, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
