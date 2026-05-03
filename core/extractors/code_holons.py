"""code_holons — read every module's __holon__ declaration and emit them as nodes.

This is THE maximalist move: the project's code becomes part of its own
knowledge graph. Each module that declares `__holon__ = HolonMeta(...)`
becomes a structural node at scale 3 (or whatever scale it self-declares).
The 12 IVM-slot relations declared in the HolonMeta become edges.

After this extractor runs, the same maxim layer that validates research-data
relationships also validates code-module relationships. The graph contains
its own structural laws AND its own implementation; the carousel can render
both layers.
"""
from __future__ import annotations

REQUIRES: list[str] = ["maxims_as_nodes"]   # runs last so all other holons exist first

import importlib
import pkgutil
from pathlib import Path

from ..schema import Confidence, Edge, Layer, Node, Slot
from ..holon_meta import HolonMeta


# Slot name → (Slot enum, direction). Direction tells us whether to emit
# the edge as A → declared_target (when A IS the source of the relation)
# or declared_target → A (when the declared target is the source).
#
# Convention from existing extractors (experiments_log.py et al):
#   - paper → section [CONTAINER]: source IS the container (higher scale)
#   - section → experiment [CAUSE]: source IS the cause
#   - did → parent_did [PREDECESSOR]: target IS the predecessor (earlier)
#
# So when A declares `container=[B]` semantically meaning "B contains A",
# we must emit B → A [CONTAINER] with B as source. direction='from_target'.
#
# When A declares `effect=[B]` meaning "A has B as its effect" (A causes B),
# we emit A → B [CAUSE]. The slot system reciprocates as A.EFFECT.
# direction='to_target', slot=CAUSE.
_SLOT_BY_FIELD: dict[str, tuple[Slot, str]] = {
    # field_name → (slot to emit, direction)
    # direction='from_target': declared_target is source (B → A)
    # direction='to_target':   A is source (A → declared_target)
    #
    # Round-8 review fixes applied: `instantiation` now uses Slot.INSTANTIATION
    # (not SPECIFICATION) so the distinction is preserved; `successor` now uses
    # Slot.SUCCESSOR (was PREDECESSOR with reverse direction, which the
    # validator read as the inverse temporal claim).
    "container":          (Slot.CONTAINER, "from_target"),
    "substrate":          (Slot.SUBSTRATE, "from_target"),
    "cause":              (Slot.CAUSE, "from_target"),       # A's cause IS B → B causes A
    "effect":             (Slot.CAUSE, "to_target"),         # A causes B → A→B[CAUSE], reciprocates A.EFFECT
    "peer_coherent":      (Slot.PEER_COHERENT, "to_target"),
    "peer_contradictory": (Slot.PEER_CONTRADICTORY, "to_target"),
    "specification":      (Slot.SPECIFICATION, "to_target"), # A's form IS B → A→B[SPECIFICATION]
    "instantiation":      (Slot.INSTANTIATION, "to_target"), # A's instances ARE B → A→B[INSTANTIATION]
    "predecessor":        (Slot.PREDECESSOR, "to_target"),   # A→B[PREDECESSOR]: target B is the predecessor of A
    "successor":          (Slot.SUCCESSOR, "to_target"),     # A→B[SUCCESSOR]:   target B is the successor of A
}


def _walk_modules() -> list:
    """Walk all submodules of `core` and collect their __holon__ if present.

    Returns: list of (module_path, module_object, HolonMeta, active_since_iso)

    The active_since uses git's first-commit-time-of-the-file as the
    authoritative authoring date. Falls back to file mtime, then now().
    Round-8 review #5 fix: file mtime alone collapses to checkout-time on
    fresh clones, defeating the temporal axis. Git commit time is stable
    across checkouts.
    """
    import core
    from datetime import datetime
    import subprocess
    found = []
    seen_module_paths = set()

    def authoring_iso(mod) -> str:
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            return datetime.now().isoformat()
        path = Path(mod_file)
        # Try git: use the file's earliest commit (first-author-time).
        try:
            r = subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%aI", "--", path.name],
                cwd=str(path.parent),
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0 and r.stdout.strip():
                # First line = earliest commit's author-time (ISO 8601)
                return r.stdout.strip().splitlines()[-1]
        except Exception:
            pass
        # Fallback: file mtime
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        except Exception:
            return datetime.now().isoformat()

    def visit(pkg):
        for _, name, is_pkg in pkgutil.iter_modules(pkg.__path__):
            full = f"{pkg.__name__}.{name}"
            if full in seen_module_paths:
                continue
            seen_module_paths.add(full)
            try:
                mod = importlib.import_module(full)
            except Exception:
                continue
            holon = getattr(mod, "__holon__", None)
            if isinstance(holon, HolonMeta):
                found.append((full, mod, holon, authoring_iso(mod)))
            if is_pkg:
                visit(mod)

    visit(core)
    holon = getattr(core, "__holon__", None)
    if isinstance(holon, HolonMeta):
        found.append(("core", core, holon, authoring_iso(core)))
    return found


def _holon_node_id(name: str) -> str:
    return f"holon_code_{name.lower()}"


def extract(graph) -> dict:
    """Walk all core modules; emit holon nodes + slot-declared edges.

    Edge directions follow the existing extractor convention. See
    `_SLOT_BY_FIELD` table — when holon A declares `field=[B]`, the edge
    is emitted with the right source/target order so the maxim layer's
    scale + anteriority validators give correct results.
    """
    nodes_added = 0
    edges_added = 0
    holons_found = _walk_modules()

    # Step 1 — register every code holon as a node, using the file's mtime
    # for active_since (so the temporal axis reflects real authoring order
    # rather than build-run order).
    for module_path, _mod, h, mtime_iso in holons_found:
        nid = _holon_node_id(h.name)
        if nid in graph._nodes:
            continue
        node = Node(
            id=nid,
            label=f"⟨code⟩ {h.name}",
            scale=h.scale,
            layer=Layer.STRUCTURAL,
            metadata={
                "node_type": "code_holon",
                "module_path": module_path,
                "holon_name": h.name,
                "code": h.code,
                "thermo": h.thermo,
                "aristotelian_cause": h.aristotelian_cause,
                "description": h.description,
            },
        )
        node.active_since = mtime_iso       # OVERRIDE default datetime.now()
        graph.add_node(node)
        nodes_added += 1

    # Step 2 — wire the declared slot relations
    for _, _mod, h, _ in holons_found:
        a_id = _holon_node_id(h.name)
        if a_id not in graph._nodes:
            continue
        for field_name, (slot, direction) in _SLOT_BY_FIELD.items():
            targets = getattr(h, field_name, [])
            for declared_name in targets:
                # Resolve declared target name to a code-holon node id
                candidates = [
                    _holon_node_id(declared_name),
                    _holon_node_id(declared_name.split(".")[-1]),
                ]
                b_id = next((c for c in candidates if c in graph._nodes), None)
                if not b_id or b_id == a_id:
                    continue
                # Honor declared direction
                if direction == "from_target":
                    src, tgt = b_id, a_id
                else:
                    src, tgt = a_id, b_id
                try:
                    graph.add_edge(Edge(
                        source=src, target=tgt,
                        slot=slot, confidence=Confidence.EXTRACTED,
                        scale_from=graph._nodes[src].scale,
                        scale_to=graph._nodes[tgt].scale,
                        evidence=f"code holon: {h.name}.{field_name}={declared_name} "
                                 f"(emitted as {src}→{tgt}[{slot.name}], dir={direction})",
                    ))
                    edges_added += 1
                except (KeyError, ValueError):
                    continue

    return {
        "extractor": "code_holons",
        "files_processed": len(holons_found),
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "holons_walked": [h.name for _, _, h, _ in holons_found],
    }


# ---- This module's own __holon__ ----
from ..holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="code_holons",
    scale=3,
    aristotelian_cause="formal",
    container=["core.extractors"],
    substrate=["core.holon_meta", "core.schema"],
    effect=["code-holon nodes + 12-slot edges encoding the codebase's own structure"],
    description="Maximalist move: emit the project's CODE as IVM holons in the graph",
)
