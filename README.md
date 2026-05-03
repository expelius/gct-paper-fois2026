# Tensegrity Knowledge Graph (GCT) — FOIS 2026 / Applied Ontology submission

This repository is the public reproducibility package for the paper:

> **The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation**
> Juan David Zuluaga-Monroy, Diego Fernando Zuluaga-Monroy.
> Submitted to *Applied Ontology* (IOS Press) / FOIS 2026.

The paper synthesises seven classical philosophical traditions — Fuller's IVM cuboctahedron, Koestler's holons, Aristotle's four causes, Whitehead's process philosophy, Wittgenstein's family resemblance, Porphyry's tree, and Boethius's topical maxims — into a single, formally grounded knowledge representation architecture.

---

## What's in this repository

| Path | Contents |
|---|---|
| `publication/` | Paper draft (Markdown + LaTeX), figures, cover letter, all reproducibility scripts and reports, OWL serialisation, change log |
| `tensegrity_graph_phase9_complete.json` | **Frozen reference snapshot** for §5 of the paper (1,660 nodes / 2,120 edges, SHA-256 `dc7bf9d5…d1953739`) |
| `tensegrity_graph_phase14_complete.json` | Companion snapshot for §7.1 schema-extensibility demo (CODE slot closed by `code_implements` extractor) |
| `tensegrity_graph_biomedical.json` | Second-corpus snapshot for §6.4 (25 nodes, 12/12 slots populated, 0 violations) |
| `core/` | The GCT framework code (extractor pipeline, schema, maxim engine, search algorithms) — used by reproducibility scripts and to rebuild the snapshots |
| `enrich_with_maxims.py` | Post-build enrichment script (maxims layer + viz layer + manual edge patch) |
| `query_graph.py` | Read-only CLI query interface to any snapshot (30 subcommands) |

---

## 30-second reproduction

The single-command verification of every numerical claim in §5 of the paper:

```bash
cd publication
python compute_paper_numbers.py                       # default: phase-9 (paper §5)
python compute_paper_numbers.py --snapshot phase14    # extensibility demo (§7.1)
python compute_paper_numbers.py --snapshot biomedical # second corpus (§6.4)
```

No pip dependencies (Python 3.10+ stdlib only). Each invocation reads the SHA-pinned snapshot and emits a Markdown report listing every claim from the corresponding paper section.

## 5-minute defence verification

```bash
cd publication
python violation_ablation.py        # 11/11 maxim detection rate (§5.2)
python superseded_retraction.py     # SUPERSEDED defeasibility-lite (§5.7)
python cardinality_ablation.py      # 12-slot vs 4-slot ablation (§7.3 L1)
```

---

## Repository structure detail

```
.
├── README.md                                 # this file
├── LICENSE-CODE.txt                          # MIT (all Python source)
├── LICENSE-DATA.txt                          # CC-BY 4.0 (snapshots, paper, figures, OWL)
├── CITATION.cff                              # GitHub-renderable citation
├── tensegrity_graph_phase9_complete.json     # frozen §5 reference (4.6 MB)
├── tensegrity_graph_phase14_complete.json    # §7.1 extensibility demo (6.5 MB)
├── tensegrity_graph_biomedical.json          # §6.4 second corpus (84 KB)
├── enrich_with_maxims.py                     # post-build enrichment
├── query_graph.py                            # CLI query interface
├── core/                                     # GCT framework
│   ├── builder.py
│   ├── schema.py
│   ├── maxims.py
│   ├── extractors/                           # 14 extractors in topological order
│   └── ...
└── publication/
    ├── PAPER_DRAFT.md                        # full paper (Markdown, ~8,900 words)
    ├── gct_paper_main.tex                    # LaTeX source (IOS Press iosart2x)
    ├── PAPER_DRAFT_preview.pdf               # reportlab preview (619 KB)
    ├── COVER_LETTER.md                       # submission cover letter
    ├── README.md                             # reviewer-facing detail
    ├── SUBMISSION_PACKAGE.md                 # change log + status table
    ├── SUBMISSION_PLAYBOOK.md                # step-by-step submission process
    ├── empirical_evaluation.md               # §5 verified numbers (phase9)
    ├── biomedical_evaluation.md              # §6.4 verified numbers (biomedical)
    ├── violation_ablation_report.md          # 11/11 maxim detection report
    ├── superseded_retraction_report.md       # SUPERSEDED retraction analysis
    ├── cardinality_ablation_report.md        # 12-slot vs 4-slot ablation
    ├── side_findings_resolution.md           # earlier code repair log
    ├── compute_paper_numbers.py              # single-script reproducibility
    ├── violation_ablation.py                 # synthetic-injection harness
    ├── biomedical_instantiation.py           # rebuilds biomedical snapshot
    ├── cardinality_ablation.py               # 12 → 4 slot collapse
    ├── superseded_retraction.py              # defeasibility-lite analysis
    ├── gct.owl                               # OWL 2 DL serialisation (240 triples)
    ├── gct_owl_README.md                     # OWL companion (mapping + worked example)
    └── figs/                                 # 4 figures at 200 DPI
```

---

## Citing

A Zenodo DOI will be assigned upon paper acceptance. Until then, please cite the GitHub release:

```bibtex
@inproceedings{zuluaga2026gct,
  author    = {Zuluaga-Monroy, Juan David and Zuluaga-Monroy, Diego Fernando},
  title     = {The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation},
  booktitle = {Proceedings of FOIS 2026 / Applied Ontology},
  year      = {2026},
  publisher = {IOS Press},
  note      = {Reproducibility package: https://github.com/expelius/gct-paper-fois2026 (release \texttt{gct-paper-v1})}
}
```

`CITATION.cff` provides the GitHub-renderable equivalent.

---

## Licensing

- **Code** (all Python files): MIT — see `LICENSE-CODE.txt`
- **Data, paper, figures, OWL**: CC-BY 4.0 — see `LICENSE-DATA.txt`

---

## Authors

- **Juan David Zuluaga-Monroy** (corresponding) — `expelius@gmail.com`
- **Diego Fernando Zuluaga-Monroy** — `diferzu@gmail.com`

Independent Research Group, Colombia.

---

## Issues and feedback

Open an issue on this repository. We respond within ~48 hours.
