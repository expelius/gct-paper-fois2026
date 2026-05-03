"""Extractor protocol + DAG orchestration helpers.

The Tensegrity knowledge-graph extractors share a simple interface:

  - Module-level `extract(graph) -> dict[str, Any]` function (the work)
  - Module-level `REQUIRES: list[str]` constant (which other extractors must
    have run first; default empty list = no dependencies, can run early)

This module defines the protocol formally + provides a topological-sort
orchestrator (`build_extractor_order`) that resolves the dependency DAG and
fails loudly on missing-dependency or cycle errors.

Migrating an extractor to use this is one-line: add `REQUIRES = ['foo']` at
the top of the module. Extractors that don't declare REQUIRES default to no
dependencies (current implicit behavior).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExtractorModule(Protocol):
    """Structural type for a Tensegrity extractor module.

    Any module satisfying this protocol can be plugged into `run_all`. The
    convention is module-level (not class-based) because each extractor is
    a single coherent file; classes would add ceremony without adding value.
    """
    REQUIRES: list[str]
    def extract(self, graph) -> dict: ...


def build_extractor_order(extractor_modules: list) -> list:
    """Topological sort over the extractor DAG.

    Args:
        extractor_modules: list of imported modules. Each may define a
            module-level `REQUIRES` list of strings naming other extractors
            (by their short name — the last `.`-separated component).

    Returns:
        A new list of the same modules in dependency-respecting order.

    Raises:
        ValueError: if the dependency graph has a cycle or a REQUIRES entry
            names an unknown extractor.
    """
    name_to_module = {m.__name__.split(".")[-1]: m for m in extractor_modules}
    deps = {
        name: list(getattr(m, "REQUIRES", []))
        for name, m in name_to_module.items()
    }

    # Validate that every declared dependency exists
    for name, reqs in deps.items():
        for r in reqs:
            if r not in name_to_module:
                raise ValueError(
                    f"Extractor '{name}' REQUIRES '{r}' which is not in the "
                    f"registered extractor list. Known extractors: "
                    f"{sorted(name_to_module)}"
                )

    # Kahn's algorithm — topological sort with cycle detection.
    #
    # ORDERING POLICY (round-8 review #9): within a single dependency layer
    # (extractors with the same set of unresolved deps), we sort
    # ALPHABETICALLY for determinism. Two consequences:
    #
    #   1. Build outputs are reproducible across runs.
    #   2. Renaming an extractor changes the within-layer position. If
    #      ordering between two extractors matters semantically, encode it
    #      via REQUIRES, not via name choice. Alphabetical sort is
    #      explicitly NOT a stable contract for cross-extractor ordering.
    ordered: list = []
    remaining = dict(deps)   # copy
    while remaining:
        ready = [n for n, r in remaining.items() if not r]
        if not ready:
            raise ValueError(
                f"Cycle detected in extractor dependency DAG. "
                f"Remaining: {remaining}"
            )
        ready.sort()         # alphabetical within layer (see policy comment above)
        for n in ready:
            ordered.append(name_to_module[n])
            del remaining[n]
            for other_reqs in remaining.values():
                if n in other_reqs:
                    other_reqs.remove(n)
    return ordered


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='extractors_base',
    scale=1,
    aristotelian_cause='formal',
    container=['core.extractors'],
    specification=['ExtractorModule protocol + topological sort'],
    description='Extractor interface + DAG resolver',
)
