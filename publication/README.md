# Tensegrity Knowledge Graph (GCT) — Reproducibility Package

This directory contains the complete submission package for the paper *"The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation"* (Zuluaga-Monroy & Zuluaga-Monroy, 2026).

It is intended to support independent reproduction of every empirical result in the paper, and to allow reviewers to install and query the GCT against the released corpus snapshot in under five minutes.

---

## What is the GCT?

A formally grounded, domain-agnostic knowledge graph architecture that synthesizes seven classical philosophical traditions:

| Tradition | Operationalisation in GCT |
|---|---|
| Fuller's IVM cuboctahedron | 12-slot semantic schema $\Sigma$ |
| Koestler's holons | 5 epistemological scales $s_0, \ldots, s_4$ |
| Aristotle's four causes | Edge-type vocabulary (formal / material / efficient / final) |
| Whitehead's process philosophy | Temporal evidential decay (6-week half-life) |
| Wittgenstein's family resemblance | Dual similarity metric (cosine + Jaccard) |
| Porphyry's tree | Taxonomic CONTAINER edges |
| Boethius's topical maxims | 12-rule inference engine (1 per slot) |

The system is defined formally as a typed directed multigraph $G = (N, E, \tau_N, \tau_E, \sigma, \lambda)$. See `PAPER_DRAFT.md` §3 for definitions, `gct_paper_main.tex` for the LaTeX submission source.

---

## Files in this directory

| File | Purpose |
|---|---|
| `PAPER_DRAFT.md` | Full paper draft (Markdown), ~8,200 words across 8 sections + frontmatter |
| `gct_paper_main.tex` | LaTeX source for IOS Press / Applied Ontology submission |
| `COVER_LETTER.md` | Submission cover letter draft (~480 words) |
| `empirical_evaluation.md` | Raw evaluation data tables (phase-9 snapshot, §5 anchor) |
| `biomedical_evaluation.md` | Second-corpus empirical evaluation (§6.4) |
| `compute_paper_numbers.py` | Reproducibility harness — `--snapshot {phase9,phase14,biomedical}` |
| `violation_ablation.py` | Synthetic-injection ablation harness (§5.2 defence) |
| `violation_ablation_report.md` | Ablation report — 11/11 detection rate verified |
| `biomedical_instantiation.py` | Build script for the §6.4 biomedical second-corpus snapshot |
| `gct.owl` | OWL 2 DL serialisation of the GCT schema (240 triples, BFO 2.0 mapping) |
| `gct_owl_README.md` | Companion to `gct.owl` — slot mapping table + worked example |
| `side_findings_resolution.md` | Resolution of two side findings flagged in earlier passes |
| `figs/fig_eval1_ac_distribution.png` | Aristotelian Completeness distribution (Fig. §5.1) |
| `figs/fig_eval2_slot_distribution.png` | IVM slot distribution (Fig. §5.3) |
| `figs/fig_eval3_ve_distribution.png` | VE score distribution + god nodes (Fig. §5.4) |
| `figs/fig_eval4_wfr_coverage.png` | Wittgenstein family resemblance coverage (Fig. §5.5) |
| `LICENSE-CODE.txt` | MIT license — applies to all Python source |
| `LICENSE-DATA.txt` | CC-BY 4.0 — applies to snapshots, paper, figures, OWL |
| `CITATION.cff` | GitHub-renderable citation file |
| `README.md` | This file |
| `SUBMISSION_PACKAGE.md` | Submission status + outstanding tasks + change log |

---

## Reproducing the empirical results

The paper anchors three independent snapshots:

| Section | Snapshot | SHA-256 | Headline |
|---|---|---|---|
| §5 (main evaluation) | `../tensegrity_graph_phase9_complete.json` | `dc7bf9d5…d1953739` | 1,660 nodes / 2,120 edges / 8 slots / 0 violations / 26 god nodes |
| §7.1 (extensibility demo) | `../tensegrity_graph_phase14_complete.json` | `fb5d4cae…caf1d216` | 2,067 / 3,282 / 10 slots / 67 CODE edges via `code_implements` |
| §6.4 (second corpus) | `../tensegrity_graph_biomedical.json` | `c0ff97e6…0954c368` | 25 / 38 / **12 slots** / 0 violations / 100% experiment WFR |

All three snapshots are self-contained JSON documents — no external services or databases are required.

### 30-second reproduction (single-command verification)

```bash
cd knowledge-graph/publication
python compute_paper_numbers.py                       # default: phase9 (paper §5)
python compute_paper_numbers.py --snapshot phase14    # extensibility demo (§7.1)
python compute_paper_numbers.py --snapshot biomedical # second corpus (§6.4)
```

Each invocation emits a Markdown report listing every numerical claim in the corresponding section, sourced directly from the SHA-pinned snapshot. Reviewers should run all three to verify §5, §6.4, and §7.1 independently.

### 5-minute defence verification

```bash
cd knowledge-graph/publication
python violation_ablation.py        # 11/11 maxim violations caught (§5.2 defence)
```

This script deep-copies the phase-9 snapshot, injects one synthetic violation per maxim slot, runs the maxim engine, and reports per-slot detection rate. Verifies the §5.2 zero-violations claim is not engine silence.

### Subcommand-level reproduction via `query_graph.py`

For fine-grained inspection, the snapshot is also queryable through `query_graph.py` directly (no pip dependencies, Python 3.10+ only):

```bash
cd knowledge-graph

python query_graph.py --graph tensegrity_graph_phase9_complete.json summary
# graph statistics; verify: 1660 nodes, 2120 edges

python query_graph.py --graph tensegrity_graph_phase9_complete.json maxims
# Boethian engine output; verify: 335 proposals, 0 violations

python query_graph.py --graph tensegrity_graph_phase9_complete.json god-nodes
# top VE nodes; verify: D-101c (0.833) at top

python query_graph.py --graph tensegrity_graph_phase9_complete.json incomplete
# nodes with low Aristotelian Completeness
```

Full subcommand list: `summary`, `god-nodes`, `orphans`, `overloaded`, `hot-frontiers`, `asymmetric`, `incomplete`, `by-scale`, `by-layer`, `by-type`, `find`, `show`, `neighbors`, `concept`, `experiment`, `paper`, `inversions`, `societies`, `delta`, `health`, `maxims`, `violations`, `infer`, `maxim-instances`, `family`, `family-clusters`, `porphyrian`, `siblings`, `prehension`, `boecian`. Run `python query_graph.py --help` for details.

### Regenerating the graph from primary sources

The graph is built from an append-only research log via a 12-extractor pipeline. To rebuild from scratch:

```bash
cd knowledge-graph
python core/build_graph.py --output tensegrity_graph_rebuild.json
python enrich_with_maxims.py tensegrity_graph_rebuild.json
```

The build is idempotent: repeated execution over an unchanged source produces a byte-identical snapshot.

---

## Reproducing the figures

The four §5 figures are generated by:

```bash
python .tools/python/gen_eval_figures.py
# Outputs to .tools/python/figs/ at 200 DPI, dark-navy palette
```

Figures use `matplotlib` only (no seaborn or plotly). Source: `.tools/python/gen_eval_figures.py`.

---

## MCP server interface

For interactive exploration, the snapshot is exposed through a local Model Context Protocol server with twenty typed query tools:

```bash
python knowledge-graph/mcp_server.py
# Auto-discovers the highest-phase snapshot in the directory
```

Query tool catalogue (see `mcp_server.py` for full schemas):

- **Structural:** `kg_find`, `kg_neighbors`, `kg_siblings`, `kg_show`
- **Philosophical:** `kg_porphyrian`, `kg_family_resemblance`, `kg_boecian`, `kg_prehension`
- **Diagnostic:** `kg_violations`, `kg_proposals`, `kg_god_nodes`, `kg_inversions`, `kg_health`
- **Typed retrieval:** `kg_experiment`, `kg_paper`, `kg_concept`, `kg_maxim_instances`
- **Aggregate:** `kg_summary`, `kg_societies`, `kg_family_clusters`

---

## Domain independence

The schema is domain-agnostic. To instantiate the GCT for a different research programme:

1. Define your node types $\Gamma$ (e.g., for biomedical: `experiment`, `pathway`, `clinical_trial`, ...)
2. Map your primary source documents to extractors that emit nodes typed by $\Gamma$ and edges typed by $\Sigma$
3. Apply the same `enrich_with_maxims.py` pipeline; the maxims are domain-independent

§6 of the paper walks through a worked biomedical instantiation with no schema modifications.

---

## Citing this work

```bibtex
@inproceedings{zuluaga2026gct,
  author    = {Zuluaga-Monroy, Juan David and Zuluaga-Monroy, Diego Fernando},
  title     = {The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation},
  booktitle = {Proceedings of FOIS 2026 / Applied Ontology},
  year      = {2026},
  publisher = {IOS Press},
  note      = {Code: https://github.com/expelius/gct-paper-fois2026 (GCT module)}
}
```

A Zenodo DOI for the corpus snapshot will be assigned upon paper acceptance.

---

## License

- **Code** (extractors, query layer, MCP server): MIT License
- **Corpus snapshot** (`tensegrity_graph_phase9_complete.json`): CC BY 4.0
- **Paper draft and figures**: CC BY 4.0

---

## Contact

Juan David Zuluaga-Monroy — `expelius@gmail.com`

For technical questions about the schema or extractor pipeline, please open an issue at `https://github.com/expelius/gct-paper-fois2026`.
