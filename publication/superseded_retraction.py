"""superseded_retraction.py — Defeasibility-lite retraction-propagation
analysis on top of the frozen GCT phase-9 snapshot.

Background (paper §7.3, L2). The Boethian maxim engine performs *monotone*
deductive inference: once a maxim's premises are satisfied, its conclusion is
asserted permanently and there is no in-engine mechanism for retracting a
conclusion when later evidence undermines its premise. Many real-world
research-evidence relations are irreducibly defeasible — an experiment is a
prima facie cause of a claim, but the claim may be retracted if the
experiment is found confounded, superseded by a methodologically corrected
follow-up, or invalidated by a later replication.

This script implements *defeasibility-lite*: it does NOT modify the maxim
engine; it operates purely as analysis on the frozen snapshot, using the
SUPERSEDED relationships already encoded in the graph (PREDECESSOR edges
whose evidence string carries the marker ``"extends or supersedes"`` —
emitted automatically by ``experiments_log`` when D-ID suffix conventions
indicate a corrective follow-up, e.g. ``D-101c`` supersedes ``D-101``).

The analysis:

  1. Detects supersession pairs ``(successor X, superseded Y)`` from
     PREDECESSOR-edge evidence text.
  2. For each superseded node Y, traverses outgoing edges (edges where
     ``Y`` is the source) to identify *downstream consumers* — paper
     sections, paper-anchor nodes, candidate claims, and other
     experiments that drew evidential support from Y.
  3. Emits a SUPERSEDED_INHERITED warning per downstream consumer:
     "this evidential edge points back to a superseded experiment;
     consumers should re-validate against the successor X before
     citing." The warning is *informational* — it is not an
     in-engine retraction, but a downstream-consumer signal that
     a defeasible reasoner could use as an attack relation.
  4. Reports counts and an estimated *defeasibility coverage* —
     the fraction of CAUSE/EFFECT chains in the graph that pass
     through at least one superseded node, i.e. the fraction of
     the corpus's evidential reasoning that a defeasible
     inference layer would re-evaluate.

Outputs both stdout report and a markdown file
``publication/superseded_retraction_report.md``.

Run:
    cd publication
    python superseded_retraction.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


SNAPSHOT = Path(__file__).resolve().parent.parent / "tensegrity_graph_phase9_complete.json"
REPORT_PATH = Path(__file__).resolve().parent / "superseded_retraction_report.md"

# Marker pattern emitted by core/extractors/experiments_log.py when the
# D-ID suffix convention signals supersession.
SUPERSEDE_RE = re.compile(
    r"D-ID suffix indicates\s+(?P<successor>D-\S+)\s+extends or supersedes\s+(?P<superseded>D-\S+)"
)

# Slots that carry evidential support — the chains a defeasible reasoner
# would need to re-evaluate. CAUSE flows from cause to effect; EFFECT is the
# reciprocal annotation; SPECIFICATION grounds an artifact in its formal
# protocol; PREDECESSOR is the lineage chain itself.
EVIDENTIAL_SLOTS = {"CAUSE", "EFFECT", "SPECIFICATION", "PREDECESSOR"}


def load_graph(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def detect_supersessions(edges: list) -> list[dict]:
    """Return [{successor, superseded, edge_id, evidence}, ...] for every
    edge whose ``evidence`` text matches the supersession marker."""
    pairs = []
    for e in edges:
        ev = e.get("evidence") or ""
        m = SUPERSEDE_RE.search(ev)
        if not m:
            continue
        # Belt-and-braces: the edge should be PREDECESSOR with source =
        # successor (later D-ID) and target = superseded (earlier D-ID).
        successor = m.group("successor")
        superseded = m.group("superseded")
        pairs.append({
            "successor": successor,
            "superseded": superseded,
            "edge_id": e.get("id"),
            "slot": e.get("slot"),
            "evidence": ev,
            "edge_source": e.get("source"),
            "edge_target": e.get("target"),
        })
    return pairs


def build_outgoing_index(edges: list) -> dict[str, list[dict]]:
    """source-node → list of outgoing edges."""
    out = defaultdict(list)
    for e in edges:
        s = e.get("source")
        if s:
            out[s].append(e)
    return out


def build_incoming_index(edges: list) -> dict[str, list[dict]]:
    inc = defaultdict(list)
    for e in edges:
        t = e.get("target")
        if t:
            inc[t].append(e)
    return inc


def downstream_consumers(node_id: str,
                         outgoing: dict[str, list[dict]]) -> list[dict]:
    """Return outgoing edges whose slot is in EVIDENTIAL_SLOTS — these are
    the edges that propagate the superseded node's evidence to consumers.

    PREDECESSOR is filtered to suffix-lineage edges only on the OUTGOING
    side (outgoing PREDECESSOR from a superseded node would be unusual —
    supersession edges *point to* the superseded node, not from it).
    """
    consumers = []
    for e in outgoing.get(node_id, []):
        slot = e.get("slot")
        if slot in EVIDENTIAL_SLOTS:
            consumers.append({
                "consumer": e.get("target"),
                "via_slot": slot,
                "via_edge": e.get("id"),
            })
    return consumers


def compute_defeasibility_coverage(nodes: list,
                                   edges: list,
                                   superseded_ids: set[str]) -> dict:
    """Estimate the fraction of CAUSE/EFFECT chains that traverse at least
    one superseded node. We model a *chain* as a 2-edge walk (A → B → C)
    where both edges are CAUSE or EFFECT — this captures the minimal unit
    of multi-step evidential reasoning the maxim engine would chain over.

    A chain is *touched* by supersession if any of {A, B, C} is in
    ``superseded_ids``. We report:
      - total CAUSE/EFFECT edges
      - total 2-edge CAUSE/EFFECT chains
      - touched chains and percentage
      - 1-edge support: fraction of CAUSE/EFFECT edges directly incident
        on a superseded node
    """
    ce_edges = [e for e in edges
                if e.get("slot") in {"CAUSE", "EFFECT"}]
    n_ce = len(ce_edges)

    # 1-edge incidence
    incident = 0
    for e in ce_edges:
        if e.get("source") in superseded_ids or e.get("target") in superseded_ids:
            incident += 1

    # 2-edge chains
    by_source = defaultdict(list)
    for e in ce_edges:
        by_source[e.get("source")].append(e)

    n_chains = 0
    n_chains_touched = 0
    for e1 in ce_edges:
        mid = e1.get("target")
        for e2 in by_source.get(mid, []):
            n_chains += 1
            a, c = e1.get("source"), e2.get("target")
            if (a in superseded_ids
                    or mid in superseded_ids
                    or c in superseded_ids):
                n_chains_touched += 1

    return {
        "total_ce_edges": n_ce,
        "ce_edges_incident_to_superseded": incident,
        "incident_pct": (100.0 * incident / n_ce) if n_ce else 0.0,
        "total_2edge_ce_chains": n_chains,
        "ce_chains_touching_superseded": n_chains_touched,
        "chain_touch_pct": (100.0 * n_chains_touched / n_chains) if n_chains else 0.0,
    }


def render_report(graph: dict,
                  pairs: list[dict],
                  per_pair_consumers: list[dict],
                  coverage: dict) -> str:
    n_nodes = len(graph.get("nodes", []))
    n_edges = len(graph.get("edges", []))
    superseded_ids = {p["superseded"] for p in pairs}
    successor_ids = {p["successor"] for p in pairs}

    lines = []
    lines.append("# SUPERSEDED Retraction Propagation — Defeasibility-Lite Report")
    lines.append("")
    lines.append(f"**Snapshot:** `tensegrity_graph_phase9_complete.json` "
                 f"({n_nodes} nodes, {n_edges} edges)")
    lines.append("")
    lines.append(
        "This report is a defeasibility-lite analysis on top of the frozen "
        "GCT snapshot. The maxim engine itself remains monotone; this script "
        "exposes explicit SUPERSEDED retraction metadata that downstream "
        "consumers (papers, candidate claims, follow-up experiments) can use "
        "to filter or re-evaluate evidential chains running through superseded "
        "nodes. See `PAPER_DRAFT.md` §5.7 and §7.3 (L2) for the framing."
    )
    lines.append("")
    lines.append("## 1. Headline counts")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Supersession edges detected (parseable evidence marker) | "
                 f"{len(pairs)} |")
    lines.append(f"| Distinct superseded nodes (Y) | "
                 f"{len(superseded_ids)} |")
    lines.append(f"| Distinct successor nodes (X) | "
                 f"{len(successor_ids)} |")
    pairs_with_successor_in_graph = sum(
        1 for p in pairs
        if p["successor"] in {n["id"] for n in graph["nodes"]}
    )
    lines.append(f"| Pairs whose successor X is present as a node | "
                 f"{pairs_with_successor_in_graph} / {len(pairs)} |")
    lines.append("")

    lines.append("## 2. Per-pair downstream propagation")
    lines.append("")
    lines.append("For each (successor X, superseded Y) pair, we list the "
                 "downstream consumers of Y — edges leaving Y whose slot is "
                 "in {CAUSE, EFFECT, SPECIFICATION, PREDECESSOR}. Each "
                 "consumer would be flagged SUPERSEDED_INHERITED by a "
                 "defeasibility-lite filter.")
    lines.append("")
    lines.append("| Successor X | Superseded Y | Y outgoing evidential edges | Distinct downstream consumers |")
    lines.append("|---|---|---:|---:|")
    total_distinct_consumers = set()
    for entry in per_pair_consumers:
        consumers = entry["consumers"]
        distinct = {c["consumer"] for c in consumers}
        total_distinct_consumers |= distinct
        lines.append(
            f"| {entry['successor']} | {entry['superseded']} | "
            f"{len(consumers)} | {len(distinct)} |"
        )
    lines.append("")
    lines.append(f"**Total distinct downstream consumers across all "
                 f"superseded nodes:** {len(total_distinct_consumers)}")
    lines.append("")

    # Slot distribution of consumer edges
    slot_counter = Counter()
    for entry in per_pair_consumers:
        for c in entry["consumers"]:
            slot_counter[c["via_slot"]] += 1
    if slot_counter:
        lines.append("**Distribution of propagation paths by slot:**")
        lines.append("")
        lines.append("| Slot | Edges propagating retraction |")
        lines.append("|---|---:|")
        for slot, n in sorted(slot_counter.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {slot} | {n} |")
        lines.append("")

    lines.append("## 3. Worked example: D-101 → D-101c")
    lines.append("")
    # Prefer the D-101c pair (canonical example in the paper); fall back to
    # any pair where superseded == "D-101" if D-101c is not present.
    target = next((e for e in per_pair_consumers
                   if e["superseded"] == "D-101"
                   and e["successor"] == "D-101c"), None)
    if target is None:
        target = next((e for e in per_pair_consumers
                       if e["superseded"] == "D-101"), None)
    if target:
        lines.append(
            f"**Pair:** the methodologically corrected experiment "
            f"`{target['successor']}` (Papyan ETF metric using "
            f"`std_across_pairs` and `norm_cv`) supersedes the original "
            f"`{target['superseded']}` (mean inter-scale angle, shown by "
            f"the successor to be an algebraic tautology of three centred "
            f"vectors)."
        )
        lines.append("")
        n_cons = len(target["consumers"])
        edge_word = "edge" if n_cons == 1 else "edges"
        lines.append(
            f"`{target['superseded']}` has **{n_cons} outgoing evidential "
            f"{edge_word}**. A defeasibility-lite filter would emit a "
            f"SUPERSEDED_INHERITED warning on each, recommending the "
            f"consumer re-validate against `{target['successor']}` (which "
            f"applies the methodologically correct metric) before citing:"
        )
        lines.append("")
        lines.append("| Consumer node | Via slot | Via edge id |")
        lines.append("|---|---|---|")
        for c in target["consumers"]:
            lines.append(f"| {c['consumer']} | {c['via_slot']} | {c['via_edge']} |")
        lines.append("")
    else:
        lines.append("(D-101 not found among superseded nodes — see Section 2 above.)")
        lines.append("")

    lines.append("## 4. Estimated defeasibility coverage")
    lines.append("")
    lines.append(
        "We estimate the fraction of evidential chains a full defeasible "
        "reasoner would re-evaluate. A *2-edge CAUSE/EFFECT chain* (A → B → C, "
        "both edges in {CAUSE, EFFECT}) is the minimal unit of multi-step "
        "evidential reasoning the maxim engine would chain over. A chain is "
        "*touched* if any of A, B, C is a superseded node."
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total CAUSE/EFFECT edges | {coverage['total_ce_edges']} |")
    lines.append(f"| CAUSE/EFFECT edges incident to a superseded node | "
                 f"{coverage['ce_edges_incident_to_superseded']} "
                 f"({coverage['incident_pct']:.2f}%) |")
    lines.append(f"| Total 2-edge CAUSE/EFFECT chains | "
                 f"{coverage['total_2edge_ce_chains']} |")
    lines.append(f"| 2-edge chains touching a superseded node | "
                 f"{coverage['ce_chains_touching_superseded']} "
                 f"({coverage['chain_touch_pct']:.2f}%) |")
    lines.append("")

    lines.append("## 5. Honest framing")
    lines.append("")
    lines.append(
        "This is **defeasibility-lite**, not full defeasible reasoning. "
        "The maxim engine still asserts conclusions monotonically. What "
        "the snapshot now carries is *retraction metadata* — explicit "
        "supersession edges plus a downstream-consumer index — that any "
        "external reasoner (a default-logic layer, an argumentation "
        "framework, a manual reviewer) can use as an attack relation. "
        "Full defeasibility would require integrating that attack "
        "relation into the maxim engine itself, so that "
        "`missing_specification` proposals on consumers of a superseded "
        "experiment are emitted with `confidence: defeated_by(X)` rather "
        "than as ordinary positive proposals. That extension is "
        "straightforward but beyond the scope of the present submission."
    )
    lines.append("")
    lines.append("---")
    lines.append("Generated by `publication/superseded_retraction.py` from the frozen phase-9 snapshot.")
    lines.append("")
    return "\n".join(lines)


def main():
    graph = load_graph(SNAPSHOT)
    edges = graph.get("edges", [])

    pairs = detect_supersessions(edges)

    outgoing = build_outgoing_index(edges)
    per_pair_consumers = []
    for p in pairs:
        cons = downstream_consumers(p["superseded"], outgoing)
        per_pair_consumers.append({
            "successor": p["successor"],
            "superseded": p["superseded"],
            "consumers": cons,
        })

    superseded_ids = {p["superseded"] for p in pairs}
    coverage = compute_defeasibility_coverage(graph["nodes"], edges, superseded_ids)

    report = render_report(graph, pairs, per_pair_consumers, coverage)
    REPORT_PATH.write_text(report, encoding="utf-8")

    # Stdout summary (compact)
    print(f"Snapshot: {SNAPSHOT.name}")
    print(f"Supersession pairs detected: {len(pairs)}")
    print(f"Distinct superseded nodes: {len(superseded_ids)}")
    total_distinct_consumers = set()
    for entry in per_pair_consumers:
        for c in entry["consumers"]:
            total_distinct_consumers.add(c["consumer"])
    print(f"Distinct downstream consumers across all superseded nodes: "
          f"{len(total_distinct_consumers)}")
    print(f"CAUSE/EFFECT edges incident to a superseded node: "
          f"{coverage['ce_edges_incident_to_superseded']} / "
          f"{coverage['total_ce_edges']} "
          f"({coverage['incident_pct']:.2f}%)")
    print(f"2-edge CAUSE/EFFECT chains touching a superseded node: "
          f"{coverage['ce_chains_touching_superseded']} / "
          f"{coverage['total_2edge_ce_chains']} "
          f"({coverage['chain_touch_pct']:.2f}%)")
    print(f"Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
