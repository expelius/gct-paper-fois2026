"""Extractor for CROSS-CUTS-EXPLORATION-INVENTORY-*.md — produces CC-NEW-XX nodes.

CC-NEW are project-internal cross-cutting hypotheses (s3 structural).
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log', 'prereg', 'project_graph']   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
CC_DIR = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO"

CC_HEADER_RE = re.compile(r"###\s+(CC-NEW-\d+)\s*[—-]\s*(.+?)$", re.MULTILINE)
DID_RE = re.compile(r"\bD-\d+[a-z]?\b")
PCODE_RE = re.compile(r"\bP-[A-Z][A-Z0-9]*(?:-\d+)?\b")
PAPER_RE = re.compile(r"\bP\d+\b")


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    cc_files = sorted(list(CC_DIR.glob("CROSS-CUT*.md")))
    nodes_added = 0
    edges_added = 0
    files_processed = 0

    for f in cc_files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        files_processed += 1

        # Find each CC-NEW-XX block
        matches = list(CC_HEADER_RE.finditer(text))
        for i, m in enumerate(matches):
            cc_id = m.group(1)
            cc_title = m.group(2).strip()
            # Block content is from this match to next (or EOF)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block = text[start:end]

            if cc_id not in graph._nodes:
                graph.add_node(Node(
                    id=cc_id,
                    label=f"{cc_id}: {cc_title[:60]}",
                    scale=3,
                    layer=Layer.STRUCTURAL,
                    metadata={
                        "node_type": "cross_cut",
                        "title": cc_title,
                        "source_file": f.name,
                        "block_excerpt": block[:300],
                    },
                ))
                nodes_added += 1

            # Anchor connections to D-XXX, P-XX, papers
            for did in set(DID_RE.findall(block)):
                if did in graph._nodes:
                    try:
                        graph.add_edge(Edge(
                            source=did, target=cc_id,
                            slot=Slot.SUBSTRATE, confidence=Confidence.EXTRACTED,
                            scale_from=1, scale_to=3,
                            evidence=f"{cc_id} anchored on {did}",
                        ))
                        edges_added += 1
                    except (KeyError, ValueError):
                        continue
            for pcode in set(PCODE_RE.findall(block)):
                if pcode in graph._nodes:
                    try:
                        # Cross-scale (CC-NEW s3 → prereg s1) — PEER_COHERENT
                        # would violate the same-scale similars maxim. The
                        # exploratory hypothesis depends on the prereg as its
                        # methodological/causal ground; CAUSE is the right slot.
                        graph.add_edge(Edge(
                            source=cc_id, target=pcode,
                            slot=Slot.CAUSE, confidence=Confidence.EXTRACTED,
                            scale_from=3, scale_to=1,
                            evidence=f"{cc_id} grounded on prereg {pcode}",
                        ))
                        edges_added += 1
                    except (KeyError, ValueError):
                        continue
            for paper in set(PAPER_RE.findall(block)):
                if paper in graph._nodes:
                    try:
                        graph.add_edge(Edge(
                            source=cc_id, target=paper,
                            slot=Slot.EFFECT, confidence=Confidence.EXTRACTED,
                            scale_from=3, scale_to=2,
                            evidence=f"{cc_id} would feed {paper}",
                        ))
                        edges_added += 1
                    except (KeyError, ValueError):
                        continue

    return {
        "extractor": "cross_cuts",
        "files_processed": files_processed,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='cross_cuts',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['CC-NEW nodes + cross-anchor edges'],
    peer_coherent=['experiments_log', 'prereg', 'project_graph'],
)
