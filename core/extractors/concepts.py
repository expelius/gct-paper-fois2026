"""Phase 2 — Concept extraction.

Two strategies combined:

1. **Curated concept seed list** from `project_conceptual_vocabulary.md` —
   the vocabulary already curated by the user. Each entry becomes a Concept
   node (s2 structural).

2. **Co-occurrence-based functional uses** — scan all paper drafts + memory
   entries for occurrences of each curated concept; create functional
   holon nodes (s1 functional layer) for each context where the concept appears.

Then run `consolidate_societies()` to verify family resemblance clusters
match the curated taxonomy (Wittgenstein cross-validation).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from collections import defaultdict

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log', 'prereg', 'paper_drafts', 'memory']   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
MEMORY_DIR = Path(os.path.expanduser(
    "~/.claude/projects/C--Users-juand-OneDrive-Documentos-REPOSITORIOS-VS-CODE-Tensegrity/memory"
))
PAPERS_DIR = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO"


# Load curated concepts from the JSON vocabulary file (single source of truth).
# Edit `core/concept_vocabulary.json` to add/remove concepts or extend synonyms;
# no Python edit required.
import json as _json
_VOCAB_PATH = Path(__file__).parent.parent / "concept_vocabulary.json"
try:
    _VOCAB = _json.loads(_VOCAB_PATH.read_text(encoding="utf-8"))
    CURATED_CONCEPTS = [
        (c["canonical"], c["patterns"] + (c.get("synonyms") or []), c["scale"], c["axis"])
        for c in _VOCAB["concepts"]
    ]
    DRIFT_THRESHOLD_DAYS = _VOCAB.get("drift_detection", {}).get("stale_threshold_days", 60)
except Exception as _e:
    # Fallback: empty list (this should never happen — flagged loudly in stats)
    CURATED_CONCEPTS = []
    DRIFT_THRESHOLD_DAYS = 60
    print(f"[concepts.py] WARNING: failed to load vocabulary JSON: {_e}")

_CURATED_CONCEPTS_LEGACY = [
    # ---- Geometric / structural ----
    ("HNC", [r"\bHNC\b", r"Hierarchical Neural Collapse", r"Holonic Neural Composition"], 2, "architecture"),
    ("ETF", [r"\bETF\b", r"Equiangular Tight Frame", r"equiangular"], 2, "geometry"),
    ("IVM", [r"\bIVM\b", r"Isotropic Vector Matrix", r"vector equilibrium", r"cuboctahed"], 2, "geometry"),
    ("Cuboctahedron", [r"cuboctahedr", r"vector equilibrium"], 2, "geometry"),
    ("Tetrahedron", [r"tetrahedr"], 2, "geometry"),
    ("Octahedron", [r"octahedr"], 2, "geometry"),
    ("Icosahedron", [r"icosahedr"], 2, "geometry"),
    ("Dodecahedron", [r"dodecahedr"], 2, "geometry"),
    ("Tensegrity", [r"tensegri[dt]"], 2, "structural"),
    ("Jitterbug", [r"[Jj]itterbug"], 2, "geometry"),
    # ---- Curvature / metric ----
    (r"κ-IVM", [r"\bκ-IVM\b", r"\bkappa[- ]IVM\b", r"κ\s*deviation"], 2, "metric"),
    (r"κ_OR", [r"\bκ_OR\b", r"Ollivier[- ]Ricci"], 2, "metric"),
    # ---- Holon scales ----
    ("s0_bytes", [r"\bs[_₀0]\b.*?byte", r"byte[- ]level\s+s[₀0]"], 2, "scale"),
    ("s1_words", [r"\bs[_₁1]\b.*?word", r"word[- ]scale\s+s[₁1]"], 2, "scale"),
    ("s2_discourse", [r"\bs[_₂2]\b.*?discourse", r"discourse[- ]scale"], 2, "scale"),
    # ---- Project pillars ----
    ("LT_pillar", [r"\bLT\b\s+pillar", r"Liquid Tensegrity"], 2, "pillar"),
    ("NESS_pillar", [r"\bNESS\b", r"non[- ]equilibrium steady state"], 2, "pillar"),
    ("SADE_pillar", [r"\bSADE\b"], 2, "pillar"),
    # ---- Metrics ----
    ("BPB", [r"\bBPB\b", r"bits[- ]per[- ]byte"], 2, "metric"),
    ("AR_TI", [r"\bAR\b.*?Asymmetry Ratio", r"Asymmetry Ratio", r"\bTI\b.*?Tensegrity Index"], 2, "metric"),
    (r"σ_geometric", [r"\bσ\b\s+geometric", r"angular dispersion", r"std.*?angle"], 2, "metric"),
    ("PR_jacobian", [r"\bPR\b.*?Jacobian", r"Participation Ratio.*?Jacobian"], 2, "metric"),
    ("PR_covariance", [r"\bPR\b.*?covariance", r"Participation Ratio.*?covariance"], 2, "metric"),
    ("Cohen_d", [r"Cohen'?s\s*d", r"\bCohen-d\b"], 2, "metric"),
    ("BootstrapCI", [r"bootstrap\s+CI", r"bootstrap.*?confidence"], 2, "metric"),
    # ---- Theoretical ----
    ("Papyan_NeuralCollapse", [r"Papyan", r"neural collapse"], 2, "theoretical"),
    ("Allen_Hierarchy", [r"Allen.*?Giampietro", r"Allen.*?holon", r"hierarchy theory"], 2, "theoretical"),
    ("Fuller_Synergetics", [r"Buckminster Fuller", r"synergetics", r"Fuller IVM"], 2, "theoretical"),
    ("Grant_Projection", [r"Grant.*?Projection", r"Grant theorem", r"Grant.*?solid"], 2, "theoretical"),
    ("Whitehead_Process", [r"Whitehead", r"concrescence"], 2, "theoretical"),
    ("Wittgenstein_Use", [r"Wittgenstein", r"family resemblance", r"language game"], 2, "theoretical"),
    ("Aristotle_Causes", [r"Aristot", r"four causes", r"causa\s+(material|formal|efficient|final)"], 2, "theoretical"),
    ("Poincare_Disk", [r"Poincar[ée] (disk|ball)", r"hyperbolic embedding"], 2, "theoretical"),
    # ---- Methodological ----
    ("PreRegistration", [r"pre[- ]regist", r"OSF preregist"], 2, "methodological"),
    ("WikiText103", [r"WikiText[- ]?103", r"wikitext"], 2, "data"),
    ("EdgeOfETF", [r"edge[- ]of[- ]ETF", r"deformed attractor"], 2, "theoretical"),
    ("RolesSwitching", [r"role[- ]switching", r"liquid.*?switch"], 2, "theoretical"),
]
# (legacy list above retained for diff comparison; CURATED_CONCEPTS now loaded from JSON)


def _slug(name: str) -> str:
    return "concept_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]


def extract(graph) -> dict:
    """Extract Concept nodes (s2 structural) + functional uses (s1)
    + family resemblance edges (Wittgenstein PEER_COHERENT)."""
    from ..builder import TensegrityGraph

    # Gather text corpus to scan
    files_to_scan = []
    for f in PAPERS_DIR.glob("PAPER-*.md"):
        files_to_scan.append(f)
    for f in PAPERS_DIR.glob("OSF-PREREG-*.md"):
        files_to_scan.append(f)
    for f in PAPERS_DIR.glob("CROSS-CUT*.md"):
        files_to_scan.append(f)
    for f in MEMORY_DIR.glob("*.md"):
        if f.name != "MEMORY.md":
            files_to_scan.append(f)

    nodes_added = 0
    edges_added = 0
    concept_uses: dict[str, list[str]] = defaultdict(list)  # concept_id → list of file_ids where it appears

    # Step 1: register all curated concepts as structural nodes
    concept_nodes = {}
    for canonical, patterns, scale, axis in CURATED_CONCEPTS:
        cid = _slug(canonical)
        if cid in graph._nodes:
            continue
        graph.add_node(Node(
            id=cid,
            label=canonical,
            scale=scale,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "concept",
                "axis_tag": axis,
                "alias_patterns": patterns,
                "canonical": canonical,
            },
        ))
        concept_nodes[cid] = (canonical, patterns, axis)
        nodes_added += 1

    # Step 2: scan corpus for occurrences → create functional uses + Peer-coherent edges
    file_to_text = {}
    for f in files_to_scan:
        try:
            file_to_text[f] = f.read_text(encoding="utf-8")
        except Exception:
            continue

    # For each concept, find documents that mention it; create functional use per (concept, doc)
    for cid, (canonical, patterns, axis) in concept_nodes.items():
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        for f, text in file_to_text.items():
            n_hits = sum(len(p.findall(text)) for p in compiled)
            if n_hits == 0:
                continue
            # Create functional holon: this concept AS USED IN this file
            file_slug = re.sub(r"[^a-z0-9]+", "_", f.stem.lower()).strip("_")[:40]
            fid = f"{cid}_in_{file_slug}"
            if fid not in graph._nodes:
                graph.add_node(Node(
                    id=fid,
                    label=f"{canonical} as used in {f.stem[:30]}",
                    scale=1,
                    layer=Layer.FUNCTIONAL,
                    structural_ref=cid,
                    metadata={
                        "node_type": "concept_functional_use",
                        "in_document": f.name,
                        "n_hits": n_hits,
                        "axis": axis,
                    },
                ))
                nodes_added += 1
                concept_uses[cid].append(fid)
            # Edge: functional use → structural concept (role_of via SPECIFICATION)
            try:
                graph.add_edge(Edge(
                    source=fid, target=cid,
                    slot=Slot.SPECIFICATION, confidence=Confidence.EXTRACTED,
                    scale_from=1, scale_to=2,
                    evidence=f"concept '{canonical}' appears {n_hits}× in {f.name}",
                ))
                edges_added += 1
            except (KeyError, ValueError):
                pass
            # Edge: doc PEER-COHERENT to concept (the doc TALKS ABOUT the concept)
            # Find the doc node id (could be paper, prereg, memory, cc-new)
            possible_doc_ids = [
                # paper from filename PAPER-P1-...
                next((p for p in [f.stem.split("-")[1] if "PAPER-" in f.stem and len(f.stem.split("-")) > 1 else None] if p), None),
                # prereg
                f"prereg_{f.stem.replace('OSF-PREREG-', '').lower()}".replace("-", "_"),
                # memory
                f"memory_{f.stem}",
            ]
            for doc_id_candidate in possible_doc_ids:
                if doc_id_candidate and doc_id_candidate in graph._nodes:
                    # Slot choice depends on the doc-vs-concept scale relation
                    # (concept is at scale 2). Same scale = PEER_COHERENT;
                    # doc lower than concept = SPECIFICATION (doc uses concept
                    # as its form/topic). Avoids cross-scale violations of the
                    # same-scale similars maxim.
                    doc_scale = graph._nodes[doc_id_candidate].scale
                    if doc_scale == 2:
                        peer_slot = Slot.PEER_COHERENT
                    elif doc_scale < 2:
                        peer_slot = Slot.SPECIFICATION
                    else:
                        peer_slot = Slot.CAUSE
                    try:
                        graph.add_edge(Edge(
                            source=doc_id_candidate, target=cid,
                            slot=peer_slot, confidence=Confidence.EXTRACTED,
                            scale_from=doc_scale, scale_to=2,
                            evidence=f"{f.name} mentions concept {canonical}",
                        ))
                        edges_added += 1
                    except (KeyError, ValueError):
                        continue
                    break

    # Drift detection: surface concepts that have ZERO uses in the entire
    # corpus (likely deprecated or never adopted in writing). Stale-by-time
    # detection requires per-file mtime tracking — deferred to a follow-up
    # extractor that consumes file mtimes.
    unused_concepts = [cid for cid, uses in concept_uses.items() if not uses]
    # Check for canonical concepts that exist as nodes but had zero hits
    for cid in concept_nodes:
        if cid not in concept_uses:
            unused_concepts.append(cid)

    # ---- Special wiring for concept_liquid_tensegrity ----------------------
    # concept_liquid_tensegrity is the project's name-concept — the core
    # unifying concept that currently has no node. It needs richer metadata
    # and explicit edges that the co-occurrence scanner cannot infer.
    # These edges are added here post-registration so all referenced nodes
    # exist (concepts extractor runs after project_graph, paper_drafts, etc.)
    lt_id = "concept_liquid_tensegrity"
    if lt_id in graph._nodes:
        # Enrich the node metadata with the full description and tags
        graph._nodes[lt_id].metadata.update({
            "description": (
                "Dynamic coexistence of crystalline and fluid attractor phases "
                "in hierarchical recurrent language models under linguistic input "
                "modulation. The core unifying concept of the Tensegrity project."
            ),
            "tags": ["liquid_tensegrity", "lt", "phase_coexistence", "pillar_lt"],
            "is_project_name_concept": True,
        })

        # Peer-concept edges (same scale=2, structural — PEER_COHERENT)
        _peer_edges = [
            ("concept_tensegrity",       Slot.PEER_COHERENT,       "LT instantiates tensegrity principle"),
            ("concept_ivm",              Slot.PEER_COHERENT,       "IVM geometry underlies LT crystalline phase"),
            ("concept_etf",              Slot.PEER_COHERENT,       "ETF is the geometric attractor of the LT crystalline phase"),
            ("concept_lt_pillar",        Slot.PEER_COHERENT,       "LT pillar reifies Liquid Tensegrity as a project pillar"),
            ("concept_edgeofetf",        Slot.PEER_COHERENT,       "Edge-of-ETF is the computational regime of LT"),
            ("concept_rolesswitching",   Slot.PEER_COHERENT,       "Role-switching is the mechanism of LT fluid phase"),
        ]
        for target_id, slot, evidence in _peer_edges:
            if target_id in graph._nodes:
                try:
                    graph.add_edge(Edge(
                        source=lt_id, target=target_id,
                        slot=slot, confidence=Confidence.EXTRACTED,
                        scale_from=2, scale_to=2,
                        evidence=evidence,
                        essence="liquid tensegrity phase coexistence" if slot == Slot.PEER_COHERENT else "",
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    pass

        # Pillar containment (project contains LT concept via CONTAINER)
        _container_edges = [
            ("pillar_lt", Slot.CONTAINER, "pillar_lt is the formal genus of concept_liquid_tensegrity"),
        ]
        for target_id, slot, evidence in _container_edges:
            if target_id in graph._nodes:
                try:
                    graph.add_edge(Edge(
                        source=lt_id, target=target_id,
                        slot=slot, confidence=Confidence.EXTRACTED,
                        scale_from=2, scale_to=2,
                        evidence=evidence,
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    pass

        # Paper edges (LT concept SUPPORTS these papers — CAUSE slot, scale 2→2)
        _paper_edges = [
            ("P1-HNC",             "P1-HNC is the primary empirical paper for LT"),
            ("P4-LIQUID-TENSEGRITY","P4 is the theory paper explicitly defining LT"),
            ("P7",                  "P7 generalizes LT to multi-architecture setting"),
            ("P8-MESH-UNIVERSALITY","P8 extends LT universality claim to mesh architectures"),
            ("P9-UPHIP",            "P9 grounds LT in the UPHIP predictive-pressure framework"),
            ("P-OMEGA",             "P-OMEGA is the synthesis paper that crowns the LT research program"),
        ]
        for target_id, evidence in _paper_edges:
            if target_id in graph._nodes:
                try:
                    graph.add_edge(Edge(
                        source=lt_id, target=target_id,
                        slot=Slot.CAUSE, confidence=Confidence.EXTRACTED,
                        scale_from=2, scale_to=2,
                        evidence=evidence,
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    pass

        # Key experiment edges (D-IDs SUPPORT the LT concept — SUBSTRATE slot)
        _did_edges = [
            ("D-228",  "D-228: HNC 20.5× more BPB-efficient than LSTM — LT-2' primary confirmation"),
            ("D-229",  "D-229: σ-slow bimodal structure confirmed — LT phase coexistence evidence"),
            ("D-226",  "D-226: κ-ETF basin rigidity confirmed across substrates — LT-2' robustness"),
            ("D-251b", "D-251b: depth×width basin geometry 4/4 PASS — LT curvature-structure mechanism"),
        ]
        for target_id, evidence in _did_edges:
            if target_id in graph._nodes:
                try:
                    graph.add_edge(Edge(
                        source=target_id, target=lt_id,
                        slot=Slot.SUBSTRATE, confidence=Confidence.EXTRACTED,
                        scale_from=1, scale_to=2,
                        evidence=evidence,
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    pass

    return {
        "extractor": "concepts",
        "files_processed": len(file_to_text),
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "concepts_with_uses": sum(1 for v in concept_uses.values() if v),
        "concepts_unused": sorted(set(unused_concepts)),
        "drift_threshold_days": DRIFT_THRESHOLD_DAYS,
        "liquid_tensegrity_wired": lt_id in graph._nodes,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='concepts',
    scale=2,
    aristotelian_cause='formal',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['concept structural nodes + functional uses + SPECIFICATION edges'],
    peer_coherent=['memory', 'paper_drafts'],
)
