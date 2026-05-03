"""Extractor for OSF-PREREG-P*.md — produces P-XX prediction nodes + edges.

Parses ALL OSF-PREREG-*.md files in LINEAS CONSOLIDADAS DE TRABAJO/.
For each pre-reg doc, extracts:
  - The pre-reg document itself as s2 structural node
  - P-XX prediction codes mentioned (P-A2, P-C1-1, P-D095, P-NEG-1, etc.)
  - Specification edges from each P-XX → corresponding claim text (s0)
  - Container edges from doc → P-XX (genus relation)

Pre-reg docs are scale 2 (paper-level artifact); predictions are scale 1.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log']   # extractors that must run before this one

# Match P-XX codes: P-A2, P-A3-4, P-C1-1, P-D095, P-NEG-1, P-D251-1, etc.
PCODE_RE = re.compile(r"\bP-[A-Z][A-Z0-9]*(?:-\d+)?\b")

# Match section/claim headers: ### 2.1 Claim C1, ## 1. Hipótesis, etc.
SECTION_HEADER_RE = re.compile(r"^#{2,4}\s+(.+?)$", re.MULTILINE)

# Match prediction lines: "- **P-A2.** ..."
PREDICTION_LINE_RE = re.compile(r"-\s+\*\*(P-[A-Z0-9-]+)[\.\,]\*\*\s*(.+?)$", re.MULTILINE)

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
PREREG_DIR = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO"


def _doc_id_from_filename(filename: str) -> str:
    """OSF-PREREG-P1.md → 'prereg_p1'; OSF-PREREG-D251b.md → 'prereg_d251b'."""
    stem = Path(filename).stem.replace("OSF-PREREG-", "").lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return f"prereg_{stem}"


def parse_one_prereg(file_path: Path) -> tuple[list[Node], list[Edge]]:
    """Parse a single OSF-PREREG-*.md file."""
    text = file_path.read_text(encoding="utf-8")

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    doc_id = _doc_id_from_filename(file_path.name)
    title_m = re.search(r"^#\s+(.+?)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else file_path.name

    # Doc node (s2 structural)
    doc_node = Node(
        id=doc_id,
        label=f"Pre-reg: {title[:80]}",
        scale=2,
        layer=Layer.STRUCTURAL,
        metadata={
            "node_type": "prereg_document",
            "source_file": file_path.name,
            "title": title,
        },
    )
    nodes[doc_id] = doc_node

    # Find target paper(s) referenced in the title (P1, P2, etc.)
    paper_refs = re.findall(r"\bPaper\s+(P\d+)\b|\b(P\d+)\b", title)
    target_papers = set()
    for m in paper_refs:
        for paper_id in m:
            if paper_id and paper_id != doc_id:
                target_papers.add(paper_id)

    # Each prediction P-XX is a node (s1, structural) plus an edge from doc
    seen_pcodes = set()
    for m in PREDICTION_LINE_RE.finditer(text):
        pcode = m.group(1)
        text_excerpt = m.group(2)[:200].strip()
        if pcode in seen_pcodes:
            continue
        seen_pcodes.add(pcode)
        if pcode not in nodes:
            nodes[pcode] = Node(
                id=pcode,
                label=f"{pcode}: {text_excerpt[:60]}",
                scale=1,
                layer=Layer.STRUCTURAL,
                metadata={
                    "node_type": "prereg_prediction",
                    "predicted_in": doc_id,
                    "prediction_text": text_excerpt,
                },
            )
        # doc CONTAINS prediction (genus)
        edges.append(Edge(
            source=doc_id, target=pcode,
            slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED,
            scale_from=2, scale_to=1,
            evidence=f"{file_path.name} prediction line",
        ))

    # Catch P-XX codes mentioned in the doc that aren't formal predictions
    for pcode in PCODE_RE.findall(text):
        if pcode not in seen_pcodes and pcode not in nodes:
            nodes[pcode] = Node(
                id=pcode,
                label=f"{pcode} (referenced)",
                scale=1,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "prereg_prediction_referenced", "predicted_in": doc_id},
            )
            seen_pcodes.add(pcode)
            edges.append(Edge(
                source=doc_id, target=pcode,
                slot=Slot.CONTAINER, confidence=Confidence.INFERRED,
                scale_from=2, scale_to=1,
                evidence=f"{file_path.name} mentions {pcode}",
            ))

    # If doc references target paper(s), add Specification edge (formal cause: prereg specifies paper)
    for paper_id in target_papers:
        if paper_id not in nodes:
            nodes[paper_id] = Node(
                id=paper_id,
                label=f"Paper {paper_id}",
                scale=2,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "paper", "discovered_via": "prereg_extractor"},
            )
        edges.append(Edge(
            source=doc_id, target=paper_id,
            slot=Slot.SPECIFICATION, confidence=Confidence.EXTRACTED,
            scale_from=2, scale_to=2,
            evidence=f"prereg {file_path.name} specifies {paper_id}",
        ))

    return list(nodes.values()), edges


def extract(graph) -> dict:
    """Parse ALL OSF-PREREG-*.md files in the project."""
    from ..builder import TensegrityGraph

    prereg_files = sorted(PREREG_DIR.glob("OSF-PREREG-*.md"))
    total_nodes = 0
    total_edges = 0
    files_processed = 0

    for f in prereg_files:
        try:
            nodes, edges = parse_one_prereg(f)
        except Exception as e:
            print(f"[prereg] ERROR parsing {f.name}: {e}")
            continue
        files_processed += 1
        if isinstance(graph, TensegrityGraph):
            for n in nodes:
                if n.id not in graph._nodes:
                    graph.add_node(n)
                    total_nodes += 1
            for e in edges:
                try:
                    graph.add_edge(e)
                    total_edges += 1
                except (KeyError, ValueError):
                    continue
    return {
        "extractor": "prereg",
        "files_processed": files_processed,
        "nodes_added": total_nodes,
        "edges_added": total_edges,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='prereg',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['P-XX prereg prediction nodes + linkage to D-XXX'],
    peer_coherent=['experiments_log', 'cross_cuts'],
)
