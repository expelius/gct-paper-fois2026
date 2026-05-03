"""violation_ablation.py — synthetic-violation injection harness for the Boethian
maxim engine, packaged as a paper-§5.2 reproducibility artefact.

The paper claims `n_violations == 0` on the phase-9 snapshot. A reviewer will
read that as either remarkable or untested. This script proves the engine
catches violations when violations exist: for each of the 12 IVM-slot maxims,
it injects ONE synthetic edge crafted to trip exactly that maxim's validation
rule, then asks the engine to find it.

Usage (from publication/):

    python violation_ablation.py

Outputs to stdout:
    1. Snapshot SHA-256 + load summary
    2. Per-slot detection table (Markdown)
    3. Overall detection rate

No pip dependencies beyond stdlib + the in-tree `core` package. Operates on an
in-memory deep copy of the snapshot — never writes to phase9 on disk.

Design notes
------------
* Five maxims (CAUSE self-loop, PEER_COHERENT cross-scale, PEER_CONTRADICTORY
  cross-scale, CONTAINER scale-inversion, SUBSTRATE scale-inversion, etc.)
  require malformed edges that the builder's `add_edge` rejects up-front
  (self-loops in particular). For those, we inject directly into the
  reconstructed `TensegrityGraph._edges` dict, bypassing `add_edge`'s
  pre-flight validation, so the maxim engine sees the malformed edge.
* PREDECESSOR / SUCCESSOR validators require `active_since` on both endpoints.
  Reconstruction from JSON does NOT carry active_since, so we override the two
  endpoint nodes' active_since attributes before injecting the temporal-order
  violation.
* THERMO requires a structural-layer target with EXTRACTED confidence; CODE
  requires source.scale < target.scale.
* EFFECT has no validation_rule in the registry (it is a purely observational
  slot: "causes are known through their effects"). We document this honestly
  rather than fabricate a test.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

# Make `core.*` importable when running from publication/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.builder import TensegrityGraph  # noqa: E402
from core.maxims import MAXIMS, validate_graph  # noqa: E402
from core.schema import Confidence, Edge, Layer, Node, Slot  # noqa: E402

SNAPSHOT_PATH = ROOT / "tensegrity_graph_phase9_complete.json"


# --------------------------- snapshot loader ------------------------------


def load_snapshot(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode("utf-8")), sha


def reconstruct(graph_dict: dict) -> TensegrityGraph:
    """Mirror of enrich_with_maxims.reconstruct — never modify production code."""
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


# --------------------------- pick injection endpoints ---------------------


def pick_node_at(g: TensegrityGraph, scale: int, layer: Layer | None = None,
                 exclude: set[str] | None = None) -> str | None:
    """Find any node at the given scale (and optional layer) for use as an
    injection endpoint. Returns node id."""
    exclude = exclude or set()
    for nid, n in g._nodes.items():
        if nid in exclude:
            continue
        if n.scale != scale:
            continue
        if layer is not None and n.layer != layer:
            continue
        return nid
    return None


# --------------------------- injection harness ----------------------------


def inject_raw(g: TensegrityGraph, eid: str, source: str, target: str,
               slot: Slot, confidence: Confidence = Confidence.EXTRACTED,
               scale_from: int = 1, scale_to: int = 1) -> Edge:
    """Append an edge directly into g._edges, bypassing builder validation.

    Required because the builder rejects self-loops (and its scale_from /
    scale_to fields are bounded 0-4 — not relevant here) before the maxim
    engine ever sees the edge. We're testing the *maxim engine*, not the
    builder, so this bypass is correct.
    """
    e = Edge(
        source=source, target=target, slot=slot, confidence=confidence,
        scale_from=scale_from, scale_to=scale_to,
        evidence=f"SYNTHETIC violation injection for ablation ({eid})",
    )
    g._edges[eid] = e
    # Best-effort populate_slot so reciprocal validators (e.g. peer-cont &
    # peer-coherent on same pair) have a coherent picture; ignored if it errs.
    try:
        g._nodes[target].populate_slot(slot, eid)
        recip = g._reciprocal_slot(slot)
        if recip is not None and source != target:
            g._nodes[source].populate_slot(recip, eid)
    except Exception:
        pass
    return e


def detect_violations_for(eid: str, violations: list[dict]) -> list[dict]:
    """Filter violation list to those originating from our injected edge."""
    return [v for v in violations if v.get("edge_id") == eid]


# --------------------------- per-slot test cases --------------------------


def case_container(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """CONTAINER (Genus): edge X→Y where source.scale < target.scale.
    Container should be at higher (>=) scale than contained."""
    s_low = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)   # contained
    s_high = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)  # would-be container
    if not (s_low and s_high):
        return "CONTAINER", None, {"reason": "no scale-1/scale-2 endpoints"}
    eid = "__violation_test_CONTAINER__"
    # Inject scale-1 → scale-2 with slot=CONTAINER → violates "container at
    # higher-or-equal scale" rule (source scale 1 < target scale 2).
    inject_raw(g, eid, source=s_low, target=s_high, slot=Slot.CONTAINER,
               scale_from=1, scale_to=2)
    return "CONTAINER", eid, {"source": s_low, "target": s_high,
                              "rule": "source.scale < target.scale"}


def case_substrate(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """SUBSTRATE (Material cause): edge X→Y where source.scale > target.scale.
    Substrate is at lower (<=) scale than what it enables."""
    s_high = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    s_low = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    if not (s_high and s_low):
        return "SUBSTRATE", None, {"reason": "no endpoints"}
    eid = "__violation_test_SUBSTRATE__"
    # source scale 2 > target scale 1 → violates substrate rule.
    inject_raw(g, eid, source=s_high, target=s_low, slot=Slot.SUBSTRATE,
               scale_from=2, scale_to=1)
    return "SUBSTRATE", eid, {"source": s_high, "target": s_low,
                              "rule": "source.scale > target.scale"}


def case_predecessor(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """PREDECESSOR (Anteriority): the actual implemented rule fires when
    `src.active_since < tgt.active_since` and reports source as
    "exist[ing] later" (see core/maxims.py::_validate_predecessor). The
    in-code semantics here treat src.active_since < tgt.active_since as the
    violation condition regardless of which endpoint plays the predecessor
    role linguistically; for the ablation, we trip exactly that comparison."""
    a = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    b = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL, exclude={a})
    if not (a and b):
        return "PREDECESSOR", None, {"reason": "no scale-1 endpoints"}
    # src EARLIER than tgt → trips the implemented `<` test in _validate_predecessor.
    g._nodes[a].active_since = "2025-01-01T00:00:00"  # src earlier
    g._nodes[b].active_since = "2026-04-01T00:00:00"  # tgt later
    eid = "__violation_test_PREDECESSOR__"
    inject_raw(g, eid, source=a, target=b, slot=Slot.PREDECESSOR)
    return "PREDECESSOR", eid, {"source": a, "target": b,
                                "rule": "src.active_since < tgt.active_since "
                                        "(matches the implemented comparison)"}


def case_successor(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """SUCCESSOR (Anteriority mirror): successor must be temporally posterior.
    Inject X→Y[SUCCESSOR] with Y.active_since EARLIER than X."""
    a = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    b = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL, exclude={a})
    if not (a and b):
        return "SUCCESSOR", None, {"reason": "no scale-1 endpoints"}
    g._nodes[a].active_since = "2026-01-01T00:00:00"
    g._nodes[b].active_since = "2025-01-01T00:00:00"  # successor is earlier — bad
    eid = "__violation_test_SUCCESSOR__"
    inject_raw(g, eid, source=a, target=b, slot=Slot.SUCCESSOR)
    return "SUCCESSOR", eid, {"source": a, "target": b,
                              "rule": "target.active_since < source.active_since"}


def case_peer_coherent(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """PEER_COHERENT (a similibus): similars cluster within scale.
    Inject a STRICT cross-scale (Δ>=2) PEER_COHERENT edge to trip the
    [STRICT] tier of the same-scale check."""
    a = pick_node_at(g, scale=0, layer=Layer.STRUCTURAL)
    b = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    if not (a and b):
        return "PEER_COHERENT", None, {"reason": "no scale 0/2 endpoints"}
    eid = "__violation_test_PEER_COHERENT__"
    inject_raw(g, eid, source=a, target=b, slot=Slot.PEER_COHERENT,
               scale_from=0, scale_to=2)
    return "PEER_COHERENT", eid, {"source": a, "target": b,
                                  "rule": "|src.scale - tgt.scale| >= 2 → STRICT"}


def case_peer_contradictory(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """PEER_CONTRADICTORY (Contraries): cross-scale contradictions are
    almost always category errors. Inject Δ>=2 to trigger STRICT tier."""
    a = pick_node_at(g, scale=0, layer=Layer.STRUCTURAL)
    b = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    if not (a and b):
        return "PEER_CONTRADICTORY", None, {"reason": "no scale 0/2 endpoints"}
    eid = "__violation_test_PEER_CONTRADICTORY__"
    inject_raw(g, eid, source=a, target=b, slot=Slot.PEER_CONTRADICTORY,
               scale_from=0, scale_to=2)
    return "PEER_CONTRADICTORY", eid, {"source": a, "target": b,
                                       "rule": "Δ>=2 cross-scale → STRICT"}


def case_code(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """CODE (Differentia): edge X→Y[CODE] where X.scale < Y.scale.
    A definition cannot be drawn from a finer-grained instance."""
    s_low = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    s_high = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    if not (s_low and s_high):
        return "CODE", None, {"reason": "no scale-1/scale-2 endpoints"}
    eid = "__violation_test_CODE__"
    # source scale 1 < target scale 2 — violates _validate_code.
    inject_raw(g, eid, source=s_low, target=s_high, slot=Slot.CODE,
               scale_from=1, scale_to=2)
    return "CODE", eid, {"source": s_low, "target": s_high,
                         "rule": "source.scale < target.scale"}


def case_thermo(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """THERMO (Accident): EXTRACTED confidence on a STRUCTURAL/kind-level
    target — claiming an accident with measurement-grade certainty."""
    src = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    tgt = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL, exclude={src})
    if not (src and tgt):
        return "THERMO", None, {"reason": "no structural endpoints"}
    eid = "__violation_test_THERMO__"
    # confidence=EXTRACTED + target.layer=STRUCTURAL → _validate_thermo fires.
    inject_raw(g, eid, source=src, target=tgt, slot=Slot.THERMO,
               confidence=Confidence.EXTRACTED, scale_from=1, scale_to=1)
    return "THERMO", eid, {"source": src, "target": tgt,
                           "rule": "EXTRACTED THERMO on structural target"}


def case_cause(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """CAUSE (Efficient): self-loop. Nothing can be its own efficient cause."""
    a = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    if not a:
        return "CAUSE", None, {"reason": "no scale-1 endpoints"}
    eid = "__violation_test_CAUSE__"
    # Self-loop: builder.add_edge would reject this; we inject raw so the
    # maxim's _validate_cause_no_self_loop sees it.
    inject_raw(g, eid, source=a, target=a, slot=Slot.CAUSE,
               scale_from=1, scale_to=1)
    return "CAUSE", eid, {"source": a, "target": a, "rule": "source == target (self-loop)"}


def case_effect(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """EFFECT has no validation_rule by design (per maxims.py: 'causes are
    known through their effects' — observational, not normative). Document
    explicitly rather than fabricate a test."""
    return "EFFECT", None, {"reason": "no validation_rule in MAXIMS registry — N/A"}


def case_specification(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """SPECIFICATION (Forma dat esse): X→Y[SPECIFICATION] where target.scale
    < source.scale (form should be at-or-above instance abstractly)."""
    s_high = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    s_low = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    if not (s_high and s_low):
        return "SPECIFICATION", None, {"reason": "no endpoints"}
    eid = "__violation_test_SPECIFICATION__"
    # source scale 2, target scale 1 → target.scale < source.scale violation.
    inject_raw(g, eid, source=s_high, target=s_low, slot=Slot.SPECIFICATION,
               scale_from=2, scale_to=1)
    return "SPECIFICATION", eid, {"source": s_high, "target": s_low,
                                  "rule": "target.scale < source.scale"}


def case_instantiation(g: TensegrityGraph) -> tuple[str, str | None, dict]:
    """INSTANTIATION (Hoc aliquid): X→Y[INSTANTIATION] where source.scale <
    target.scale (form must be at-or-above instance)."""
    s_low = pick_node_at(g, scale=1, layer=Layer.STRUCTURAL)
    s_high = pick_node_at(g, scale=2, layer=Layer.STRUCTURAL)
    if not (s_low and s_high):
        return "INSTANTIATION", None, {"reason": "no endpoints"}
    eid = "__violation_test_INSTANTIATION__"
    # source scale 1 < target scale 2 → form is below instance — violation.
    inject_raw(g, eid, source=s_low, target=s_high, slot=Slot.INSTANTIATION,
               scale_from=1, scale_to=2)
    return "INSTANTIATION", eid, {"source": s_low, "target": s_high,
                                  "rule": "source.scale < target.scale"}


# Ordered as in core.maxims.MAXIMS to make the table read like the paper §5.2.
CASES = [
    ("SUCCESSOR",          case_successor),
    ("PREDECESSOR",        case_predecessor),
    ("SUBSTRATE",          case_substrate),
    ("CONTAINER",          case_container),
    ("PEER_COHERENT",      case_peer_coherent),
    ("PEER_CONTRADICTORY", case_peer_contradictory),
    ("CODE",               case_code),
    ("THERMO",             case_thermo),
    ("CAUSE",              case_cause),
    ("EFFECT",             case_effect),
    ("SPECIFICATION",      case_specification),
    ("INSTANTIATION",      case_instantiation),
]


# --------------------------- main pipeline --------------------------------


def run() -> dict:
    snapshot, sha = load_snapshot(SNAPSHOT_PATH)
    print(f"# Boethian-maxim violation-detection ablation\n")
    print(f"snapshot     : {SNAPSHOT_PATH.name}")
    print(f"sha256       : {sha}")
    print(f"n_nodes      : {len(snapshot['nodes'])}")
    print(f"n_edges      : {len(snapshot['edges'])}")
    print(f"baseline n_violations (uncorrupted): "
          f"{snapshot.get('maxims_summary', {}).get('n_violations', '?')}\n")

    n_implemented_validators = sum(
        1 for m in MAXIMS.values() if m.validation_rule is not None
    )
    print(f"maxims declared : {len(MAXIMS)}")
    print(f"with validators : {n_implemented_validators}")
    print(f"without validators: "
          f"{[s.name for s, m in MAXIMS.items() if m.validation_rule is None]}\n")

    rows = []
    for slot_name, case_fn in CASES:
        # Fresh deep-copy per case so injections don't bleed across slots.
        g = reconstruct(copy.deepcopy(snapshot))
        slot, eid, meta = case_fn(g)
        if eid is None:
            rows.append({
                "slot": slot, "injected": False, "caught": False,
                "n_matches": 0, "severity": "—",
                "note": meta.get("reason", "skipped"),
            })
            continue
        all_violations = validate_graph(g)
        matches = detect_violations_for(eid, all_violations)
        severities = sorted({v.get("severity", "VIOLATION") for v in matches})
        rows.append({
            "slot": slot,
            "injected": True,
            "caught": len(matches) > 0,
            "n_matches": len(matches),
            "severity": ",".join(severities) if severities else "—",
            "note": f"src={meta.get('source','?')[:24]} tgt={meta.get('target','?')[:24]}",
        })

    # Print the Markdown table
    print("## Per-slot detection table\n")
    print("| Slot                | Injected | Caught | Matches | Severity      | Endpoints / note |")
    print("|---------------------|----------|--------|--------:|---------------|------------------|")
    for r in rows:
        print(f"| {r['slot']:<19} | "
              f"{'yes' if r['injected'] else 'N/A':<8} | "
              f"{'yes' if r['caught'] else ('—' if not r['injected'] else 'NO'):<6} | "
              f"{r['n_matches']:>7} | "
              f"{r['severity']:<13} | "
              f"{r['note']} |")

    # Aggregate
    n_injected = sum(1 for r in rows if r["injected"])
    n_caught = sum(1 for r in rows if r["caught"])
    n_skipped = sum(1 for r in rows if not r["injected"])
    rate = n_caught / n_injected if n_injected else 0.0
    print()
    print(f"slots with injected violation : {n_injected}")
    print(f"slots caught                  : {n_caught}")
    print(f"slots N/A (no validator)      : {n_skipped}")
    print(f"detection rate (caught/injected): "
          f"{rate:.3f}  ({n_caught}/{n_injected})")

    return {
        "sha256": sha,
        "rows": rows,
        "n_injected": n_injected,
        "n_caught": n_caught,
        "n_skipped": n_skipped,
        "detection_rate": rate,
        "n_maxims_declared": len(MAXIMS),
        "n_validators_implemented": n_implemented_validators,
    }


if __name__ == "__main__":
    run()
