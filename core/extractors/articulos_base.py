"""Extractor for ARTICULOS BASE/ — produces external Citation nodes (s2 structural).

Each .md or .pdf in ARTICULOS BASE/ becomes a Citation node. The library is
the project's foundational reference set; nodes here can be CAUSE-cited by
paper drafts.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log']   # extractors that must run before this one

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
ARTICULOS_DIR = PROJECT_ROOT / "ARTICULOS BASE"


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    if not ARTICULOS_DIR.exists():
        return {"extractor": "articulos_base", "error": "dir not found"}

    nodes_added = 0
    edges_added = 0
    files_processed = 0

    # Both .md (synthesis docs) and .pdf (raw papers)
    for f in ARTICULOS_DIR.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".md", ".pdf"):
            continue
        files_processed += 1
        # Build node id
        node_id = "extref_" + re.sub(r"[^a-z0-9_]+", "_", f.stem.lower()).strip("_")[:60]
        if node_id in graph._nodes:
            continue
        graph.add_node(Node(
            id=node_id,
            label=f"Ext: {f.stem[:60]}",
            scale=2,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "external_reference",
                "source_file": f.name,
                "extension": f.suffix.lower(),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "library": "ARTICULOS BASE",
            },
        ))
        nodes_added += 1

    # If MDs have content, scan for D-XXX or P-XX or paper references
    for f in ARTICULOS_DIR.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        node_id = "extref_" + re.sub(r"[^a-z0-9_]+", "_", f.stem.lower()).strip("_")[:60]
        if node_id not in graph._nodes:
            continue
        # External ref CAUSES (informs) any D-XXX it mentions
        for did in set(re.findall(r"\bD-\d+[a-z]?\b", text)):
            if did in graph._nodes:
                try:
                    graph.add_edge(Edge(
                        source=node_id, target=did,
                        slot=Slot.CAUSE, confidence=Confidence.INFERRED,
                        scale_from=2, scale_to=1,
                        evidence=f"external ref {f.name} mentions {did}",
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    continue
        # External ref PEER-COHERENT to any pillar it discusses
        for pillar in ("LT", "NESS", "SADE"):
            if re.search(rf"\b{pillar}\b", text):
                pid = f"pillar_{pillar.lower()}"
                if pid in graph._nodes:
                    try:
                        graph.add_edge(Edge(
                            source=node_id, target=pid,
                            slot=Slot.PEER_COHERENT, confidence=Confidence.INFERRED,
                            scale_from=2, scale_to=2,
                            evidence=f"external ref {f.name} discusses pillar {pillar}",
                        ))
                        edges_added += 1
                    except (KeyError, ValueError):
                        continue

    return {
        "extractor": "articulos_base",
        "files_processed": files_processed,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='articulos_base',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['external reference nodes + CAUSE edges to D-IDs'],
)
