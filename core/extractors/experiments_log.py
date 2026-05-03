"""Extractor for EXPERIMENTS-LOG.md — produces D-XXX nodes + Container/Specification/Predecessor edges.

Reads the table rows in `LINEAS CONSOLIDADAS DE TRABAJO/EXPERIMENTS-LOG.md`
and yields:
  - D-XXX nodes (s1, structural) with state, script, carril, seeds metadata
  - Paper nodes (s2) referenced via "Feeds" column
  - Container edges Paper → D-XXX (genus relation: paper contains experiment)
  - Specification edges D-XXX → P-XX pre-reg prediction (formal cause: experiment instantiates pre-reg)
  - Predecessor edges D-XXX → D-(XXX-suffix) for supersession lineages (D-101c supersedes D-101)
  - Effect edges D-XXX → results_*.json node (when extractable from "Resultado 1-línea")

Pure structural parsing — no LLM cost, no external dependencies beyond stdlib.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = []   # extractors that must run before this one


# Regex for table row capturing D-ID and key fields.
# Rows look like: | D-095 | 2026-04-20 | `exp_d095_bicondition.py` | A (local CPU) | n=3 × 5 cond = 15 models | P3.§Results (primary), P1.§4.2b checkpoints | P-D095 | **OK — REINTERPRETA P3** | P1✅ ... |
ROW_RE = re.compile(
    r"^\|\s*"
    r"(?P<did>D-\d+[a-z]?)\s*\|\s*"               # D-ID (with optional letter suffix)
    r"(?P<date>[^|]*?)\s*\|\s*"                   # Fecha
    r"(?P<script>[^|]*?)\s*\|\s*"                 # Script
    r"(?P<carril>[^|]*?)\s*\|\s*"                 # Carril
    r"(?P<seeds>[^|]*?)\s*\|\s*"                  # Seeds
    r"(?P<feeds>[^|]*?)\s*\|\s*"                  # Feeds (paper sections)
    r"(?P<prereg>[^|]*?)\s*\|\s*"                 # Pre-reg
    r"(?P<estado>[^|]*?)\s*\|\s*"                 # Estado
    r"(?P<resultado>[^|]*?)\s*\|?\s*$",           # Resultado 1-línea
    re.MULTILINE,
)

# Match paper section refs.  Handles all formats found in the LOG:
#   Standard:          "P1.§4.2b"      "P3.§Results"
#   Space before §:    "P1 §future"    "P6 §3.6"
#   Version string:    "P4 v3 §5"      "P4 v3 §Results"
# NOT matched: pre-reg codes "P-D095" (dash after P, not digit).
PAPER_SECTION_RE = re.compile(
    r"P(\d+)"               # paper number
    r"(?:\s+v[\w.]+)?"      # optional version tag: "v3", "v3.1"
    r"\s*\.?\s*"            # optional dot with surrounding whitespace
    r"§\s*"                 # section marker §
    r"([^\s,)(§|]+)",       # section id — no spaces, commas, pipes, or §
    re.IGNORECASE,
)

# Match pre-reg codes like P-D095, P-A2, P-NEG-1
PREREG_RE = re.compile(r"P-[A-Z0-9]+(?:-\d+)?")

# Match supersession lineage: D-101c → suffix means parent is D-101
LINEAGE_RE = re.compile(r"^(D-\d+)([a-z])$")


def _normalize_state(estado_raw: str) -> str:
    """Map noisy estado strings to canonical state names."""
    s = estado_raw.upper()
    s = re.sub(r"\*+|`+", "", s).strip()
    if "OK" in s and "REINTERPRETA" in s:
        return "OK_REINTERPRETED"
    if "SUPERSEDED" in s:
        return "SUPERSEDED"
    if "FAIL" in s or "REJECT" in s:
        return "FAIL"
    if "INCONCLUSIVE" in s:
        return "INCONCLUSIVE"
    if "RUN" in s or "RUNNING" in s:
        return "RUN"
    if "QUEUED" in s:
        return "QUEUED"
    if "OK" in s:
        return "OK"
    return "UNKNOWN"


def _extract_papers(feeds_raw: str) -> list[tuple[str, str]]:
    """Parse Feeds column → [(paper_id, section), ...].

    Handles all § formats (standard dot, space-separated, versioned):
        "P1.§4.2b"       → ("P1", "4.2b")
        "P3.§Results"    → ("P3", "Results")
        "P1 §future"     → ("P1", "future")
        "P4 v3 §5"       → ("P4", "5")
        "P6 §3.6"        → ("P6", "3.6")
    """
    return [
        (f"P{m.group(1)}", m.group(2))
        for m in PAPER_SECTION_RE.finditer(feeds_raw)
    ]


def _extract_preregs(prereg_raw: str) -> list[str]:
    """Parse "P-D095, P-A2" → ["P-D095", "P-A2"]."""
    return PREREG_RE.findall(prereg_raw)


def _is_estado_negative_prehension(estado: str) -> bool:
    """Whitehead negative prehension: explicit exclusion / rejection."""
    s = estado.upper()
    return "REJECT" in s or "FAIL" in s or "SUPERSEDED" in s


def _parse_date(date_raw: str) -> str:
    """Try to parse a date string; return ISO format or original."""
    date_raw = date_raw.strip().replace("(", "").replace(")", "")
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(date_raw, fmt).isoformat()
        except ValueError:
            continue
    return date_raw  # fallback: keep original


def parse_experiments_log(file_path: Path) -> tuple[list[Node], list[Edge]]:
    """Parse EXPERIMENTS-LOG.md, return (nodes, edges) lists.

    Caller is responsible for adding to graph (allows dedupe + ordering).
    """
    text = Path(file_path).read_text(encoding="utf-8")
    rows = list(ROW_RE.finditer(text))

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    for m in rows:
        did = m.group("did")
        date_raw = m.group("date")
        script = m.group("script").strip().replace("`", "")
        carril = m.group("carril").strip()
        seeds = m.group("seeds").strip()
        feeds_raw = m.group("feeds")
        prereg_raw = m.group("prereg")
        estado_raw = m.group("estado")
        resultado = m.group("resultado").strip()

        # ---- Build the D-XXX node ----
        state = _normalize_state(estado_raw)
        active_since = _parse_date(date_raw)
        d_node = Node(
            id=did,
            label=f"{did}: {resultado[:80]}" if resultado else did,
            scale=1,  # s1 — section/experiment
            layer=Layer.STRUCTURAL,
            active_since=active_since,
            metadata={
                "node_type": "experiment",
                "script": script,
                "carril": carril,
                "seeds": seeds,
                "state": state,
                "prereg_raw": prereg_raw,
                "resultado_short": resultado[:200],
                "feeds_raw": feeds_raw,
            },
        )
        nodes[did] = d_node

        # ---- Paper container edges (genus: paper contains experiment) ----
        for paper_id, section in _extract_papers(feeds_raw):
            # Ensure paper node exists (s2 structural)
            if paper_id not in nodes:
                nodes[paper_id] = Node(
                    id=paper_id,
                    label=f"Paper {paper_id}",
                    scale=2,
                    layer=Layer.STRUCTURAL,
                    metadata={"node_type": "paper", "discovered_via": "experiments_log_feeds"},
                )
            # Section node (s1) under paper
            section_id = f"{paper_id}_section_{section.replace('.', '_').replace('§', '')}"
            if section_id not in nodes:
                nodes[section_id] = Node(
                    id=section_id,
                    label=f"{paper_id} §{section}",
                    scale=1,
                    layer=Layer.STRUCTURAL,
                    metadata={
                        "node_type": "paper_section",
                        "paper_id": paper_id,
                        "section": section,
                    },
                )
            # Paper CONTAINS section (Genus relation)
            edges.append(Edge(
                source=paper_id, target=section_id,
                slot=Slot.CONTAINER, confidence=Confidence.EXTRACTED,
                scale_from=2, scale_to=1,
                evidence=f"EXPERIMENTS-LOG.md row for {did} feeds {paper_id}.§{section}",
            ))
            # Section CAUSES experiment (efficient cause: section motivates experiment)
            edges.append(Edge(
                source=section_id, target=did,
                slot=Slot.CAUSE, confidence=Confidence.EXTRACTED,
                scale_from=1, scale_to=1,
                evidence=f"experiment {did} feeds paper section {paper_id}.§{section}",
            ))

        # ---- Pre-reg edges (Specification: experiment instantiates pre-reg prediction) ----
        for prereg in _extract_preregs(prereg_raw):
            if prereg not in nodes:
                nodes[prereg] = Node(
                    id=prereg,
                    label=f"Pre-reg {prereg}",
                    scale=1,
                    layer=Layer.STRUCTURAL,
                    metadata={"node_type": "prereg_prediction"},
                )
            # D-XXX INSTANTIATES Pre-reg P-XXX (type axis — instance of specification)
            edges.append(Edge(
                source=did, target=prereg,
                slot=Slot.INSTANTIATION, confidence=Confidence.EXTRACTED,
                scale_from=1, scale_to=1,
                evidence=f"D {did} pre-reg column lists {prereg}",
            ))

        # ---- Predecessor edges (supersession lineage) ----
        lineage_match = LINEAGE_RE.match(did)
        if lineage_match:
            parent_did = lineage_match.group(1)
            # Whitehead negative prehension iff state indicates rejection
            neg = _is_estado_negative_prehension(estado_raw)
            edges.append(Edge(
                source=did, target=parent_did,
                slot=Slot.PREDECESSOR, confidence=Confidence.EXTRACTED,
                scale_from=1, scale_to=1,
                evidence=f"D-ID suffix indicates {did} extends or supersedes {parent_did}",
                negative_prehension=neg,
            ))

    return list(nodes.values()), edges


def extract(graph_or_path) -> dict:
    """Convenience entry point — parse + return summary stats.

    Can be called with a TensegrityGraph (will populate it) OR with a Path
    (will return nodes + edges without populating).
    """
    from ..builder import TensegrityGraph  # local import to avoid circular

    project_root = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
    log_path = project_root / "LINEAS CONSOLIDADAS DE TRABAJO" / "EXPERIMENTS-LOG.md"
    nodes, edges = parse_experiments_log(log_path)

    if isinstance(graph_or_path, TensegrityGraph):
        graph = graph_or_path
        added_nodes = 0
        added_edges = 0
        for n in nodes:
            if n.id not in graph._nodes:
                graph.add_node(n)
                added_nodes += 1
        for e in edges:
            try:
                graph.add_edge(e)
                added_edges += 1
            except (KeyError, ValueError):
                continue
        return {
            "extractor": "experiments_log",
            "nodes_added": added_nodes,
            "edges_added": added_edges,
            "nodes_parsed": len(nodes),
            "edges_parsed": len(edges),
        }
    else:
        return {
            "extractor": "experiments_log",
            "nodes_parsed": len(nodes),
            "edges_parsed": len(edges),
            "nodes": nodes,
            "edges": edges,
        }


if __name__ == "__main__":
    import json
    result = extract(None)
    print(f"Parsed {result['nodes_parsed']} nodes + {result['edges_parsed']} edges")
    if result["nodes"]:
        print("\nSample node:")
        print(json.dumps(result["nodes"][0].to_dict(), indent=2, default=str))


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='experiments_log',
    scale=2,
    aristotelian_cause='material',
    container=['core.extractors'],
    substrate=['core.schema', 'core.builder'],
    effect=['D-XXX nodes + paper section nodes + initial CONTAINER edges'],
    peer_coherent=['prereg', 'cross_cuts', 'paper_drafts'],
)
