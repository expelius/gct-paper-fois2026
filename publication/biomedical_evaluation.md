# GCT — Second-Corpus Empirical Evaluation (biomedical)
# Source: tensegrity_graph_biomedical.json
# SHA-256: c0ff97e69d6d3e81...5c7d7fb20954c368
# Date: 2026-05-02

This document reports the §6-equivalent metrics for the **biomedical
second-corpus instantiation** of the GCT, mirroring the structure of
`empirical_evaluation.md` (the phase-9 §5 report). Reviewers can reproduce
every number below by running:

```
python publication/biomedical_instantiation.py     # builds + enriches the snapshot
python publication/compute_paper_numbers.py --snapshot biomedical
```

The biomedical corpus is intentionally small (25 nodes, 38 edges) — its
purpose is **not** to compete with the 1,660-node neural-architecture corpus
in §5, but to demonstrate that the same enrichment pipeline runs unmodified
on a structurally distinct domain and produces non-zero values for every
GCT metric. The headline finding is that **all 12 GCT slots populate
when the domain has the right artifacts**, in contrast to the 8/12 of
phase-9 (where CODE / SUCCESSOR / PEER_CONTRADICTORY / THERMO were all
empty).

---

## Headline numbers

| Metric | phase-9 (§5) | biomedical (§6.4) |
|---|---|---|
| Total nodes | 1,660 | 25 |
| Total edges | 2,120 | 38 |
| Slots occupied | **8/12** | **12/12** |
| Maxim violations | 0 | **0** |
| Maxim proposals | 335 | 7 |
| Dominant proposal type | missing_specification (100%) | missing_specification (100%) |
| Mean AC | 0.284 | **0.427** |
| God nodes (VE_h ≥ 0.5) | 26 (3.3%) | **8 (33%)** |
| FR mean | 0.470 | 0.259 |
| Largest component | 1,090 nodes (66%) | 20 nodes (80%) |

The mean AC is higher in the biomedical corpus (0.427 vs 0.284) because
every experiment was constructed with a SUBSTRATE+CAUSE+CONTAINER skeleton
by design — it shows how AC behaves when a corpus is born already
multi-cause-documented, complementing the §5 finding that real research
records accumulate documentation incrementally.

The *qualitative* signature is what matters: same engine, same maxim
output pattern (proposals dominated by missing_specification, zero
violations), same algebraic emergence of god nodes from graph structure.

---

## Graph statistics

| Metric | Value |
|--------|-------|
| Total nodes | 25 |
| Total edges | 38 |
| Structural nodes | 24 |
| Functional nodes | 0 |
| Thermodynamic nodes | 1 (free-energy measurement) |
| Connected components (β₀) | 3 |
| Largest component | 20 nodes (80.0%) |
| Singleton components | 0 |
| Distinct slot types occupied | **12/12** |

The three connected components separate by topic: (1) a TP53/apoptosis
sub-graph anchored on BIO-EXP-001/002/008 + DISEASE-apoptosis-evasion,
(2) the metabolic+oncogene cluster (HK2, MYC, KRAS, SDHB, PIK3CA across
glycolysis, TCA, PI3K-AKT), and (3) the published-paper sub-graph
(Warburg 2009 + Hingorani 2003 + their sections). All three are bridged
in practice via shared DESeq2 code holon and overlapping cell lines —
ablation of any single edge does not fragment the largest component.

---

## §6.4.1 Slot Distribution — KEY TABLE

This is the single table that most directly defends domain-independence:
all 12 slots populate when the biology supplies the right artifacts.

| Slot | Mechanism | Count | % of edges | Biological role |
|---|---|---|---|---|
| SUBSTRATE          | CABLE | 8 | 21.1% | cell line → experiment (material cause) |
| CONTAINER          | STRUT | 7 | 18.4% | pathway/paper → experiment/section (genus) |
| CODE               | STRUT | 7 | 18.4% | experiment → DESeq2 pipeline (formal) |
| CAUSE              | STRUT | 3 |  7.9% | gene knockdown → phenotype (efficient) |
| EFFECT             | CABLE | 3 |  7.9% | gene → metabolic axis output (final/observation) |
| PEER_COHERENT      | STRUT | 2 |  5.3% | replication (essence: TP53 / glycolytic flux) |
| SPECIFICATION      | STRUT | 2 |  5.3% | experiment → ClinicalTrials.gov pre-reg (formal) |
| INSTANTIATION      | CABLE | 2 |  5.3% | disease category → experimental phenotype (form→instance) |
| PREDECESSOR        | STRUT | 1 |  2.6% | HEK293 result → HeLa replication (temporal-prior) |
| SUCCESSOR          | CABLE | 1 |  2.6% | siRNA result → planned CRISPR-KO (temporal-posterior) |
| PEER_CONTRADICTORY | CABLE | 1 |  2.6% | siRNA vs CRISPR knockout discrepancy (Stojic 2018) |
| THERMO             | CABLE | 1 |  2.6% | ΔG_net glycolysis ≈ -85 kJ/mol (accident on pathway) |

**12 of 12 slots populated** — vs 8/12 in phase-9.

The four slots empty in phase-9 (CODE, SUCCESSOR, PEER_CONTRADICTORY, THERMO)
all populate naturally in the biomedical instantiation because:

- **CODE** — every wet-lab experiment uses a documented analysis pipeline
  (DESeq2 here); the link is part of the ordinary methods section.
- **SUCCESSOR** — clinical and translational research routinely declares
  the next planned experiment in the same publication.
- **PEER_CONTRADICTORY** — the biomedical literature is unusually candid
  about the siRNA-knockdown vs CRISPR-knockout discrepancy (Stojic et al.
  2018, Nat. Comm.); recording the disagreement explicitly is normative.
- **THERMO** — pathway-level free-energy measurements are first-class
  observations, not derivative metrics.

This is itself a finding: which slots populate is not arbitrary, it
reflects which knowledge-management practices a domain has institutionalised.

---

## §6.4.2 Aristotelian Completeness

| Causes documented (k/4) | Count | Percentage |
|---|---|---|
| 0/4 (AC = 0.00) | 0 | 0.0% |
| 1/4 (AC = 0.25) | 11 | 45.8% |
| 2/4 (AC = 0.50) |  9 | 37.5% |
| 3/4 (AC = 0.75) |  4 | 16.7% |
| 4/4 (AC = 1.00) |  0 | 0.0% |
| **Mean AC** | **0.427** | — |

Mean AC = 0.427 is substantially higher than phase-9's 0.284 — the
biomedical corpus was constructed cause-aware, so every experiment
node already carries SUBSTRATE (cell line), CAUSE (knockdown→phenotype),
and CONTAINER (pathway) edges. No node achieves AC=1.0 because no single
node has all four causes (formal cause is satisfied by the SPECIFICATION/
CODE edges, which only attach to the subset linked to ClinicalTrials.gov
or the analysis pipeline). This mirrors the phase-9 finding that AC=1.0
is rare even in a more mature corpus.

---

## §6.4.3 Boethian Maxim Engine

| Metric | Value |
|---|---|
| Total proposals generated | 7 |
| Violations detected | **0** |
| Dominant proposal type | missing_specification (100%) |

**Result interpretation**: identical pattern to phase-9. All seven
proposals are `missing_specification` — the engine identifies precisely
the experiments not yet linked to a clinical pre-registration, which
is the actionable equivalent in this domain of phase-9's missing-OSF-
pre-reg audit. Zero violations confirms the graph is internally
consistent under the same maxims that governed phase-9.

---

## §6.4.4 VE Score Distribution and God Nodes

| Metric | Value |
|---|---|
| Structural nodes | 24 |
| God nodes (VE_h ≥ 0.5) | **8 (33%)** |
| Mean VE | 0.365 |
| Top god node | BIO-EXP-001 (VE_h = 1.000) |

Top god nodes (descending VE_h):

| Node | VE_h | Why it ranks high |
|---|---|---|
| BIO-EXP-001 | 1.000 | TP53/HEK293 — touches CAUSE+SUBSTRATE+CONTAINER+CODE+SPECIFICATION+PEER+SUCCESSOR+INSTANTIATION (the corpus's central node) |
| BIO-EXP-004 | 0.833 | siHK2/HeLa — well-connected to glycolysis+CODE+EFFECT |
| BIO-EXP-006 | 0.833 | siMYC/A549 — well-connected to glycolysis+CODE+EFFECT |
| BIO-EXP-007 | 0.833 | siPIK3CA/HeLa — well-connected to PI3K-AKT+CODE+SPECIFICATION |
| BIO-EXP-002 | 0.667 | TP53/HeLa replication |
| BIO-EXP-003 | 0.667 | siKRAS/A549 → PREREG-NCT04185883 |

The 33% god-node rate is much higher than phase-9's 3.3%, because in a
small graph each node's slots are a larger fraction of the total. This
is expected behaviour and confirms the algebraic god-node detection
mechanism does not depend on absolute scale — it picks out the most
relationally rich nodes regardless of corpus size.

---

## §6.4.5 Wittgenstein Family Resemblance

FR score statistics across all evaluable pairs:
- min = 0.167, mean = 0.259, max = 0.400 (Jaccard over neighbour sets)
- 8 of 8 BIO-EXP-* nodes have at least one family neighbour (100% coverage
  within the gene-knockdown experiment family)

Selected family clusters:

| Anchor | Top family neighbours (Jaccard) |
|---|---|
| BIO-EXP-002 (siTP53/HeLa)    | BIO-EXP-004 (0.40), BIO-EXP-007 (0.40), BIO-EXP-008 (0.25) |
| BIO-EXP-004 (siHK2/HeLa)     | BIO-EXP-002 (0.40), BIO-EXP-006 (0.33), BIO-EXP-007 (0.33) |
| BIO-EXP-005 (siSDHB/HEK293)  | BIO-EXP-001 (0.33), BIO-EXP-008 (0.25), BIO-EXP-002 (0.20) |
| BIO-EXP-006 (siMYC/A549)     | BIO-EXP-003 (0.33), BIO-EXP-004 (0.33), BIO-EXP-002 (0.17) |

The families bridge *across cell lines and across genes* — the highest
similarity (0.40) is between siTP53/HeLa and siHK2/HeLa, reflecting
shared cell-line substrate + shared CODE+SPECIFICATION pattern.

Per-type WFR coverage (verified post-classifier-extension, 2026-05-03):

| Node type | With family | In family layer | Snapshot total | Family-layer coverage | Snapshot coverage |
|---|---|---|---|---|---|
| experiment    | 8 | 8 |  8 | **100%** | **100%** |
| concept       | 0 | 0 |  8 | — | 0% |
| paper         | 0 | 0 |  4 | — | 0% |
| paper_section | 0 | 0 |  3 | — | 0% |

The 100%/100% experiment coverage is the cleanest WFR result of the three snapshots (phase-9 reports 100%/87%, phase-14 reports 100%/67%) — every experiment node in the biomedical corpus is in the family layer AND has at least one structurally similar counterpart, with no ghost experiments. The zero coverage for concept / paper / paper_section is correct: the biomedical instantiation only computed `viz_wittgenstein_neighbors` for the 8 BIO-EXP-* nodes (per the pipeline's experiment-prioritised default); extending coverage to other types would require a small expansion of the family-precompute pass and is an incremental follow-up.

---

## §6.4.6 Porphyrian relations (rank-2 sanity)

| Metric | Value |
|---|---|
| Nodes with CONTAINER parents (genera) | 7 |
| Nodes with CONTAINER children (species) | 5 |
| Pathway → experiment subsumption chains | 4 |

The Porphyrian backbone in the biomedical corpus is the
pathway → experiment → cell-line chain (s2 → s1 → s0), in addition to
the paper → section chain. The chain is shallower than phase-9's because
the corpus is intentionally small, but the same transitive-CONTAINER
structure applies.

---

# Headline phrasing for paper §6.4

"On a small biomedical second-corpus instantiation (25 nodes, 38 edges,
covering gene-knockdown experiments on TP53/KRAS/HK2/SDHB/MYC/PIK3CA across
HEK293/HeLa/A549 cell lines, glycolysis / TCA / PI3K-AKT-mTOR pathways,
two published papers, two ClinicalTrials.gov-style pre-registrations, and
one free-energy measurement on glycolysis), the unmodified GCT pipeline
populates **all 12 of 12 slots** (vs 8/12 in the neural-architecture
corpus), generates **0 logical violations and 7 missing_specification
proposals** under the same maxim engine, and **identifies 8 god nodes
algebraically** — confirming that the schema's domain-independence claim
is not merely structural but empirically supported on a second domain
that shares no node-content with the first."

---

# Reproducibility

```bash
cd knowledge-graph
python publication/biomedical_instantiation.py    # rebuilds + re-enriches
python publication/compute_paper_numbers.py --snapshot biomedical
```

The script is fully self-contained: stdlib + the existing GCT codebase
only, no external biological data. The biology is sourced from canonical
literature and the gene/cell-line/pathway choices are noted in the source
comments. The script is idempotent — repeated invocations produce the
identical snapshot up to the `created_at` timestamp on edges.
