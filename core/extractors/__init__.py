"""Extractors package — orchestrates Phase 1+ structural extraction.

Each module exposes `extract(graph)` + a module-level `REQUIRES: list[str]`
declaring its dependencies. The orchestrator topologically sorts these and
runs them in dependency-respecting order. Cycle detection + missing-dependency
errors fail the build loudly.

To add a new extractor:
  1. Create core/extractors/foo.py with `REQUIRES = [...]` + `def extract(graph)`
  2. Import it in EXTRACTOR_MODULES below
  3. Re-run the build — topological sort places it correctly
"""
from . import (
    experiments_log,
    prereg,
    project_graph,
    memory,
    paper_drafts,
    cross_cuts,
    results_jsons,
    articulos_base,
    concepts,
    maxims_as_nodes,
    code_holons,
    code_implements,            # CODE-edge wirer: code_holon → maxim_* (closes Slot.CODE)
    ghost_experiments,          # reconcile disk results vs EXPERIMENTS-LOG
    operational_distinctions,   # JCC/PJC: D-ID → OperationalDistinction → paper_section
    epistemic_frontier,         # EFR: persistently unstabilised claims as first-class nodes
)
from ._base import build_extractor_order


# All registered extractor modules. Order here doesn't matter — the
# topological sort over REQUIRES determines actual run order.
EXTRACTOR_MODULES = [
    experiments_log,
    prereg,
    project_graph,
    cross_cuts,
    paper_drafts,
    memory,
    articulos_base,
    results_jsons,
    concepts,
    maxims_as_nodes,
    code_holons,                # MAXIMALIST: emit the project's own code as IVM holons
    code_implements,            # closes CODE slot: code_holon → maxim_* (REQUIRES code_holons + maxims_as_nodes)
    ghost_experiments,          # emit ghost nodes for unregistered results dirs
    operational_distinctions,   # JCC/PJC: REQUIRES=['experiments_log'] — runs after
    epistemic_frontier,         # EFR: REQUIRES=['experiments_log','paper_drafts'] — runs last
]

# Resolved at import time — fails immediately if there's a cycle or missing
# dependency in any module's REQUIRES list. This is the new authoritative
# ordering; the old hand-maintained EXTRACTORS_IN_ORDER constant is kept as
# an alias for backwards compatibility.
EXTRACTORS_IN_ORDER = build_extractor_order(EXTRACTOR_MODULES)


def run_all(graph) -> list[dict]:
    """Run all extractors in order, return list of stats dicts.

    Each extractor's add_node/add_edge calls are wrapped in
    `graph.with_provenance(extractor_name)` so every node and edge gets stamped
    with which extractor created it (queryable post-hoc, useful for debugging).
    """
    stats = []
    for ex in EXTRACTORS_IN_ORDER:
        ext_name = ex.__name__.split(".")[-1]
        try:
            with graph.with_provenance(ext_name):
                r = ex.extract(graph)
            stats.append(r)
        except Exception as e:
            stats.append({"extractor": ex.__name__, "error": str(e)})
    return stats


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='extractors',
    scale=3,
    aristotelian_cause='efficient',
    container=['core'],
    substrate=['core.extractors._base'],
    effect=['runs all extractors in topological order'],
    description='Extractor orchestrator — 15 extractors incl. operational_distinctions (JCC/PJC) + epistemic_frontier (EFR/DLL, 2026-05-02) + code_implements (CODE slot wirer, 2026-05-02)',
)
