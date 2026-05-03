# Submission Playbook — Step by Step

Walk through this in order. Each step has a single concrete action.

---

## Phase 1 — Local git commit (5 min)

You'll commit two clusters: (a) the publication package, (b) the supporting code changes (new extractors + maxim fixes).

### 1.1 Stage the publication artifacts

```bash
cd "C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity"
git add knowledge-graph/publication/
git add knowledge-graph/tensegrity_graph_phase14_complete.json
git add knowledge-graph/tensegrity_graph_biomedical.json
```

### 1.2 Stage the supporting code

```bash
git add knowledge-graph/core/extractors/code_implements.py
git add knowledge-graph/core/extractors/epistemic_frontier.py
git add knowledge-graph/core/extractors/operational_distinctions.py
git add knowledge-graph/core/extractors/__init__.py
git add knowledge-graph/core/maxims.py
```

### 1.3 Commit with a clear message

```bash
git commit -m "Submission package for FOIS 2026 / Applied Ontology

- Complete paper draft (PAPER_DRAFT.md, gct_paper_main.tex, ~8,200 words)
- Three reproducible snapshots (phase9 frozen / phase14 extensibility / biomedical second-corpus)
- Single-script reproducibility harness (compute_paper_numbers.py)
- Synthetic-injection ablation harness (violation_ablation.py, 11/11 detection rate)
- OWL serialisation aligned with BFO 2.0 (gct.owl, 240 triples, OWL 2 DL)
- Cover letter, CITATION.cff, LICENSE-CODE (MIT) + LICENSE-DATA (CC-BY 4.0)
- Maxim engine fixes: PREDECESSOR + SUCCESSOR ISO datetime parsing + tie-breaker
- New extractors: code_implements (CODE slot), epistemic_frontier, operational_distinctions"
```

---

## Phase 2 — Get the IOS Press LaTeX class file (10 min, gated by IOS Press)

`gct_paper_main.tex` declares `\documentclass{iosart2x}`. The class file is gated by IOS Press. Pick whichever is fastest:

### Option A — Overleaf (recommended, fastest)

1. Go to https://www.overleaf.com/latex/templates/template-for-ios-press-manuscripts/qqqgfzdmtpkn
2. Click **"Open as Template"** (creates a new Overleaf project)
3. Top-right menu → **Menu → Source → Download as zip**
4. Extract the zip; copy `iosart2x.cls` and `iosart2x.cfg` into `knowledge-graph/publication/`

### Option B — IOS Press submissions portal

1. Go to https://www.submissions.iospress.com/applied-ontology
2. Create author account (free) → "Submission Guidelines" → download LaTeX template package

### Option C — Email request

Email `editorial@iospress.nl` requesting the Applied Ontology LaTeX template; typically 24–48h turnaround.

---

## Phase 3 — Compile the IOS Press PDF (2 min, after Phase 2)

```bash
export PATH="$PATH:/c/Users/juand/AppData/Local/Programs/MiKTeX/miktex/bin/x64"
cd "C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity/knowledge-graph/publication"
pdflatex gct_paper_main.tex   # first pass — resolves citations
pdflatex gct_paper_main.tex   # second pass — fills cross-references
```

Verify the PDF visually:
- Author block + title
- Double-column layout (IOS Press standard)
- All 4 figures render at the correct size
- All 4 tables render
- References render with DOIs + hyperlinks
- Page count: should be ~12–14 pages in double-column (vs 17 in our single-column fallback)

---

## Phase 4 — GitHub release (5 min)

You need to be logged in to `gh` first:

```bash
gh auth login   # follow the browser prompt
```

Then push the tag:

```bash
cd "C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity"
git push origin main
git tag -a gct-paper-v1 -m "GCT paper submission to FOIS 2026 / Applied Ontology

Reproducibility package frozen at this tag.
Snapshot SHAs:
- phase9:     dc7bf9d51f3e42b8...94269c57d1953739
- phase14:    fb5d4cae...caf1d216
- biomedical: c0ff97e6...0954c368"
git push origin gct-paper-v1
```

If you don't have a remote named `origin` pointing to the public mirror, set it:
```bash
git remote add origin https://github.com/expelius/gct-paper-fois2026.git
```

---

## Phase 5 — Zenodo DOI (5 min)

One-time setup (if not done):
1. Go to https://zenodo.org/account/settings/github/
2. Log in via GitHub OAuth
3. Toggle **ON** the `expelius/gct-paper-fois2026` repository

Then publish the release:
1. On GitHub, go to https://github.com/expelius/gct-paper-fois2026/releases
2. Click **"Draft a new release"**
3. Tag: `gct-paper-v1` (already pushed in Phase 4)
4. Title: "GCT Paper v1 — FOIS 2026 / Applied Ontology submission"
5. Description: paste relevant excerpt from `SUBMISSION_PACKAGE.md`
6. **Publish release** → Zenodo will detect it within ~30 seconds and mint a DOI
7. Copy the DOI from the Zenodo dashboard

Update local files with the new DOI:
```bash
# Edit CITATION.cff line 35: replace `version: gct-paper-v1` with the Zenodo DOI
# Add the DOI to the Acknowledgements section of PAPER_DRAFT.md and gct_paper_main.tex
```

---

## Phase 6 — Submit to Applied Ontology (10 min)

1. Go to https://www.submissions.iospress.com/applied-ontology
2. **Submit New Manuscript**
3. Upload:
   - **Main file:** `gct_paper_main.pdf` (compiled in Phase 3)
   - **Source file:** `gct_paper_main.tex` (the LaTeX source)
   - **Cover letter:** `COVER_LETTER.md` content (paste into the cover letter field)
   - **Supplementary materials:** zip of `publication/` directory if the portal accepts it
4. Fill in metadata:
   - **Title:** *The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation*
   - **Authors:** Juan David Zuluaga-Monroy (corresponding) + Diego Fernando Zuluaga-Monroy
   - **Keywords:** copy from the abstract
   - **Subject area:** Knowledge Representation / Formal Ontology
   - **Conflict of interest:** none
   - **Funding:** none specific (independent research)
   - **Data and code availability:** link to the GitHub release + Zenodo DOI
5. Suggest reviewers (optional but speeds up triage):
   - Anyone in the BFO community (Barry Smith, Stefano Borgo, …)
   - Authors of the closest works cited (Bai, Beygi Nasrabadi, Ebrahimi)
6. **Submit**

---

## Post-submission

You should receive:
- Confirmation email within minutes
- Editor assignment within ~1 week
- First reviews within 6–10 weeks

While waiting:
- Don't modify the public release tag; if you find errors, prepare a v1.1 tag for the revision round
- Keep the dispatch log running — accumulating telemetry helps the next paper
- Consider preparing a 1-page poster summary for FOIS in case the conference accepts it

---

## Troubleshooting

**`iosart2x.cls` not found after Phase 2**  → confirm both `.cls` AND `.cfg` files are in the same directory as `gct_paper_main.tex`

**`pdflatex` hangs on first run**  → run `initexmf --set-config-value "[MPM]AutoInstall=1"` (already done on this machine)

**Bibliography page is blank**  → run `pdflatex` twice (first pass writes the `.aux`, second pass reads it)

**Figures not rendering**  → confirm `figs/` directory is alongside `gct_paper_main.tex`

**`gh auth login` fails**  → use `gh auth login --web` and follow the browser prompt
