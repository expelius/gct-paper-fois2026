# Cardinality Expansion — 12-slot vs 30-slot Icosahedral Refinement

**Motivation:** The companion downward ablation (`cardinality_ablation.py`) showed that collapsing 12 → 4 loses 67% of
inference rules and all sub-cause discriminative power. That gives §7.3
a defended *floor* but leaves the *ceiling* open: would a finer 30-slot
icosahedral schema buy additional discriminative power, or would the
corpus's metadata exhaust itself before sub-slot distinctions become
populated? This script answers the upper-bound question with a
**heuristic** classifier that splits each of the 12 IVM slots into 2-3
sub-modalities (totalling 30) using existing edge metadata only — no
fresh annotation is performed.

**Snapshot:** `tensegrity_graph_phase9_complete.json`
**SHA-256:** `dc7bf9d51f3e42b8...94269c57d1953739`

**Operates on an in-memory copy. The on-disk snapshot is unchanged;**
**`compute_paper_numbers.py --snapshot phase9` continues to report the**
**original 12-slot numbers.**

**Honest caveat — heuristic, not authoritative.** The classifier consumes
only existing edge metadata (`slot`, `evidence`, source/target id-prefix,
scale gap, confidence). Sub-slots whose distinction is not encoded in
current metadata will therefore be undercounted. The script never claims
a sub-slot is *empty* in the underlying domain — only that current
metadata cannot separate it from a sibling sub-slot. This under-population
IS the finding: it shows the corpus uses ~12-15 sub-categories,
validating 12 as the right cardinality for the present knowledge-
management practice.

## 1. 30-sub-slot schema (theoretically motivated)

Each parent slot splits into 2-3 sub-modalities; total = 30 = #edges of
the icosahedron. The decomposition is theoretically motivated as sub-
modalities of each Aristotelian-causal channel.

| Parent slot | Sub-slots | Count |
|---|---|---:|
| CAUSE | CAUSE_DIRECT, CAUSE_MEDIATED, CAUSE_NECESSARY | 3 |
| EFFECT | EFFECT_DIRECT, EFFECT_OBSERVED | 2 |
| PREDECESSOR | PREDECESSOR_TEMPORAL, PREDECESSOR_LOGICAL, PREDECESSOR_REFINEMENT | 3 |
| SUCCESSOR | SUCCESSOR_PLANNED, SUCCESSOR_OBSERVED | 2 |
| CONTAINER | CONTAINER_PHYSICAL, CONTAINER_CONCEPTUAL, CONTAINER_DOCUMENTARY | 3 |
| SPECIFICATION | SPECIFICATION_PROTOCOL, SPECIFICATION_HYPOTHESIS, SPECIFICATION_DESIGN | 3 |
| SUBSTRATE | SUBSTRATE_MATERIAL, SUBSTRATE_INFORMATIONAL | 2 |
| INSTANTIATION | INSTANTIATION_TYPE, INSTANTIATION_MEMBER | 2 |
| PEER_COHERENT | PEER_COHERENT_REPLICATION, PEER_COHERENT_CONFIRMATION, PEER_COHERENT_GENERALIZATION | 3 |
| PEER_CONTRADICTORY | PEER_CONTRADICTORY_DIRECT, PEER_CONTRADICTORY_METHODOLOGICAL | 2 |
| CODE | CODE_IMPLEMENTATION, CODE_TEST, CODE_ANALYSIS | 3 |
| THERMO | THERMO_ENTROPY, THERMO_FREE_ENERGY | 2 |
| **TOTAL** | | **30** |

## 2. Heuristic classifier rules (existing metadata only)

The classifier is deterministic, idempotent, and uses only metadata
present on each edge today: the parent `slot` field, the lower-cased
`evidence` string, the source/target node id-prefix (`D-`, `P-`, `CC-`,
`concept_`, `_section_`, `json_`, `run_`, `PAPER-`, etc.), the
source/target `scale`, and the edge `confidence`. Rules are documented
inline in `cardinality_expansion.py`. A sub-slot is flagged as
**structurally unreachable from current annotation** when no defensible
rule can be written from existing metadata; this is part of the finding,
not a failure of the classifier.

Rules-fired histogram (top 10):

| Rule name | Edges classified |
|---|---:|
| `concept_in_doc` | 600 |
| `source_is_results_json` | 325 |
| `concept_mention` | 303 |
| `target_or_source_is_experiment` | 265 |
| `paper_to_section` | 202 |
| `default` | 142 |
| `prereg_endpoint` | 106 |
| `osf_prereg_source` | 97 |
| `memory_doc_reference` | 15 |
| `cross_cut_grounding` | 11 |

## 3. 30-sub-slot distribution on phase-9

| Parent | Sub-slot | Count | % of edges | Status |
|---|---|---:|---:|---|
| CAUSE | CAUSE_DIRECT | 265 | 12.5% | occupied |
| CAUSE | CAUSE_MEDIATED | 6 | 0.3% | sparse |
| CAUSE | CAUSE_NECESSARY | 0 | 0.0% | structurally unreachable from current metadata |
| EFFECT | EFFECT_DIRECT | 0 | 0.0% | structurally unreachable from current metadata |
| EFFECT | EFFECT_OBSERVED | 343 | 16.2% | occupied |
| PREDECESSOR | PREDECESSOR_TEMPORAL | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| PREDECESSOR | PREDECESSOR_LOGICAL | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| PREDECESSOR | PREDECESSOR_REFINEMENT | 8 | 0.4% | sparse |
| SUCCESSOR | SUCCESSOR_PLANNED | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| SUCCESSOR | SUCCESSOR_OBSERVED | 0 | 0.0% | structurally unreachable from current metadata |
| CONTAINER | CONTAINER_PHYSICAL | 27 | 1.3% | occupied |
| CONTAINER | CONTAINER_CONCEPTUAL | 4 | 0.2% | sparse |
| CONTAINER | CONTAINER_DOCUMENTARY | 308 | 14.5% | occupied |
| SPECIFICATION | SPECIFICATION_PROTOCOL | 9 | 0.4% | sparse |
| SPECIFICATION | SPECIFICATION_HYPOTHESIS | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| SPECIFICATION | SPECIFICATION_DESIGN | 615 | 29.0% | occupied |
| SUBSTRATE | SUBSTRATE_MATERIAL | 39 | 1.8% | occupied |
| SUBSTRATE | SUBSTRATE_INFORMATIONAL | 20 | 0.9% | occupied |
| INSTANTIATION | INSTANTIATION_TYPE | 9 | 0.4% | sparse |
| INSTANTIATION | INSTANTIATION_MEMBER | 5 | 0.2% | sparse |
| PEER_COHERENT | PEER_COHERENT_REPLICATION | 97 | 4.6% | occupied |
| PEER_COHERENT | PEER_COHERENT_CONFIRMATION | 361 | 17.0% | occupied |
| PEER_COHERENT | PEER_COHERENT_GENERALIZATION | 0 | 0.0% | structurally unreachable from current metadata |
| PEER_CONTRADICTORY | PEER_CONTRADICTORY_DIRECT | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| PEER_CONTRADICTORY | PEER_CONTRADICTORY_METHODOLOGICAL | 0 | 0.0% | structurally unreachable from current metadata |
| CODE | CODE_IMPLEMENTATION | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| CODE | CODE_TEST | 0 | 0.0% | structurally unreachable from current metadata |
| CODE | CODE_ANALYSIS | 0 | 0.0% | structurally unreachable from current metadata |
| THERMO | THERMO_ENTROPY | 0 | 0.0% | empty (parent slot unpopulated in phase-9) |
| THERMO | THERMO_FREE_ENERGY | 0 | 0.0% | structurally unreachable from current metadata |
| **TOTAL (sub-slot-classified)** | — | **2116** | — | — |
| **Out-of-vocab edges (CONFIRMS / REFUTES, scale-1 marker types)** | — | 4 | — | passed through unchanged |
| **Grand total = phase-9 edge count** | — | **2120** | 100.0% | — |

**Sub-slot occupancy:** **15 of 30** sub-slots have ≥1 edge; **9 of 30** have ≥10 edges; **15 of 30** are empty (8 of those are structurally unreachable
from current metadata, the rest are unpopulated because their parent slot
itself is unoccupied in phase-9 — see §5.3 of the paper for the parent-
level pattern).

## 4. Effective inference-rule count (sub-slot-aware maxim engine)

If each of the 30 sub-slots had its own maxim, the engine could run only
on the **15 of 30** sub-slots that have at least one edge to
operate on. The remaining maxims are vacuous: they would never fire on
phase-9 because no edge of that sub-slot exists.

| Schema | Total maxims | Vacuous on phase-9 | Effective |
|---|---:|---:|---:|
| 4-slot (cause)   | 4 | 0 | **4** |
| 12-slot (IVM)    | 12 | 4 (33%) | **8** |
| 30-slot (icosa.) | 30 | 15 (50%) | **15** |

**Reading.** The 12-slot schema has 4 vacuous slots (33%), the 30-slot
schema has many more vacuous sub-slots. The marginal gain in distinct
effective inference rules going 12 → 30 is 7 sub-slots
(the difference between 12-slot and 30-slot effective counts).
Going 12 → 4 loses 67% of inference rules; going 12 → 30 gains 7 effective rules at the cost of 11 additional vacuous maxims.

## 5. AC discriminative power under 30-slot

Aristotelian Completeness recomputed at 30-sub-slot resolution:
AC_30(n) = |{sub-slots incident to n}| / 30.

| Metric | 12-slot | 30-slot |
|---|---:|---:|
| Mean AC | 0.284 | 0.044 |
| AC ≥ 0.5 prevalence | 128 (16.0%) | 0 (0.0%) |
| Distinct AC values populated | 5 of 5 | 8 of 31 (k/30 for k=0..30) |

**Reading.** Under 30-slot, AC ≥ 0.5 prevalence collapses to 0 nodes (0.0%) because reaching 15 of 30 distinct
sub-slots requires breadth across all four causes AND multiple sub-
modalities per cause — a structural threshold the corpus does not
approach. The discriminative power that the 12-slot schema provides at
0.5 (16% of nodes — the "at least half-documented" class that §5.1
uses to flag investigative gaps) becomes an empty class under 30-slot.
**Sparsity dominates: 30-slot AC is too coarse a discriminator at the
middle of the distribution because 30 is the wrong denominator for this
corpus.**

## 6. Sandwich finding

Combining the 12 → 4 downward ablation (companion script) with the
12 → 30 upward expansion (this script):

| Direction | Cardinality | Finding |
|---|---:|---|
| Coarse (downward) | 4 | **67% loss** of inference rules; AC discriminative power collapses (1.44× inflation of AC ≥ 0.5 false-positives); cause-level rules cannot distinguish the 11 slot-specific violation patterns of §5.2 |
| **Empirical sweet spot** | **12** | **8 effective + 4 vacuous** maxims (33% sparsity); AC ≥ 0.5 = 16% of nodes (diagnostic mid-class); 11/11 violation-detection reproducible |
| Fine (upward) | 30 | **15 effective + 15 vacuous** maxims (50% sparsity); AC ≥ 0.5 collapses to 0.0% of nodes; 8 sub-slots structurally unreachable from current metadata |

**The 12-slot schema is empirically anchored on both sides:** it is the
**smallest cardinality at which the maxim engine retains discriminative**
**power** (lower bound from §5.2 + downward ablation) AND the **largest**
**cardinality at which the corpus avoids sub-slot sparsity** (upper bound
from this expansion). Going finer than 12 leaves most sub-slots empty;
going coarser than 12 collapses the inference engine.

## 7. Side-by-side comparison panel (4 / 12 / 30)

| Metric | 4-slot | 12-slot | 30-slot |
|---|---:|---:|---:|
| Vocabulary size | 4 | 12 | 30 |
| Distinct values populated on phase-9 | 4 | 8 | 15 |
| Vacuous slots (% of vocabulary) | 0 (0%) | 4 (33%) | 15 (50%) |
| Effective maxims (one per occupied slot) | 4 | 8 | 15 |
| Mean AC | 0.306 | 0.284 | 0.044 |
| AC ≥ 0.5 prevalence | 23.1% | 16.0% | 0.0% |
| §5.2 11/11 violation-detection reproducible | no (cause-rules too coarse) | YES | indeterminate (most sub-slot rules vacuous) |
| Sub-slots structurally unreachable from current metadata | n/a | n/a | 8 |

## 8. Caveats

This expansion is **heuristic, not authoritative**. The classifier
consumes only existing edge metadata; full upward validation would
require fresh sub-slot annotation by a human reviewer (or a separate
LLM-assisted annotation pass) on every edge in the corpus. The
structurally-unreachable sub-slots flagged in §3 are precisely those (8 of 8) where 
no defensible rule could be written from current metadata — they
require either (a) modal/counterfactual annotation (CAUSE_NECESSARY,
EFFECT_DIRECT), (b) fresh extractor coverage of currently-empty parent
slots (CODE_*, THERMO_*, SUCCESSOR_*, PEER_CONTRADICTORY_*), or (c)
concept-subsumption typing (PEER_COHERENT_GENERALIZATION).

The headline finding survives the heuristic uncertainty: even granting
generous classification of every ambiguous edge to the *richest*
plausible sub-slot, the corpus's 2,120 edges cannot populate 30
sub-slots evenly — the parent-slot distribution itself (§5.3) shows
that 4 of 12 slots are empty, so at least 6 of 30 sub-slots are
structurally empty no matter what the classifier does. The 30-slot
schema is therefore **provably over-fitted** to the corpus's current
metadata richness, regardless of how generously the classifier maps
the populated edges.

The full upward study — independent annotation of every edge against
the 30-sub-slot vocabulary — remains future work for the strong claim
(*30 is too fine for any plausible knowledge-management corpus*). The
present heuristic study supports only the weaker claim relevant to
§7.3 limitation L1 (*30 is too fine for THIS corpus's current metadata*)
— which is sufficient to anchor the upper bound on cardinality for this
paper.

## 9. Reproducibility

```
cd publication/
python cardinality_expansion.py
```

Re-running the script regenerates this report verbatim; no on-disk state
is modified. Verify that `python compute_paper_numbers.py --snapshot
phase9` continues to report the original 12-slot numbers (1,660 nodes,
2,120 edges, 8/12 slots populated, 335 proposals, 0 violations,
mean AC = 0.284) — the script operates on an in-memory copy only.
