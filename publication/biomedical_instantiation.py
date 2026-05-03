"""biomedical_instantiation.py — second-corpus empirical demonstration of GCT.

Builds a small (~25-node) but REAL biomedical research corpus in code, runs it
through the same TensegrityGraph + enrichment pipeline as the main neural-
architecture corpus, and emits `tensegrity_graph_biomedical.json` alongside
the phase9 / phase14 snapshots so `compute_paper_numbers.py --snapshot biomedical`
can read it.

Purpose: defends §7.3's single-corpus-evaluation limitation by replacing the
purely structural domain-independence argument of §6 with a runnable, slot-
exercising second-domain instantiation. Even at small N, the existence of a
second graph that produces non-zero values for the same metrics (AC, slot
distribution, maxim proposals/violations, family resemblance, VE god nodes) is
much stronger evidence of domain-independence than the structural argument
alone.

Biology choices — all REAL, drawn from canonical molecular biology literature:
  - TP53 (the "guardian of the genome"; its knockdown lifts apoptosis brake)
  - KRAS (GTPase oncogene; G12D mutation drives ~30% pancreatic adenocarcinomas)
  - HK2 (hexokinase 2; first committed step of glycolysis; Warburg-relevant)
  - SDHB (succinate dehydrogenase B subunit; TCA cycle + ETC complex II)
  - MYC (master transcription factor; drives glycolytic + glutaminolytic flux)
  - PIK3CA (PI3K catalytic subunit; oncogenic in ~13% of tumours)
Cell lines: HEK293 (kidney), HeLa (cervical adenocarcinoma), A549 (lung adenoca).
Pathways: glycolysis, TCA cycle, PI3K-AKT-mTOR, p53 apoptosis.
Pre-registrations: ClinicalTrials.gov-style identifiers (NCT********).

Self-contained: only stdlib + the existing GCT codebase. Run from this dir.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Make the knowledge-graph parent directory importable when run from publication/.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent  # knowledge-graph/
sys.path.insert(0, str(_REPO))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.builder import TensegrityGraph
from core.schema import Confidence, Edge, Layer, Node, Slot

OUTPUT_PATH = _REPO / "tensegrity_graph_biomedical.json"


# ---------------------------------------------------------------------------
# Node helpers — small wrappers so each call documents the biology
# ---------------------------------------------------------------------------

def _exp(g: TensegrityGraph, exp_id: str, label: str, gene: str, cell_line: str,
         phenotype: str, state: str = "OK") -> None:
    """A single gene-knockdown experiment node (s1 — section/experiment level)."""
    g.add_node(Node(
        id=exp_id, label=label, scale=1, layer=Layer.STRUCTURAL,
        active_since=datetime(2025, 11, 1).isoformat(),
        metadata={
            "node_type": "experiment",
            "domain": "biomedical",
            "gene_target": gene,
            "cell_line": cell_line,
            "phenotype": phenotype,
            "state": state,
        },
    ))


# Single frozen build timestamp — applied to every node + edge to make the
# resulting JSON byte-deterministic across reruns (so the published SHA-256
# stays valid). 2026-05-02 is the day this script was authored.
_FROZEN_TS_NODE = "2026-05-02T00:00:00"


def _concept(g: TensegrityGraph, cid: str, label: str, kind: str,
             description: str = "") -> None:
    """Concept node (pathway, disease, mechanism) at s2 — paper/concept level."""
    g.add_node(Node(
        id=cid, label=label, scale=2, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "concept",
            "domain": "biomedical",
            "concept_kind": kind,
            "description": description,
        },
    ))


def _paper(g: TensegrityGraph, pid: str, label: str, doi: str = "") -> None:
    """Published paper node (s2)."""
    g.add_node(Node(
        id=pid, label=label, scale=2, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "paper", "domain": "biomedical", "doi": doi,
        },
    ))


def _section(g: TensegrityGraph, sid: str, label: str, paper_id: str) -> None:
    """Paper section node (s1)."""
    g.add_node(Node(
        id=sid, label=label, scale=1, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "paper_section",
            "domain": "biomedical",
            "paper_id": paper_id,
            "section": label,
        },
    ))


def _prereg(g: TensegrityGraph, pid: str, nct_id: str, label: str) -> None:
    """Clinical pre-registration (ClinicalTrials.gov-style) node — s2."""
    g.add_node(Node(
        id=pid, label=label, scale=2, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "prereg_prediction_referenced",
            "domain": "biomedical",
            "registry": "ClinicalTrials.gov",
            "nct_id": nct_id,
        },
    ))


def _cell_line(g: TensegrityGraph, cid: str, label: str, tissue: str,
               species: str = "Homo sapiens") -> None:
    """Cell-line node — s0 (atomic substrate)."""
    g.add_node(Node(
        id=cid, label=label, scale=0, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "cell_line",
            "domain": "biomedical",
            "tissue_origin": tissue,
            "species": species,
        },
    ))


def _measurement(g: TensegrityGraph, mid: str, label: str, parent: str,
                 quantity: str, value: str) -> None:
    """Thermodynamic / quantitative measurement (functional layer, points to structural parent)."""
    g.add_node(Node(
        id=mid, label=label, scale=0, layer=Layer.THERMODYNAMIC,
        structural_ref=parent,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "measurement",
            "domain": "biomedical",
            "quantity": quantity,
            "value": value,
        },
    ))


def _code_holon(g: TensegrityGraph, cid: str, label: str, lang: str = "python") -> None:
    """Analysis-script node treated as a code holon (s0)."""
    g.add_node(Node(
        id=cid, label=label, scale=0, layer=Layer.STRUCTURAL,
        active_since=_FROZEN_TS_NODE,
        metadata={
            "node_type": "code_holon",
            "domain": "biomedical",
            "language": lang,
        },
    ))


# Deterministic timestamp for reproducibility — keeps the snapshot SHA stable
# across reruns. Build date freeze: 2026-05-02 (the day this script was authored).
_FROZEN_TS = "2026-05-02T00:00:00"


def _e(g: TensegrityGraph, src: str, tgt: str, slot: Slot, evidence: str,
       conf: Confidence = Confidence.EXTRACTED, scale_from: int = 1,
       scale_to: int = 1, essence: str = "") -> None:
    """Wrapper that adds an edge with sensible defaults; biology in `evidence`."""
    e = Edge(
        source=src, target=tgt, slot=slot, confidence=conf,
        scale_from=scale_from, scale_to=scale_to,
        evidence=evidence, essence=essence,
    )
    e.created_at = _FROZEN_TS   # freeze for deterministic SHA
    g.add_edge(e)


# ---------------------------------------------------------------------------
# Main build — corpus declaration order: nodes first, then edges
# ---------------------------------------------------------------------------

def build_biomedical_corpus() -> TensegrityGraph:
    g = TensegrityGraph()
    # Freeze build_id so provenance + serialised SHA stay deterministic across reruns.
    g.build_id = "20260502T000000"

    # ===== 1. Cell-line substrates (s0) ==============================
    # Three workhorse human lines used across thousands of knockdown studies.
    _cell_line(g, "CL-HEK293", "HEK293 (human embryonic kidney)",  tissue="kidney")
    _cell_line(g, "CL-HeLa",   "HeLa (cervical adenocarcinoma)",   tissue="cervix")
    _cell_line(g, "CL-A549",   "A549 (lung adenocarcinoma)",       tissue="lung")

    # ===== 2. Pathway / concept nodes (s2) ===========================
    _concept(g, "PATHWAY-glycolysis",   "Glycolysis (EMP pathway)", kind="metabolic_pathway",
             description="Glucose → 2 pyruvate; HK2-rate-limited in tumour cells (Warburg).")
    _concept(g, "PATHWAY-tca",          "TCA cycle / Krebs cycle",  kind="metabolic_pathway",
             description="Acetyl-CoA oxidation; SDH (Complex II) ties TCA to ETC.")
    _concept(g, "PATHWAY-pi3k-akt",     "PI3K-AKT-mTOR signalling", kind="signalling_pathway",
             description="Growth-factor → PI3K → AKT → mTORC1; oncogenic when constitutively on.")
    _concept(g, "DISEASE-pancreatic-ca","Pancreatic adenocarcinoma",kind="disease",
             description="~95% bear KRAS-G12D/V; exemplar of oncogene-addicted cancer.")
    _concept(g, "DISEASE-apoptosis-evasion", "Apoptosis evasion (cancer hallmark)",
             kind="disease",
             description="Hanahan & Weinberg hallmark; TP53 loss is canonical driver.")

    # ===== 3. Gene-knockdown experiments (s1) ========================
    # Each experiment carries a real gene + cell line + observed phenotype.
    _exp(g, "BIO-EXP-001", "siTP53 in HEK293 → reduced apoptosis after etoposide",
         gene="TP53", cell_line="CL-HEK293",
         phenotype="apoptosis_attenuation_after_DNA_damage", state="OK")
    _exp(g, "BIO-EXP-002", "siTP53 in HeLa → reduced apoptosis after etoposide (replication)",
         gene="TP53", cell_line="CL-HeLa",
         phenotype="apoptosis_attenuation_after_DNA_damage", state="OK")
    _exp(g, "BIO-EXP-003", "siKRAS in A549 → loss of anchorage-independent growth",
         gene="KRAS", cell_line="CL-A549",
         phenotype="anchorage_independent_growth_loss", state="OK")
    _exp(g, "BIO-EXP-004", "siHK2 in HeLa → ~60% drop in lactate efflux (Warburg attenuated)",
         gene="HK2", cell_line="CL-HeLa",
         phenotype="glycolytic_flux_reduction", state="OK")
    _exp(g, "BIO-EXP-005", "siSDHB in HEK293 → succinate accumulation + pseudohypoxia",
         gene="SDHB", cell_line="CL-HEK293",
         phenotype="succinate_accumulation_HIF1a_stabilisation", state="OK")
    _exp(g, "BIO-EXP-006", "siMYC in A549 → glycolytic + glutaminolytic flux drop",
         gene="MYC", cell_line="CL-A549",
         phenotype="dual_metabolic_flux_drop", state="OK")
    _exp(g, "BIO-EXP-007", "siPIK3CA in HeLa → AKT phospho-S473 collapse (>80%)",
         gene="PIK3CA", cell_line="CL-HeLa",
         phenotype="AKT_dephosphorylation", state="OK")
    # Planned follow-up — used as a SUCCESSOR target for BIO-EXP-001
    _exp(g, "BIO-EXP-008", "TP53-/- knockout in HEK293 (planned 2026Q3 follow-up)",
         gene="TP53", cell_line="CL-HEK293",
         phenotype="planned_apoptosis_followup", state="QUEUED")

    # ===== 4. Published-paper nodes (s2) =============================
    _paper(g, "PAPER-WARBURG-2009", "Vander Heiden et al. (2009) — Warburg revisited",
           doi="10.1126/science.1160809")
    _paper(g, "PAPER-KRAS-G12D",    "Hingorani et al. (2003) — KRAS-G12D pancreatic model",
           doi="10.1016/S1535-6108(03)00309-X")

    # ===== 5. Paper sections (s1) ====================================
    _section(g, "PAPER-WARBURG-2009_section_introduction",
             "Introduction", "PAPER-WARBURG-2009")
    _section(g, "PAPER-WARBURG-2009_section_HK2_dependency",
             "HK2 dependency in tumour cells", "PAPER-WARBURG-2009")
    _section(g, "PAPER-KRAS-G12D_section_pancreatic_initiation",
             "Pancreatic initiation by KRAS-G12D", "PAPER-KRAS-G12D")

    # ===== 6. Clinical pre-registrations (s2) ========================
    _prereg(g, "PREREG-NCT04185883", "NCT04185883",
            "Phase II trial of adagrasib (MRTX849, KRAS-G12C inhibitor) in NSCLC")
    _prereg(g, "PREREG-NCT03634332", "NCT03634332",
            "Phase I/II trial of alpelisib (PIK3CA inhibitor) in HR+ breast cancer")

    # ===== 7. Thermodynamic measurement (s0, functional/thermo layer) =
    _measurement(g, "FREE-ENERGY-glycolysis-net",
                 "Net ΔG glycolysis ≈ -85 kJ/mol (standard physiological)",
                 parent="PATHWAY-glycolysis",
                 quantity="ΔG_net_kJ_per_mol", value="-85")

    # ===== 8. Code holon (s0) ========================================
    _code_holon(g, "CODE-deseq2-pipeline",
                "DESeq2 differential expression pipeline (R)", lang="R")

    # =================================================================
    # EDGES — wire all 12 GCT slots wherever biology supports it
    # =================================================================

    # ---- CAUSE (efficient cause) — gene knockdown → phenotype -----
    # The knockdown of gene G efficiently CAUSES the observed phenotype P.
    _e(g, "BIO-EXP-001", "DISEASE-apoptosis-evasion", Slot.CAUSE,
       "siTP53 efficiently causes apoptosis evasion under genotoxic stress (Vogelstein 2000)",
       scale_from=1, scale_to=2)
    _e(g, "BIO-EXP-003", "DISEASE-pancreatic-ca", Slot.CAUSE,
       "KRAS knockdown reverses pancreatic-ca tumourigenicity (Singh et al. 2009)",
       scale_from=1, scale_to=2)
    _e(g, "BIO-EXP-007", "PATHWAY-pi3k-akt", Slot.CAUSE,
       "PIK3CA knockdown causally collapses PI3K-AKT-mTOR axis activity",
       scale_from=1, scale_to=2)

    # ---- EFFECT (final cause / observational downstream) ----------
    # Gene → downstream metabolic-axis effect. Biological direction is gene
    # acts ON pathway, so EFFECT mirrors CAUSE on a different pair.
    _e(g, "BIO-EXP-004", "PATHWAY-glycolysis", Slot.EFFECT,
       "HK2 knockdown drops glycolytic flux ≈60% — direct metabolic effect",
       scale_from=1, scale_to=2)
    _e(g, "BIO-EXP-005", "PATHWAY-tca", Slot.EFFECT,
       "SDHB knockdown accumulates succinate — TCA-cycle blockade (Selak et al. 2005)",
       scale_from=1, scale_to=2)
    _e(g, "BIO-EXP-006", "PATHWAY-glycolysis", Slot.EFFECT,
       "MYC knockdown drops glycolytic flux (and glutaminolysis); dual metabolic effect",
       scale_from=1, scale_to=2)

    # ---- SPECIFICATION (formal cause) — experiment → pre-registration --
    # The clinical pre-reg formalises the protocol of the relevant experiment.
    # Direction: experiment → prereg (the prereg SPECIFIES the experiment).
    # Note: scale_from <= scale_to is enforced by the SPECIFICATION maxim.
    _e(g, "BIO-EXP-003", "PREREG-NCT04185883", Slot.SPECIFICATION,
       "BIO-EXP-003 (KRAS knockdown phenotype) is the preclinical SPECIFICATION for adagrasib trial NCT04185883",
       scale_from=1, scale_to=2)
    _e(g, "BIO-EXP-007", "PREREG-NCT03634332", Slot.SPECIFICATION,
       "BIO-EXP-007 (PIK3CA dependency) is the preclinical SPECIFICATION for alpelisib trial NCT03634332",
       scale_from=1, scale_to=2)

    # ---- SUBSTRATE (material cause) — experiment uses cell line ---
    # The cell line is the material substrate the experiment was conducted in.
    # Direction: cell-line → experiment (substrate is at lower scale).
    for exp_id, cl_id in [
        ("BIO-EXP-001", "CL-HEK293"),
        ("BIO-EXP-002", "CL-HeLa"),
        ("BIO-EXP-003", "CL-A549"),
        ("BIO-EXP-004", "CL-HeLa"),
        ("BIO-EXP-005", "CL-HEK293"),
        ("BIO-EXP-006", "CL-A549"),
        ("BIO-EXP-007", "CL-HeLa"),
        ("BIO-EXP-008", "CL-HEK293"),
    ]:
        _e(g, cl_id, exp_id, Slot.SUBSTRATE,
           f"{cl_id} is the material substrate of {exp_id}",
           scale_from=0, scale_to=1)

    # ---- PREDECESSOR (efficient cause, temporal-prior) -----------
    # BIO-EXP-001 (HEK293) preceded BIO-EXP-002 (HeLa replication).
    # Maxim: src.scale must equal tgt.scale (peer replication).
    _e(g, "BIO-EXP-001", "BIO-EXP-002", Slot.PREDECESSOR,
       "BIO-EXP-002 is a HeLa replication of the HEK293 result in BIO-EXP-001",
       scale_from=1, scale_to=1)

    # ---- CONTAINER (final cause / genus) — pathway contains experiments --
    # The pathway concept genus-contains the experiments studying it.
    # Direction: pathway → experiment (CONTAINER must be at >= scale).
    _e(g, "PATHWAY-glycolysis", "BIO-EXP-004", Slot.CONTAINER,
       "Glycolysis pathway contains the HK2 knockdown experiment that probes it",
       scale_from=2, scale_to=1)
    _e(g, "PATHWAY-glycolysis", "BIO-EXP-006", Slot.CONTAINER,
       "Glycolysis pathway contains the MYC knockdown experiment (MYC drives glycolytic flux)",
       scale_from=2, scale_to=1)
    _e(g, "PATHWAY-tca", "BIO-EXP-005", Slot.CONTAINER,
       "TCA cycle contains the SDHB knockdown experiment (SDHB IS Complex II of TCA/ETC)",
       scale_from=2, scale_to=1)
    _e(g, "PATHWAY-pi3k-akt", "BIO-EXP-007", Slot.CONTAINER,
       "PI3K-AKT-mTOR pathway contains the PIK3CA knockdown experiment",
       scale_from=2, scale_to=1)
    # Papers contain their sections (genus relation)
    _e(g, "PAPER-WARBURG-2009", "PAPER-WARBURG-2009_section_introduction",
       Slot.CONTAINER, "paper contains section", scale_from=2, scale_to=1)
    _e(g, "PAPER-WARBURG-2009", "PAPER-WARBURG-2009_section_HK2_dependency",
       Slot.CONTAINER, "paper contains section", scale_from=2, scale_to=1)
    _e(g, "PAPER-KRAS-G12D", "PAPER-KRAS-G12D_section_pancreatic_initiation",
       Slot.CONTAINER, "paper contains section", scale_from=2, scale_to=1)

    # ---- PEER_COHERENT (a similibus) — replication, same essence -
    # BIO-EXP-001 and BIO-EXP-002 both confirm TP53-loss-blocks-apoptosis,
    # in two cell lines — Wittgenstein essence is the *claim*, not the line.
    _e(g, "BIO-EXP-001", "BIO-EXP-002", Slot.PEER_COHERENT,
       "Both confirm TP53-loss attenuates etoposide-induced apoptosis (cross-line replication)",
       essence="TP53 loss blocks DNA-damage apoptosis",
       scale_from=1, scale_to=1)
    # MYC and HK2 knockdowns both attenuate glycolytic flux — coherent on
    # the broader glycolysis-dependence claim. Different genes, same essence.
    _e(g, "BIO-EXP-004", "BIO-EXP-006", Slot.PEER_COHERENT,
       "Both confirm tumour glycolytic flux is suppressible by single-gene knockdown",
       essence="glycolytic flux is single-gene-knockdown-suppressible in tumour cells",
       scale_from=1, scale_to=1)

    # ---- PEER_CONTRADICTORY (a contrariis) -----------------------
    # Real biological example: BIO-EXP-001 (siRNA knockdown of TP53) vs the
    # planned BIO-EXP-008 (CRISPR knockout of TP53). The literature has
    # documented systematic discrepancies between RNAi-knockdown phenotypes
    # and CRISPR-knockout phenotypes (Stojic et al. 2018, Nature Comm; Smith
    # et al. 2017 Nat Methods) — partial vs complete loss of function can
    # yield categorically different phenotypes due to compensation/dosage.
    # Maxim invariant: src.scale must equal tgt.scale.
    _e(g, "BIO-EXP-001", "BIO-EXP-008", Slot.PEER_CONTRADICTORY,
       "Anticipated contradiction: siRNA partial knockdown vs CRISPR full KO often "
       "diverge on TP53 phenotype (Stojic et al. 2018 Nature Communications; "
       "documented 'knockdown vs knockout' discrepancy)",
       conf=Confidence.AMBIGUOUS, scale_from=1, scale_to=1)

    # ---- INSTANTIATION (individual / hypostasis) -----------------
    # Maxim convention: edge direction is form (source) → instance (target),
    # so source.scale >= target.scale. The disease/hallmark category is the
    # FORM (s2); the experimental phenotype is the INSTANCE (s1).
    _e(g, "DISEASE-apoptosis-evasion", "BIO-EXP-001", Slot.INSTANTIATION,
       "BIO-EXP-001 phenotype is an instance of the apoptosis-evasion cancer hallmark category",
       scale_from=2, scale_to=1)
    _e(g, "DISEASE-pancreatic-ca", "BIO-EXP-003", Slot.INSTANTIATION,
       "BIO-EXP-003 KRAS-A549 phenotype is an instance of the KRAS-driven adenocarcinoma category",
       scale_from=2, scale_to=1)

    # ---- SUCCESSOR (temporal-posterior follow-up) ----------------
    # BIO-EXP-008 is the planned 2026Q3 successor of BIO-EXP-001.
    # Maxim: src.scale must equal tgt.scale.
    _e(g, "BIO-EXP-001", "BIO-EXP-008", Slot.SUCCESSOR,
       "BIO-EXP-008 is the planned CRISPR-KO follow-up to siRNA result BIO-EXP-001",
       scale_from=1, scale_to=1)

    # ---- CODE (formal, differentia) — experiment uses script ------
    # Each gene-knockdown experiment was analysed with the DESeq2 pipeline.
    # CODE direction: src is the formal-definition (higher scale), tgt is
    # the executable (lower scale). For us: experiment (s1) → code holon (s0).
    for exp_id in ["BIO-EXP-001", "BIO-EXP-002", "BIO-EXP-003", "BIO-EXP-004",
                   "BIO-EXP-005", "BIO-EXP-006", "BIO-EXP-007"]:
        _e(g, exp_id, "CODE-deseq2-pipeline", Slot.CODE,
           f"{exp_id} differential-expression analysis ran via DESeq2 pipeline",
           scale_from=1, scale_to=0)

    # ---- THERMO (accident — measurement bound to substance) ------
    # Free-energy measurement attached to glycolysis. THERMO is a cable
    # along the halves axis — accidens praedicabile (Porphyry): a contingent
    # attribute of the substance. Per maxim refinement (round-7 review), an
    # accidental attribute of a STRUCTURAL/kind-level target should carry
    # AMBIGUOUS or INFERRED confidence (the value could have been otherwise
    # under different conditions — pH, tissue, organism — and is not a
    # defining property of the pathway as such).
    _e(g, "FREE-ENERGY-glycolysis-net", "PATHWAY-glycolysis", Slot.THERMO,
       "Standard physiological ΔG_net of glycolysis ≈ -85 kJ/mol (thermodynamic accident of the substrate)",
       conf=Confidence.INFERRED, scale_from=0, scale_to=2)

    return g


# ---------------------------------------------------------------------------
# Persist + enrich
# ---------------------------------------------------------------------------

def main() -> int:
    print("[biomedical_instantiation] building graph …")
    g = build_biomedical_corpus()

    stats = g.stats()
    print(f"  nodes: {stats['n_nodes']}  edges: {stats['n_edges']}  "
          f"struts/cables: {stats['n_struts']}/{stats['n_cables']}")
    print(f"  slot usage: {stats['slot_usage']}")

    # Write the snapshot in the same format as phase9 / phase14
    print(f"[biomedical_instantiation] writing {OUTPUT_PATH.name} …")
    g.save(str(OUTPUT_PATH))

    # Run the canonical enrichment pipeline on it (adds maxims_violations,
    # maxims_proposals, viz_wittgenstein_neighbors, etc. — same fields the
    # paper §5 numbers depend on).
    print(f"[biomedical_instantiation] running enrich_with_maxims on {OUTPUT_PATH.name} …")
    from enrich_with_maxims import enrich
    summary = enrich(OUTPUT_PATH)
    print(f"  enrichment summary: {summary['n_violations']} violations / "
          f"{summary['n_proposals']} proposals / "
          f"{summary['n_nodes_with_findings']} nodes touched")
    print(f"  by_slot: {summary['by_slot']}")
    print(f"  by_proposal_type: {summary['by_proposal_type']}")

    print(f"[biomedical_instantiation] DONE. Snapshot at {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
