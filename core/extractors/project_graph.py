"""Extractor for PROJECT-GRAPH-LIVE.md — produces R-pivot nodes (s3) + Pillar nodes (s2).

PROJECT-GRAPH-LIVE has the canonical structure of:
  - 3 theoretical pillars (LT, NESS, SADE) — s2
  - 7 research lines — s3
  - 10 papers — s2 (already discovered via experiments_log)
  - R-pivots (R-001, R-002, R-003, R-004 + sub-letters) — s3
  - dependencies between papers
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = []   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
PG_FILE = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO" / "PROJECT-GRAPH-LIVE.md"

RPIVOT_RE = re.compile(r"\bR-\d+[a-z]?\b")
PAPER_RE = re.compile(r"\bP\d+\b")

PILLAR_NAMES = {"LT", "NESS", "SADE"}
LINE_NAMES = {"A", "A2", "B", "C", "D", "E", "F"}


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    if not PG_FILE.exists():
        return {"extractor": "project_graph", "error": "file not found"}

    text = PG_FILE.read_text(encoding="utf-8")

    nodes_added = 0
    edges_added = 0

    # ---- 3 pillars (s2 structural) ----
    for pillar in PILLAR_NAMES:
        pid = f"pillar_{pillar.lower()}"
        if pid not in graph._nodes:
            graph.add_node(Node(
                id=pid,
                label=f"Pillar {pillar}",
                scale=2,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "pillar", "name": pillar, "source": "PROJECT-GRAPH-LIVE.md §1"},
            ))
            nodes_added += 1

    # ---- R-pivots (s3 structural) ----
    rpivots = sorted(set(RPIVOT_RE.findall(text)))
    for rid in rpivots:
        if rid not in graph._nodes:
            # Find first context around R-id mention
            m = re.search(rf"\b{re.escape(rid)}\b[^\n]*", text)
            ctx = m.group(0)[:120] if m else rid
            graph.add_node(Node(
                id=rid,
                label=f"{rid}: {ctx[:60]}",
                scale=3,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "narrative_pivot", "context_snippet": ctx},
            ))
            nodes_added += 1

    # ---- Research lines (s3 structural) ----
    for ln in LINE_NAMES:
        lid = f"linea_{ln.lower()}"
        if lid not in graph._nodes:
            graph.add_node(Node(
                id=lid,
                label=f"Línea {ln}",
                scale=3,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "research_line", "name": ln},
            ))
            nodes_added += 1

    # ---- Papers (ensure existence) — s2 ----
    papers_in_text = sorted(set(PAPER_RE.findall(text)))
    for pid in papers_in_text:
        if pid not in graph._nodes:
            graph.add_node(Node(
                id=pid,
                label=f"Paper {pid}",
                scale=2,
                layer=Layer.STRUCTURAL,
                metadata={"node_type": "paper", "discovered_via": "project_graph_extractor"},
            ))
            nodes_added += 1

    # ---- Edges: each pillar ENVIRONS / CONTAINS the papers in its scope ----
    # Heuristic: search PROJECT-GRAPH for which papers are listed under each pillar
    # (Section §1 typically lists papers per pillar.)
    pillar_section_m = re.search(r"## §1\..+?(?=^## §2)", text, re.DOTALL | re.MULTILINE)
    if pillar_section_m:
        pillar_section = pillar_section_m.group(0)
        for pillar in PILLAR_NAMES:
            pid = f"pillar_{pillar.lower()}"
            # Find the block for this pillar
            pblock_m = re.search(rf"\b{pillar}\b.+?(?=\b(?:LT|NESS|SADE)\b|## )", pillar_section, re.DOTALL)
            pblock = pblock_m.group(0) if pblock_m else ""
            for paper in PAPER_RE.findall(pblock):
                try:
                    graph.add_edge(Edge(
                        source=pid, target=paper,
                        slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED,
                        scale_from=2, scale_to=2,
                        evidence=f"PROJECT-GRAPH-LIVE §1 lists {paper} under pillar {pillar}",
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    continue

    # ---- R-pivots are CAUSES of the project's narrative state ----
    # Connect R-pivots to project-level (s4) — create a project node if needed
    project_id = "tensegrity_project"
    if project_id not in graph._nodes:
        graph.add_node(Node(
            id=project_id,
            label="Tensegrity Project",
            scale=4,
            layer=Layer.STRUCTURAL,
            metadata={"node_type": "project_root"},
        ))
        nodes_added += 1
    for rid in rpivots:
        try:
            graph.add_edge(Edge(
                source=rid, target=project_id,
                slot=Slot.CAUSE, confidence=Confidence.EXTRACTED,
                scale_from=3, scale_to=4,
                evidence=f"R-pivot {rid} reframes the project narrative",
            ))
            edges_added += 1
        except (KeyError, ValueError):
            continue

    # ---- Pillars CONTAIN their concepts in the project (genus) ----
    for pillar in PILLAR_NAMES:
        pid = f"pillar_{pillar.lower()}"
        try:
            graph.add_edge(Edge(
                source=project_id, target=pid,
                slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED,
                scale_from=4, scale_to=2,
                evidence="project contains pillar",
            ))
            edges_added += 1
        except (KeyError, ValueError):
            continue

    return {
        "extractor": "project_graph",
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "rpivots_found": len(rpivots),
        "papers_found": len(papers_in_text),
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='project_graph',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['pillar nodes (LT/NESS/SADE) + R-pivot nodes + project root'],
    peer_coherent=['cross_cuts'],
)
