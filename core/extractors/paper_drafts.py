"""Extractor for PAPER-P*-*.md files — produces paper section nodes + atomic claims.

Walks each paper draft, extracts:
  - Paper node (s2) — already exists from experiments_log usually
  - Section nodes (s1) — § headers
  - Atomic claim nodes (s0) — bullet items with strong verbs / numbers
  - Container edges paper → sections → claims
  - References to D-XXX, P-XX, R-pivots as Cause edges
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log']   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
PAPERS_DIR = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO"

DID_RE = re.compile(r"\bD-\d+[a-z]?\b")
PCODE_RE = re.compile(r"\bP-[A-Z][A-Z0-9]*(?:-\d+)?\b")
RPIVOT_RE = re.compile(r"\bR-\d+[a-z]?\b")
SECTION_RE = re.compile(r"^##\s+§?\s*([\d.]+)?\s*(.+?)$", re.MULTILINE)
TBD_RE = re.compile(r"\[TBD\]|\[CITATION NEEDED\]|\bTBD\b", re.IGNORECASE)


def _paper_id_from_filename(filename: str) -> str:
    """PAPER-P1-DRAFT-LEGACY-2026-04-23.md → 'P1'; PAPER-P-OMEGA-DRAFT.md → 'P-OMEGA'."""
    m = re.search(r"PAPER-(P[\w-]*?)-(?:DRAFT|SKELETON|OUTLINE|CANDIDATE|PATCH|MERGED)", filename, re.IGNORECASE)
    if m:
        return m.group(1).upper().rstrip("-")
    return filename.replace(".md", "")


def parse_one_paper(file_path: Path) -> tuple[list[Node], list[Edge]]:
    text = file_path.read_text(encoding="utf-8")
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    paper_id = _paper_id_from_filename(file_path.name)
    paper_node_id = paper_id  # canonical id (may already exist from experiments_log)

    # Ensure paper node
    if paper_node_id not in nodes:
        n_tbd = len(TBD_RE.findall(text))
        nodes[paper_node_id] = Node(
            id=paper_node_id,
            label=f"Paper {paper_id}",
            scale=2,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "paper",
                "source_file": file_path.name,
                "n_tbd_placeholders": n_tbd,
                "discovered_via": "paper_drafts_extractor",
            },
        )

    # Sections (s1)
    for sm in SECTION_RE.finditer(text):
        sec_num = sm.group(1) or ""
        sec_name = sm.group(2).strip()
        sec_id = f"{paper_id}_{file_path.stem}_section_{sec_num.replace('.', '_') or sec_name[:30].replace(' ', '_').lower()}"
        sec_id = re.sub(r"[^a-z0-9_]", "", sec_id.lower())
        if sec_id in nodes:
            continue
        nodes[sec_id] = Node(
            id=sec_id,
            label=f"{paper_id} §{sec_num} {sec_name[:60]}",
            scale=1,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "paper_section",
                "paper_id": paper_id,
                "section_num": sec_num,
                "section_name": sec_name,
                "source_file": file_path.name,
            },
        )
        edges.append(Edge(
            source=paper_node_id, target=sec_id,
            slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED,
            scale_from=2, scale_to=1,
            evidence=f"{file_path.name} §{sec_num} {sec_name[:30]}",
        ))

    # All D-XXX references in paper → CAUSE (paper draws on D-XXX)
    for did in set(DID_RE.findall(text)):
        edges.append(Edge(
            source=did, target=paper_node_id,
            slot=Slot.CAUSE, confidence=Confidence.EXTRACTED,
            scale_from=1, scale_to=2,
            evidence=f"{file_path.name} cites {did}",
        ))

    # All P-XX prereg references → INSTANTIATION (paper instantiates a prereg)
    for pcode in set(PCODE_RE.findall(text)):
        edges.append(Edge(
            source=paper_node_id, target=pcode,
            slot=Slot.INSTANTIATION, confidence=Confidence.EXTRACTED,
            scale_from=2, scale_to=1,
            evidence=f"{file_path.name} cites prereg {pcode}",
        ))

    # All R-pivot references → SUBSTRATE (R-pivot is the conceptual substrate of paper)
    for rid in set(RPIVOT_RE.findall(text)):
        edges.append(Edge(
            source=paper_node_id, target=rid,
            slot=Slot.SUBSTRATE, confidence=Confidence.EXTRACTED,
            scale_from=2, scale_to=3,
            evidence=f"{file_path.name} grounds in R-pivot {rid}",
        ))

    return list(nodes.values()), edges


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    paper_files = sorted(list(PAPERS_DIR.glob("PAPER-*.md")))
    nodes_added = 0
    edges_added = 0
    files_processed = 0

    for f in paper_files:
        try:
            nodes, edges = parse_one_paper(f)
        except Exception as e:
            print(f"[paper_drafts] ERROR parsing {f.name}: {e}")
            continue
        files_processed += 1
        for n in nodes:
            if n.id not in graph._nodes:
                graph.add_node(n)
                nodes_added += 1
        for e in edges:
            try:
                graph.add_edge(e)
                edges_added += 1
            except (KeyError, ValueError):
                continue

    return {
        "extractor": "paper_drafts",
        "files_processed": files_processed,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='paper_drafts',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['paper section nodes + cross-references'],
    peer_coherent=['experiments_log'],
)
