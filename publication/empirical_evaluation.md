# GCT — Empirical Evaluation Data (phase9 frozen reference)
# Source: tensegrity_graph_phase9_complete.json
# SHA-256: dc7bf9d51f3e42b8...94269c57d1953739
# Date: 2026-05-02

This document contains the canonical numerical claims for §5 of the paper, anchored to the **frozen phase-9 snapshot**. Reviewers can reproduce every number below by running `python compute_paper_numbers.py` (default) from the publication directory.

For the post-evaluation extensibility-demonstration data backing §7.1 (CODE-slot closure), see the **Appendix: phase-14 extensibility-demo data** at the bottom of this file, or run `python compute_paper_numbers.py --snapshot phase14`.

---

## Graph Statistics (Table for paper §5)

| Metric | Value |
|--------|-------|
| Total nodes | 1,660 |
| Total edges | 2,120 |
| Structural nodes | 798 |
| Connected components (β₀) | 272 |
| Largest component | 1,090 nodes (65.7%) |
| Singleton components | 34 |
| Distinct slot types occupied | 8/12 (4 slots at 0%) |

## Aristotelian Completeness Distribution (Table for paper §5.1)

**Verified 2026-05-02 against `tensegrity_graph_phase9_complete.json` SHA-256 `dc7bf9d51f3e42b8...d1953739`** via `compute_paper_numbers.py`. Numbers below are the canonical pre-computed `aristotelian_completeness.completeness` field stored on each structural node.

| Causes present (k/4) | Count | Percentage |
|---|---|---|
| 0/4 (AC = 0.00) | 43 | 5.4% |
| 1/4 (AC = 0.25) | 627 | 78.6% |
| 2/4 (AC = 0.50) | 106 | 13.3% |
| 3/4 (AC = 0.75) | 19 | 2.4% |
| 4/4 (AC = 1.00) | 3 | 0.4% |
| **Mean AC** | **0.284** | — |

**Interpretation for paper**: 84.0% of structural nodes have fewer than 2 of 4 Aristotelian causes documented.
Only 3 nodes (0.4%) achieve full Aristotelian completeness, confirming that scientific knowledge representation
in practice is systematically underdocumented with respect to formal and material causes.
This validates the GCT's inference engine: the 335 missing_specification proposals identify
precisely the nodes lacking formal cause documentation.

### AC by node type (top types — id-prefix inference)
| Node type | Mean AC | n |
|---|---|---|
| cross_cut | 0.477 | 11 |
| code_holon | 0.470 | 25 |
| experiment | 0.464 | 77 |
| paper | 0.305 | 100 |
| paper_section | 0.250 | 203 |

## Boethian Maxims Engine (Table for paper §5.2)

| Metric | Value |
|---|---|
| Total proposals generated | 335 |
| Violations detected | 0 |
| Dominant proposal type | missing_specification (100%) |

**Interpretation**: The engine detects 0 logical violations (the graph is internally consistent)
and generates 335 actionable proposals — all identifying nodes that lack a SPECIFICATION
(formal cause) edge. These 335 proposals constitute a machine-generated research audit:
the exact set of experimental nodes that have not yet been formally pre-registered.

A synthetic-injection ablation (`violation_ablation.py`) confirms the engine catches violations when present: 11/11 = 100% detection rate across the 11 maxims that define a `validation_rule`. EFFECT carries no validator by design (observational, not normative). See `violation_ablation_report.md` for the full report.

## Slot Distribution (Figure for paper §4)

| Slot | Mechanism | Count | % of edges |
|---|---|---|---|
| SPECIFICATION | STRUT | 624 | 29.4% |
| PEER_COHERENT | STRUT | 458 | 21.6% |
| EFFECT | CABLE | 343 | 16.2% |
| CONTAINER | STRUT | 339 | 16.0% |
| CAUSE | STRUT | 254 | 12.0% |
| SUBSTRATE | CABLE | 59 | 2.8% |
| INSTANTIATION | CABLE | 14 | 0.7% |
| PREDECESSOR | STRUT | 8 | 0.4% |
| CODE | STRUT | 0 | 0.0% |
| SUCCESSOR | CABLE | 0 | 0.0% |
| PEER_CONTRADICTORY | CABLE | 0 | 0.0% |
| THERMO | CABLE | 0 | 0.0% |

**Note for paper**: 4 of 12 slots are unoccupied in phase-9 (CODE, SUCCESSOR, PEER_CONTRADICTORY, THERMO).
This is a finding: the GCT schema is richer than any single research project will fully instantiate,
mirroring how natural language has syntactic categories that individual sentences leave unused.
§7.1 of the paper demonstrates how the CODE slot is closed by a single new extractor in a post-evaluation
hardening pass (see Appendix below for phase-14 numbers).

## VE Score Distribution (Figure for paper §5.4)

| Metric | Value |
|---|---|
| Structural nodes | 798 |
| God nodes (VE ≥ 0.5) | 26 (3.3%) |
| Mean VE | 0.189 |
| Top god node | D-101c (VE = 0.833) |

Top 6 god nodes: D-101c (0.833), D-101 (0.667), D-097 (0.667), D-099 (0.667), D-251b (0.667), D-253 (0.667)
— all experiments with multiple replications, predecessor chains, and paper citations.

## Wittgenstein Family Resemblance Coverage (Table for paper §5.5)

**Verified 2026-05-02 against `tensegrity_graph_phase9_complete.json` SHA-256 `dc7bf9d51f3e42b8...d1953739`** via `compute_paper_numbers.py`. Both family-layer and snapshot denominators are reported explicitly.

| Node type | With family | In family layer | Snapshot total | Family-layer coverage | Snapshot coverage |
|---|---|---|---|---|---|
| experiment    | 67 | 67 |  77 | **100%** | 87% |
| concept       | 35 | 35 | 573 | **100%** |  6% |
| paper         | 18 | 18 | 116 | **100%** | 16% |
| paper_section | 10 | 10 | 203 | **100%** |  5% |

Family resemblance score statistics across all evaluable pairs:
- min = 0.100, mean = 0.470, max = 1.000

**Note**: Within the family-eligible subset (those nodes with sufficient connectivity to support a meaningful Jaccard or cosine evaluation), 100% coverage is achieved across all four artifact types. Snapshot coverage shows the gradient between artifacts that have accumulated enough graph structure to be similarity-evaluable (experiments at 87%) and those that have not (paper sections at 5%, concepts at 6%).

## Porphyrian Relations Coverage (Table for paper §5.5)

| Metric | Value |
|---|---|
| Nodes with Porphyrian data | 350 |
| With genera (CONTAINER parents) | 319 |
| With species (CONTAINER children) | 37 |

---

# Key Numbers for Abstract / Introduction (anchored on phase-9)

"Applied to a corpus of 1,660 knowledge nodes and 2,120 typed edges across 8 node types
and 12 Aristotelian-causal slot categories, the GCT: (i) identified that 84.0% of structural
nodes are documented with fewer than 2 of 4 Aristotelian causes; (ii) generated 335 formally
sound inference proposals via the Boethian maxim engine, with 0 logical violations detected
and 100% detection rate on a synthetic-injection ablation; (iii) achieved 100% Wittgenstein
family-resemblance coverage across all four artifact types within the family-eligible subset
(67/67 experiments, 35/35 concepts, 18/18 papers, 10/10 paper_sections); and (iv) identified
26 god nodes (VE ≥ 0.5) that emerge algebraically as the most evidentially central knowledge
constructs."

---

# Appendix: phase-14 extensibility-demo data (for §7.1)

The phase-14 snapshot (`tensegrity_graph_phase14_complete.json`, SHA-256 `2acc255497832764...2c28732ba09b1a2f`) is the post-evaluation companion snapshot produced by adding a single new extractor (`code_implements`) to the build pipeline. It backs the schema-extensibility argument in §7.1 — it is **not** part of the §5 evaluation.

Phase-14 differences from phase-9 worth recording:

| Metric | phase-9 (paper §5) | phase-14 (§7.1 demo) |
|---|---|---|
| Total nodes | 1,660 | 2,067 |
| Total edges | 2,120 | 3,282 |
| Slots occupied | 8/12 | 10/12 |
| CODE edges | 0 | 67 |
| PEER_CONTRADICTORY edges | 0 | 1 |
| Maxim violations | 0 | 4 (3 PREDECESSOR clock-collisions on D-309c + 1 SUBSTRATE — none caused by the new CODE extractor) |
| Maxim proposals | 335 | 446 |

The 67 CODE edges are emitted in three families:
1. **Slot-population grounding** — for each extractor E that populated edges of slot S during build, emit `maxim_<S> → holon_code_<E>`. Computed automatically from the build's `provenance.extractor` trail.
2. **Schema-definition grounding** — all 12 maxims → `holon_code_schema` and `holon_code_maxims` (24 edges).
3. **Factory-definition grounding** — targeted maxim → code_holon edges for `holon_meta`, `node_types`, `builder`, `diagnostics`, `inference`, `viz_precompute`, `extractors_base`, `extractors`, `workspace_config`.

The closure of the CODE slot is verified to:
- Be deterministic and idempotent on the CODE-edge subset across 3 trials
- Introduce **0 maxim violations specific to CODE**
- Pass all 16 `tests/test_build_invariants.py`
- Require no modifications to the schema, the maxim engine, or any pre-existing extractor

Reviewers can reproduce the phase-14 numbers by running `python compute_paper_numbers.py --snapshot phase14`.
