# Cardinality Ablation — 12-slot vs 4-slot Tetrahedral Collapse

**Motivation:** §7.3 of the GCT paper admits that the choice of 12 slots
rests on the cuboctahedron's Vector-Equilibrium properties rather than on
a derivation from knowledge-representation theory. This ablation provides
a one-direction empirical anchor for the cardinality argument: it collapses
the 12 slots into the 4 Aristotelian causes (the natural tetrahedral
coarse-grain) and quantifies what is lost.

**Snapshot:** `tensegrity_graph_phase9_complete.json`
**SHA-256:** `dc7bf9d51f3e42b8...94269c57d1953739`

**Operates on an in-memory copy. The on-disk snapshot is unchanged;**
**`compute_paper_numbers.py --snapshot phase9` continues to report the**
**original 12-slot numbers.**

## 1. Collapse mapping

Each of the 12 IVM slots maps to exactly one Aristotelian cause:

| Cause | 12-slot members | Native schema agreement? |
|---|---|---|
| FORMAL | SPECIFICATION, INSTANTIATION, CODE | ✓; INSTANTIATION: native=material; ✓ |
| MATERIAL | SUBSTRATE, THERMO | ✓; ✓ |
| EFFICIENT | CAUSE, PREDECESSOR, SUCCESSOR | ✓; ✓; ✓ |
| FINAL | EFFECT, CONTAINER, PEER_COHERENT, PEER_CONTRADICTORY | ✓; ✓; PEER_COHERENT: native=None (lateral); PEER_CONTRADICTORY: native=None (lateral) |

**Mapping caveat — divergence from native schema.** The schema's native
`Slot.aristotelian_cause` field disagrees with the task mapping in three
places: `INSTANTIATION` is natively `material` (this report maps it to
`FORMAL` because it instantiates a *type*, which is a formal-cause artefact);
`PEER_COHERENT` and `PEER_CONTRADICTORY` are natively `None` ("lateral,
dialectical, not causal"), and this report maps them to `FINAL` because
in the GCT they encode the telos of cross-validation (corroboration /
refutation). The divergence reflects two defensible coverings: the schema
treats peer slots as *outside* the four-cause partition (yielding only 10
causally-typed slots out of 12), while this report forces a total covering
for the ablation. Both readings are documented in §7.3 of the paper.

## 2. Side-by-side comparison

### 2.1 Slot distribution

**12-slot (original §5.3):**

| Slot | Count | % of edges |
|---|---:|---:|
| SPECIFICATION | 624 | 29.4% |
| INSTANTIATION | 14 | 0.7% |
| CODE | 0 | 0.0% |
| SUBSTRATE | 59 | 2.8% |
| THERMO | 0 | 0.0% |
| CAUSE | 271 | 12.8% |
| PREDECESSOR | 8 | 0.4% |
| SUCCESSOR | 0 | 0.0% |
| EFFECT | 343 | 16.2% |
| CONTAINER | 339 | 16.0% |
| PEER_COHERENT | 458 | 21.6% |
| PEER_CONTRADICTORY | 0 | 0.0% |
| **Total** | **2120** | 100.0% |
| **Distinct slot values populated** | **8/12** | — |

**4-slot (collapsed):**

| Cause | Count | % of edges | Member slots aggregated |
|---|---:|---:|---|
| FORMAL | 638 | 30.1% | SPECIFICATION, INSTANTIATION, CODE |
| MATERIAL | 59 | 2.8% | SUBSTRATE, THERMO |
| EFFICIENT | 279 | 13.2% | CAUSE, PREDECESSOR, SUCCESSOR |
| FINAL | 1140 | 53.8% | EFFECT, CONTAINER, PEER_COHERENT, PEER_CONTRADICTORY |
| **Total** | **2120** | 100.0% | — |
| **Distinct cause values populated** | **4/4** | — | — |

**Granularity loss in this corpus:** 8 populated slots → 4 populated causes = 50% reduction in
slot-level addressability. The collapse erases the distinction between (e.g.)
CAUSE and PREDECESSOR — a query for "what efficient-causally precedes node X?"
can no longer separate logical causes from temporal predecessors. (Note: under
a corpus that populates all 12 slots — see §6.4 biomedical instantiation,
which achieves 12/12 — the granularity loss would be 12 → 4 = 67%.)

### 2.2 Aristotelian Completeness distribution

Under 4-slot collapse, AC trivially equals (causes incident / 4) for every
node — the 4-slot AC is *equivalent to slot occupancy at the 4-bucket
level*, which makes the schema **trivially complete for any node with at
least one edge per cause**. The discriminative power of the AC metric
therefore collapses.

| AC bucket | 12-slot count | 12-slot % | 4-slot count | 4-slot % |
|---|---:|---:|---:|---:|
| 0/4 (AC = 0.00) | 43 | 5.4% | 34 | 4.3% |
| 1/4 (AC = 0.25) | 627 | 78.6% | 580 | 72.7% |
| 2/4 (AC = 0.50) | 106 | 13.3% | 157 | 19.7% |
| 3/4 (AC = 0.75) | 19 | 2.4% | 24 | 3.0% |
| 4/4 (AC = 1.00) | 3 | 0.4% | 3 | 0.4% |
| **Mean AC** | **0.284** | — | **0.306** | — |
| **Distinct AC values populated** | **5/5** | — | **5/5** | — |

**AC ≥ 0.5 prevalence:** 128 nodes (16.0%) under 12-slot
→ 184 nodes (23.1%) under 4-slot. The collapse inflates
the "at least half-documented" class because intermediate-cause nodes that
the 12-slot schema flagged as missing distinct sub-causes (e.g., a node with
PREDECESSOR but no CAUSE) now both satisfy the same EFFICIENT bucket. The
AC = 1.0 ceiling itself is anchored at 3 nodes (0.4%) in both columns
because the native AC computation already used a 4-cause partition; the
ablation's signal is not the ceiling but the *erosion of the slot-aware
intermediate distinctions* (1/4 vs 2/4 vs 3/4) that the 12-slot schema
preserved.

### 2.3 Boethian maxim engine

| Metric | 12-slot | 4-slot |
|---|---:|---:|
| Distinct maxims (one per slot) | 12 | 4 |
| Inference-rule reduction | — | **67%** |
| Pre-registration audit (proposals) | 335 | ≤4 generic per node (non-comparable) |
| Violations on phase-9 corpus | 0 | undefined (cause-level rules would not catch slot-level violations) |

Each of the 12 maxims encodes a slot-specific structural rule (e.g., the
CAUSE maxim forbids self-loops; the SPECIFICATION maxim demands a formal
anchor for every experiment; the THERMO maxim forbids EXTRACTED-confidence
edges into structural targets). Collapsing slots to causes means at most
**one maxim per cause** can be defined — a 67% reduction in distinct
inference rules. The 11 / 11 violation-detection result reported in §5.2
is not reproducible under the collapse: cause-level rules are too coarse
to distinguish the 11 distinct violation patterns the paper documents.

### 2.4 Graph statistics (unchanged — sanity check)

| Metric | 12-slot | 4-slot |
|---|---:|---:|
| Total nodes | 1,660 | 1,660 |
| Total edges | 2,120 | 2,120 |
| Structural nodes | 798 | 798 |

Node and edge counts are by construction unchanged — the collapse
re-types edges, never adds or removes them.

## 3. Headline finding

The 4-slot tetrahedral schema is more parsimonious but loses substantial
inference granularity that the 12-slot schema affords:

- **Maxim engine: 12 → 4 maxims = 67% reduction** in distinct inference rules.
- **Slot distribution: 8 → 4 distinct values populated = 50% reduction** in slot-level addressability on this corpus
  (rises to 12 → 4 = 67% reduction on a fully-populated corpus, e.g. §6.4 biomedical).
- **AC discriminative power: AC ≥ 0.5 prevalence inflates 1.44×** (16.0% → 23.1%) because the
  collapse merges nodes that the 12-slot schema separated by sub-cause.

The 12-slot schema is empirically the **smaller cardinality at which the**
**maxim engine retains its current discriminative power** on this corpus.

## 4. Caveats

This ablation tests **only the downward direction** on the cardinality
scale (12 → 4). It does not establish that 12 is *optimal*; that would
require also testing the upward direction (12 → 30 icosahedral) on a
corpus annotated at sub-slot granularity, which the present corpus does
not provide. The 30-slot icosahedral expansion remains future work for
which fresh annotation passes would be required.

The collapse is a re-aggregation of an existing snapshot, not an
independent extraction. It tests how much information is lost going *down*
the cardinality scale; it does not test whether some genuinely different
4-slot schema (e.g., one that does not respect Aristotelian causes) might
preserve more granularity through a different bucketing strategy.

## 5. Reproducibility

```
cd publication/
python cardinality_ablation.py
```

Re-running the script regenerates this report verbatim; no on-disk state
is modified. Verify that `python compute_paper_numbers.py --snapshot phase9`
continues to report the original 12-slot numbers (8/12 slots occupied,
335 proposals, 0 violations, mean AC = 0.284) — the script operates on an
in-memory copy only.
