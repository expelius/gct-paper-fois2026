"""Extractor for OperationalDistinction nodes — JCC/PJC framework.

Reads EXPERIMENTS-LOG.md for D-ID → script mappings, then produces
OperationalDistinction nodes via two complementary strategies:

Primary (explicit):
    Parse DISTINCTIONS_TARGETED fields from TRACE headers in exp_*.py files.
    These are present only in experiments designed after 2026-05-01 (JCC adoption).

Fallback (inferred):
    For experiments WITHOUT a DISTINCTIONS_TARGETED field, infer a single
    generic distinction from the experiment's estado (judgment_state mapping)
    and feeds columns. This populates the KG for all 315+ existing D-IDs
    so queries like "which distinctions remain AMBIGUOUS?" work immediately.

Yields:
    - operational_distinction nodes (scale=1, Layer.FUNCTIONAL)
    - CAUSE edges:              D-ID → OperationalDistinction
                                (experiment stabilizes the distinction)
    - PEER_CONTRADICTORY edges: D-ID → OperationalDistinction
                                (experiment contradicts / leaves unstable)
    - EFFECT edges:             OperationalDistinction → paper_section
                                (distinction unlocked → paper claim follows)

Design notes:
    - REQUIRES = ['experiments_log'] so D-ID nodes already exist when we
      add edges to them.
    - Distinction IDs are deterministic: DIST_{did}_{n} for explicit, or
      DIST_{did} for inferred. This makes rebuilds idempotent.
    - judgment_state is inferred from estado (OK → STABLE, FAIL →
      CONTRADICTORY, QUEUED/RUN → MISSING_EVIDENCE, INCONCLUSIVE → AMBIGUOUS).
    - For explicit distinctions, state_after from the TRACE header overrides
      the inference (a QUEUED experiment might already declare AMBIGUOUS→STABLE
      as its target — the target is the intended post-experiment state, not
      the current project state).

Authored: 2026-05-01 — JCC/PJC absorption
Source: Pattern-to-Judgment Computation (Patel 2026b) §4.2, §6.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterator

try:
    from ..node_types import make_operational_distinction
    from ..schema import Confidence, Edge, Layer, Node, Slot
except ImportError:
    # Direct execution fallback — add knowledge-graph/ to sys.path first
    import sys as _sys
    from pathlib import Path as _Path
    _kg_root = _Path(__file__).resolve().parents[2]
    if str(_kg_root) not in _sys.path:
        _sys.path.insert(0, str(_kg_root))
    from core.node_types import make_operational_distinction
    from core.schema import Confidence, Edge, Layer, Node, Slot

REQUIRES: list[str] = ["experiments_log"]

# ─── project paths ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(r"C:/Users/juand/OneDrive/Documentos/REPOSITORIOS VS CODE/Tensegrity")
LOG_PATH = PROJECT_ROOT / "LINEAS CONSOLIDADAS DE TRABAJO" / "EXPERIMENTS-LOG.md"
FASE5_PATH = PROJECT_ROOT / "LINEAS DE INVESTIGACIÓN" / "LINEA A" / "FASE 5"

# ─── regexes ────────────────────────────────────────────────────────────────

# Match log table rows — mirrors the pattern in experiments_log.py
ROW_RE = re.compile(
    r"^\|\s*"
    r"(?P<did>D-\d+[a-z]?)\s*\|\s*"
    r"(?P<date>[^|]*?)\s*\|\s*"
    r"(?P<script>[^|]*?)\s*\|\s*"
    r"(?P<carril>[^|]*?)\s*\|\s*"
    r"(?P<seeds>[^|]*?)\s*\|\s*"
    r"(?P<feeds>[^|]*?)\s*\|\s*"
    r"(?P<prereg>[^|]*?)\s*\|\s*"
    r"(?P<estado>[^|]*?)\s*\|\s*"
    r"(?P<resultado>[^|]*?)\s*\|?\s*$",
    re.MULTILINE,
)

# Match TRACE block header in Python scripts
TRACE_START_RE = re.compile(r"#\s*TRACE\b")
TRACE_END_RE = re.compile(r"#\s*[═=]{10,}")

# Match DISTINCTIONS_TARGETED field inside a TRACE block.
# Handles single-line and multi-line continuation:
#   #   DISTINCTIONS_TARGETED : value here
#   #                           continuation here
DIST_FIELD_RE = re.compile(
    r"#\s*DISTINCTIONS_TARGETED\s*:\s*(?P<value>[^\n]*)",
    re.IGNORECASE,
)
# Continuation line of DISTINCTIONS_TARGETED (indented comment, no UPPERCASE: pattern)
CONTINUATION_RE = re.compile(
    r"^#\s{4,}(?!(?:[A-Z_]{3,}\s*:))(?P<cont>.+)",
)
# New TRACE field (signals end of a multi-line DISTINCTIONS_TARGETED)
TRACE_FIELD_START_RE = re.compile(r"^#\s+[A-Z_]{3,}\s*:")

# Parse individual D{n}: lines within DISTINCTIONS_TARGETED value.
# Formats:
#   D1: HNC basin rigidity vs GRU (MISSING_EVIDENCE→STABLE) — P4.§5.1
#   D2: substrate-independence κ-ETF — state: AMBIGUOUS→STABLE
#   EXPLORATORY — generates candidate distinctions
EXPLICIT_DIST_RE = re.compile(
    r"D\d+\s*:\s*(?P<label>[^(—\n]+?)"   # label before state or dash
    r"(?:"
    r"\s*[(\[]?\s*(?P<state_before>STABLE|AMBIGUOUS|MISSING_EVIDENCE|CONTRADICTORY)"
    r"\s*[→→→-]+\s*"
    r"(?P<state_after>STABLE|AMBIGUOUS|MISSING_EVIDENCE|CONTRADICTORY)"
    r"\s*[)\]]?"
    r")?"
    r"(?:\s*[-—]+\s*(?P<claim>P\d+\.§\S+))?",
    re.IGNORECASE,
)

# Paper section refs re-used for EFFECT edges
PAPER_SECTION_RE = re.compile(
    r"P(\d+)(?:\s+v[\w.]+)?\s*\.?\s*§\s*([^\s,)(§|]+)",
    re.IGNORECASE,
)


# ─── estado → judgment_state mapping ─────────────────────────────────────────

def _estado_to_jstate(estado_raw: str) -> str:
    """Map noisy EXPERIMENTS-LOG estado to JCC judgment_state."""
    s = estado_raw.upper()
    s = re.sub(r"\*+|`+", "", s).strip()
    if "OK" in s:
        return "STABLE"
    if "FAIL" in s or "REJECT" in s:
        return "CONTRADICTORY"
    if "INCONCLUSIVE" in s or "AMBIGUOUS" in s:
        return "AMBIGUOUS"
    if "SUPERSEDED" in s:
        return "STABLE"   # superseded experiments did their work; distinction was settled
    return "MISSING_EVIDENCE"   # QUEUED, RUN, UNKNOWN


# ─── TRACE header parsing ─────────────────────────────────────────────────────

def _read_trace_block(script_path: Path) -> str | None:
    """Return the raw text of the TRACE block, or None if absent."""
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None

    lines = text.splitlines()
    in_trace = False
    block_lines: list[str] = []

    for line in lines:
        if not in_trace:
            if TRACE_START_RE.search(line):
                in_trace = True
                block_lines.append(line)
        else:
            if TRACE_END_RE.search(line):
                break
            block_lines.append(line)

    return "\n".join(block_lines) if block_lines else None


def _parse_distinctions_field(trace_block: str) -> str | None:
    """Extract the full DISTINCTIONS_TARGETED value from a TRACE block.

    Handles single-line and multi-line (continued) values.
    """
    m = DIST_FIELD_RE.search(trace_block)
    if not m:
        return None

    value = m.group("value").strip()

    # Check if value spans multiple continuation lines
    block_lines = trace_block[m.end():].splitlines()
    for line in block_lines:
        if TRACE_FIELD_START_RE.match(line):
            break   # next TRACE field — stop
        cont_m = CONTINUATION_RE.match(line)
        if cont_m:
            cont = cont_m.group("cont").strip()
            # Skip the template's own example/instruction lines
            if cont.startswith("List the") or cont.startswith("Format:") \
               or cont.startswith("Example:") or cont.startswith("If purely"):
                continue
            value = (value + " " + cont).strip() if value else cont
        else:
            break   # non-continuation line

    return value if value else None


def _parse_explicit_distinctions(
    did: str, raw_value: str
) -> list[dict]:
    """Parse D{n}: entries from the DISTINCTIONS_TARGETED raw value.

    Returns list of dicts with keys:
        label, option_a, option_b, state_before, state_after, claim
    """
    if not raw_value:
        return []
    raw_upper = raw_value.upper().strip()

    # Purely exploratory — no distinctions to parse
    if raw_upper.startswith("EXPLORATORY"):
        return [{
            "label": f"{did}: exploratory — generates candidate distinctions",
            "option_a": "unknown outcome A",
            "option_b": "unknown outcome B",
            "state_before": "MISSING_EVIDENCE",
            "state_after": "MISSING_EVIDENCE",
            "claim": None,
            "exploratory": True,
        }]

    results = []
    for m in EXPLICIT_DIST_RE.finditer(raw_value):
        label = m.group("label").strip().rstrip("-—").strip()
        if not label:
            continue

        # Split label into option_a / option_b on " vs " if present
        vs_split = re.split(r"\s+vs\.?\s+", label, maxsplit=1, flags=re.IGNORECASE)
        if len(vs_split) == 2:
            option_a, option_b = vs_split[0].strip(), vs_split[1].strip()
        else:
            option_a = label
            option_b = f"NOT ({label})"

        state_before = (m.group("state_before") or "AMBIGUOUS").upper()
        state_after = (m.group("state_after") or "STABLE").upper()
        claim = m.group("claim")  # may be None

        results.append({
            "label": label,
            "option_a": option_a,
            "option_b": option_b,
            "state_before": state_before,
            "state_after": state_after,
            "claim": claim,
            "exploratory": False,
        })

    return results


# ─── script file lookup ───────────────────────────────────────────────────────

def _find_script(script_name: str) -> Path | None:
    """Locate a script file under FASE 5 (and fallback to FASE 4 / project root).

    The log stores just the filename without path; we glob for it.
    """
    if not script_name or script_name == "—" or script_name.lower() == "n/a":
        return None
    # Strip backticks and whitespace
    script_name = script_name.strip().strip("`")
    if not script_name.endswith(".py"):
        return None

    # Search FASE 5 first (most experiments live here)
    for candidate in FASE5_PATH.rglob(script_name):
        return candidate

    # Fallback: glob from project root (FASE 4, etc.)
    for candidate in PROJECT_ROOT.rglob(script_name):
        return candidate

    return None


# ─── core extraction ──────────────────────────────────────────────────────────

def _make_distinct_id(did: str, n: int) -> str:
    """Deterministic node ID for an explicit distinction."""
    return f"DIST_{did}_{n}"


def _make_inferred_id(did: str) -> str:
    """Deterministic node ID for an inferred (fallback) distinction."""
    return f"DIST_{did}"


def _paper_section_node_id(paper_id: str, section: str) -> str:
    """Match the ID format used by experiments_log extractor."""
    return f"{paper_id}_section_{section.replace('.', '_').replace('§', '')}"


def _extract_paper_sections(text: str) -> list[tuple[str, str]]:
    """Parse P#.§X refs → [(paper_id, section), ...]."""
    return [
        (f"P{m.group(1)}", m.group(2))
        for m in PAPER_SECTION_RE.finditer(text)
    ]


def extract(graph) -> dict:
    """Main entry point — populate graph with OperationalDistinction nodes + edges."""
    if not LOG_PATH.exists():
        return {"extractor": "operational_distinctions", "error": "EXPERIMENTS-LOG.md not found"}

    text = LOG_PATH.read_text(encoding="utf-8")
    rows = list(ROW_RE.finditer(text))

    nodes_added = 0
    edges_added = 0
    explicit_count = 0
    inferred_count = 0
    skipped_no_script = 0
    skipped_no_did_node = 0

    for m in rows:
        did = m.group("did")
        script_raw = m.group("script").strip().replace("`", "")
        feeds_raw = m.group("feeds")
        estado_raw = m.group("estado")
        resultado_raw = m.group("resultado").strip()

        # D-ID node must already exist (experiments_log extractor)
        if did not in graph._nodes:
            skipped_no_did_node += 1
            continue

        jstate_from_estado = _estado_to_jstate(estado_raw)

        # ── Strategy 1: explicit DISTINCTIONS_TARGETED in TRACE header ──
        explicit_parsed: list[dict] = []
        script_path = _find_script(script_raw)

        if script_path:
            trace_block = _read_trace_block(script_path)
            if trace_block:
                raw_value = _parse_distinctions_field(trace_block)
                if raw_value:
                    explicit_parsed = _parse_explicit_distinctions(did, raw_value)

        if explicit_parsed:
            explicit_count += 1
            for n_idx, entry in enumerate(explicit_parsed):
                dist_id = _make_distinct_id(did, n_idx + 1)

                # Current judgment_state = what the experiment actually achieved
                # If OK → state_after is now real; else state_before still holds
                if jstate_from_estado == "STABLE":
                    current_jstate = entry["state_after"]
                    stabilized_by = [did]
                    contradicted_by = []
                elif jstate_from_estado == "CONTRADICTORY":
                    current_jstate = "CONTRADICTORY"
                    stabilized_by = []
                    contradicted_by = [did]
                else:
                    current_jstate = entry["state_before"]
                    stabilized_by = []
                    contradicted_by = []

                # Build paper claims list
                paper_claims: list[str] = []
                if entry["claim"]:
                    paper_claims.append(entry["claim"])
                # Also harvest from feeds column
                for p_id, p_sec in _extract_paper_sections(feeds_raw):
                    claim_str = f"{p_id}.§{p_sec}"
                    if claim_str not in paper_claims:
                        paper_claims.append(claim_str)

                # Create the distinction node
                description = (
                    f"Explicit. From TRACE header of {script_raw}. "
                    f"Target: {entry['state_before']}→{entry['state_after']}."
                )
                dist_node = make_operational_distinction(
                    distinction_id=dist_id,
                    label=f"{entry['label']} [{current_jstate}]",
                    option_a=entry["option_a"],
                    option_b=entry["option_b"],
                    judgment_state=current_jstate,
                    stabilized_by=stabilized_by,
                    contradicted_by=contradicted_by,
                    paper_claims_unlocked=paper_claims,
                    description=description,
                    extra_metadata={
                        "source": "explicit_trace_header",
                        "target_state_before": entry["state_before"],
                        "target_state_after": entry["state_after"],
                        "parent_experiment": did,
                        "exploratory": entry.get("exploratory", False),
                    },
                )

                if dist_id not in graph._nodes:
                    graph.add_node(dist_node)
                    nodes_added += 1

                # CAUSE edge: D-ID → OperationalDistinction
                # (experiment is the efficient cause of stabilization)
                cause_slot = (
                    Slot.PEER_CONTRADICTORY
                    if jstate_from_estado == "CONTRADICTORY"
                    else Slot.CAUSE
                )
                _try_add_edge(graph, Edge(
                    source=did, target=dist_id,
                    slot=cause_slot,
                    confidence=Confidence.EXTRACTED,
                    scale_from=1, scale_to=1,
                    evidence=f"TRACE DISTINCTIONS_TARGETED: {did} targets distinction {dist_id}",
                ))
                edges_added += 1

                # EFFECT edges: OperationalDistinction → paper_section
                for claim_str in paper_claims:
                    p_parts = PAPER_SECTION_RE.search(claim_str)
                    if not p_parts:
                        continue
                    paper_id = f"P{p_parts.group(1)}"
                    section = p_parts.group(2)
                    sec_node_id = _paper_section_node_id(paper_id, section)
                    if sec_node_id in graph._nodes:
                        _try_add_edge(graph, Edge(
                            source=dist_id, target=sec_node_id,
                            slot=Slot.EFFECT,
                            confidence=Confidence.EXTRACTED,
                            scale_from=1, scale_to=1,
                            evidence=f"Distinction {dist_id} unlocks claim in {paper_id}.§{section}",
                        ))
                        edges_added += 1

        else:
            # ── Strategy 2: fallback — infer a single distinction from estado ──
            if not script_path:
                skipped_no_script += 1

            inferred_count += 1
            dist_id = _make_inferred_id(did)

            # Infer label from resultado_short
            short = resultado_raw[:120].strip() if resultado_raw else f"{did} hypothesis"
            short = re.sub(r"\*+", "", short).strip()

            # Best-effort option split from resultado
            vs_parts = re.split(r"\s+vs\.?\s+", short, maxsplit=1, flags=re.IGNORECASE)
            if len(vs_parts) == 2:
                opt_a, opt_b = vs_parts[0].strip()[:80], vs_parts[1].strip()[:80]
            else:
                opt_a = short[:80] or f"{did} confirmed"
                opt_b = f"{did} refuted"

            stabilized_by = [did] if jstate_from_estado == "STABLE" else []
            contradicted_by = [did] if jstate_from_estado == "CONTRADICTORY" else []

            paper_claims = [
                f"{p}.§{s}"
                for p, s in _extract_paper_sections(feeds_raw)
            ]

            dist_node = make_operational_distinction(
                distinction_id=dist_id,
                label=f"{did}: {short[:60]}... [{jstate_from_estado}]",
                option_a=opt_a,
                option_b=opt_b,
                judgment_state=jstate_from_estado,
                stabilized_by=stabilized_by,
                contradicted_by=contradicted_by,
                paper_claims_unlocked=paper_claims,
                description=(
                    f"Inferred from estado={jstate_from_estado}. "
                    f"No DISTINCTIONS_TARGETED field found in TRACE header. "
                    f"Add explicit field to {script_raw or 'script'} for precision."
                ),
                extra_metadata={
                    "source": "inferred_from_estado",
                    "parent_experiment": did,
                    "resultado_short": short[:200],
                },
            )

            if dist_id not in graph._nodes:
                graph.add_node(dist_node)
                nodes_added += 1

            # CAUSE / PEER_CONTRADICTORY edge: D-ID → OperationalDistinction
            cause_slot = (
                Slot.PEER_CONTRADICTORY
                if jstate_from_estado == "CONTRADICTORY"
                else Slot.CAUSE
            )
            _try_add_edge(graph, Edge(
                source=did, target=dist_id,
                slot=cause_slot,
                confidence=Confidence.INFERRED,
                scale_from=1, scale_to=1,
                evidence=f"Inferred: estado={jstate_from_estado} implies {did} "
                         f"{'stabilizes' if cause_slot == Slot.CAUSE else 'contradicts'} {dist_id}",
            ))
            edges_added += 1

            # EFFECT edges to paper sections
            for claim_str in paper_claims:
                p_parts = PAPER_SECTION_RE.search(claim_str)
                if not p_parts:
                    continue
                paper_id = f"P{p_parts.group(1)}"
                section = p_parts.group(2)
                sec_node_id = _paper_section_node_id(paper_id, section)
                if sec_node_id in graph._nodes:
                    _try_add_edge(graph, Edge(
                        source=dist_id, target=sec_node_id,
                        slot=Slot.EFFECT,
                        confidence=Confidence.INFERRED,
                        scale_from=1, scale_to=1,
                        evidence=f"Inferred: {dist_id} feeds {paper_id}.§{section}",
                    ))
                    edges_added += 1

    return {
        "extractor": "operational_distinctions",
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "explicit_distinctions": explicit_count,
        "inferred_distinctions": inferred_count,
        "skipped_no_script": skipped_no_script,
        "skipped_no_did_node": skipped_no_did_node,
        "total_rows_processed": len(rows),
    }


def _try_add_edge(graph, edge: Edge) -> bool:
    """Add edge, silently swallowing KeyError (missing node) and ValueError (invalid)."""
    try:
        graph.add_edge(edge)
        return True
    except (KeyError, ValueError):
        return False


# ── convenience: query unstabilized distinctions ──────────────────────────────

def query_unstabilized(graph) -> list[Node]:
    """Return all OperationalDistinction nodes NOT in STABLE state.

    Wraps get_unstabilized_distinctions() from node_types for convenience.
    Usage:
        from knowledge_graph.core.extractors.operational_distinctions import query_unstabilized
        unstable = query_unstabilized(graph)
    """
    return [
        n for n in graph._nodes.values()
        if (
            n.metadata.get("node_type") == "operational_distinction"
            and n.metadata.get("judgment_state") != "STABLE"
        )
    ]


def query_by_judgment_state(graph, state: str) -> list[Node]:
    """Return OperationalDistinction nodes with the given judgment_state."""
    return [
        n for n in graph._nodes.values()
        if (
            n.metadata.get("node_type") == "operational_distinction"
            and n.metadata.get("judgment_state") == state.upper()
        )
    ]


def summary(graph) -> dict:
    """Return a summary dict of all OperationalDistinction nodes by state.

    Example output:
        {
            "total": 312,
            "STABLE": 198,
            "MISSING_EVIDENCE": 72,
            "AMBIGUOUS": 31,
            "CONTRADICTORY": 11,
            "explicit": 5,
            "inferred": 307,
        }
    """
    all_dists = [
        n for n in graph._nodes.values()
        if n.metadata.get("node_type") == "operational_distinction"
    ]
    from collections import Counter
    state_counts = Counter(n.metadata.get("judgment_state", "UNKNOWN") for n in all_dists)
    source_counts = Counter(n.metadata.get("source", "unknown") for n in all_dists)
    return {
        "total": len(all_dists),
        **dict(state_counts),
        "explicit": source_counts.get("explicit_trace_header", 0),
        "inferred": source_counts.get("inferred_from_estado", 0),
    }


if __name__ == "__main__":
    """Standalone test — build a minimal graph and run the extractor."""
    import sys
    # When run directly, add parent dirs to path so absolute imports work
    _here = Path(__file__).resolve()
    _kg_root = _here.parents[2]  # knowledge-graph/
    if str(_kg_root) not in sys.path:
        sys.path.insert(0, str(_kg_root))

    from core.builder import TensegrityGraph
    from core.extractors import experiments_log as exp_log

    g = TensegrityGraph()

    # Run experiments_log first (REQUIRES dependency)
    with g.with_provenance("experiments_log"):
        exp_log.extract(g)

    # Now run this extractor
    with g.with_provenance("operational_distinctions"):
        stats = extract(g)

    print("=" * 60)
    print("OperationalDistinctions extractor — standalone test")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()

    dist_summary = summary(g)
    print("Distinction summary:")
    for k, v in dist_summary.items():
        print(f"  {k}: {v}")

    unstable = query_unstabilized(g)
    print(f"\nUnstabilized distinctions: {len(unstable)}")
    for n in unstable[:5]:
        print(f"  {n.id} [{n.metadata['judgment_state']}] — {n.label[:70]}")
    if len(unstable) > 5:
        print(f"  ... and {len(unstable) - 5} more")


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='operational_distinctions',
    scale=1,
    aristotelian_cause='formal',
    container=['core.extractors'],
    substrate=['core.schema', 'core.node_types', 'core.extractors.experiments_log'],
    effect=['OperationalDistinction nodes + CAUSE/EFFECT/PEER_CONTRADICTORY edges'],
    peer_coherent=['experiments_log', 'paper_drafts'],
    description='JCC/PJC: extracts distinction nodes that bridge D-IDs → paper claims',
)
