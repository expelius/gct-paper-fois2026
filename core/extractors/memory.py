"""Extractor for memory entries — produces Concept-like nodes from project memory.

Reads ALL .md files in the project memory directory and creates a node per entry,
parsing frontmatter for name + description.

Memory entries are scale 0 (atomic — single notes/decisions) by default; some
are upgraded to scale 1 if they cover multi-D-ID territory.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ['experiments_log', 'project_graph', 'paper_drafts']   # extractors that must run before this one

MEMORY_DIR = Path(os.path.expanduser(
    "~/.claude/projects/C--Users-juand-OneDrive-Documentos-REPOSITORIOS-VS-CODE-Tensegrity/memory"
))

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DID_REF_RE = re.compile(r"\bD-\d+[a-z]?\b")
PAPER_REF_RE = re.compile(r"\bP\d+\b")
RPIVOT_REF_RE = re.compile(r"\bR-\d+[a-z]?\b")


def _parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def extract(graph) -> dict:
    from ..builder import TensegrityGraph

    if not MEMORY_DIR.exists():
        return {"extractor": "memory", "error": "memory dir not found"}

    nodes_added = 0
    edges_added = 0
    files_processed = 0

    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":  # the index, skip
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = _parse_frontmatter(text)
        node_id = f"memory_{f.stem}"
        if node_id in graph._nodes:
            continue
        label = fm.get("name", f.stem.replace("_", " "))[:80]
        description = fm.get("description", "")[:200]
        # Scale heuristic: if entry references many D-IDs (>3), it's a synthesis (s2);
        # if it references R-pivots, it's a narrative-pivot reflection (s3); else s0.
        n_dids = len(set(DID_REF_RE.findall(text)))
        n_rpivots = len(set(RPIVOT_REF_RE.findall(text)))
        if n_rpivots >= 1 or n_dids >= 5:
            scale = 2
        elif n_dids >= 1:
            scale = 1
        else:
            scale = 0
        graph.add_node(Node(
            id=node_id,
            label=label,
            scale=scale,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "memory_entry",
                "source_file": f.name,
                "description": description,
                "n_dids_referenced": n_dids,
                "n_rpivots_referenced": n_rpivots,
            },
        ))
        nodes_added += 1
        files_processed += 1

        # Wire references — memory entry references D-XXX/R-pivot/paper.
        # Slot choice depends on scale relationship to satisfy the maxim layer:
        #   - same scale → PEER_COHERENT (similars at same scale, fine)
        #   - source < target → SPECIFICATION (memory uses target as form/topic)
        #   - source > target → CAUSE (memory grounds its discussion on the lower-scale entity)
        # The slot system populates reciprocals automatically.
        def _wire_reference(target_id: str, target_scale: int, kind: str):
            try:
                if scale == target_scale:
                    slot = Slot.PEER_COHERENT
                elif scale < target_scale:
                    slot = Slot.SPECIFICATION
                else:
                    slot = Slot.CAUSE
                graph.add_edge(Edge(
                    source=node_id, target=target_id,
                    slot=slot, confidence=Confidence.EXTRACTED,
                    scale_from=scale, scale_to=target_scale,
                    evidence=f"memory {f.name} references {kind} {target_id}",
                ))
                return True
            except (KeyError, ValueError):
                return False

        for did in set(DID_REF_RE.findall(text)):
            if did in graph._nodes and _wire_reference(did, 1, "D-id"):
                edges_added += 1
        for rid in set(RPIVOT_REF_RE.findall(text)):
            if rid in graph._nodes and _wire_reference(rid, 3, "R-pivot"):
                edges_added += 1
        for paper in set(PAPER_REF_RE.findall(text)):
            if paper in graph._nodes and _wire_reference(paper, 2, "paper"):
                edges_added += 1

    return {
        "extractor": "memory",
        "files_processed": files_processed,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='memory',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema'],
    effect=['memory entry nodes + slot-by-scale references'],
    peer_coherent=['paper_drafts', 'concepts'],
)
