"""Graph builder — assembles Nodes + Edges into a queryable graph.

Maintains the slot-population invariant: when an edge is added, the
target node's appropriate slot is populated with the edge ID.

Built on NetworkX MultiDiGraph (one edge per (source, target, slot) triple).
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable, Optional

import networkx as nx

from .schema import Confidence, Edge, Layer, Node, Slot, validate_edge, validate_node


class TensegrityGraph:
    """Holonic graph with 12-slot IVM structure."""

    def __init__(self):
        from datetime import datetime as _dt
        self.G: nx.MultiDiGraph = nx.MultiDiGraph()
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}  # edge_id → Edge
        self._edge_counter = 0
        # Provenance machinery — set by with_provenance() context manager.
        # Every add_node / add_edge auto-stamps with the current provenance
        # so we know which extractor + build added what.
        self.build_id: str = _dt.now().strftime("%Y%m%dT%H%M%S")
        self._current_extractor: str | None = None

    def with_provenance(self, extractor_name: str):
        """Context manager: any add_node/add_edge inside the block is tagged.

        RE-ENTRANT (round-8 fix): saves and restores the previous extractor
        context on __exit__, so if extractor A's extract() calls into B's
        extract(), the inner block's exit doesn't clobber A's attribution
        for A's remaining work. Inner nodes get tagged B; outer's tagged A.

        Usage:
            with graph.with_provenance("experiments_log"):
                graph.add_node(...)
                graph.add_edge(...)
        """
        graph_self = self
        class _Ctx:
            def __enter__(self):
                self._prev = graph_self._current_extractor
                graph_self._current_extractor = extractor_name
            def __exit__(self, *a):
                graph_self._current_extractor = self._prev
        return _Ctx()

    def _stamp_provenance(self) -> dict:
        return {
            "extractor": self._current_extractor or "unknown",
            "build_id": self.build_id,
        }

    # ----- Mutation -----

    def add_node(self, node: Node) -> None:
        errors = validate_node(node)
        if errors:
            raise ValueError(f"invalid node {node.id}: {errors}")
        # Auto-stamp provenance if not already set on the node
        if not node.provenance:
            node.provenance = self._stamp_provenance()
        self._nodes[node.id] = node
        self.G.add_node(node.id, **node.to_dict())

    def add_edge(self, edge: Edge) -> str:
        errors = validate_edge(edge)
        if errors:
            raise ValueError(f"invalid edge {edge.source}→{edge.target}: {errors}")
        if edge.source not in self._nodes:
            raise KeyError(f"source node not found: {edge.source}")
        if edge.target not in self._nodes:
            raise KeyError(f"target node not found: {edge.target}")
        # Auto-stamp provenance
        if not edge.provenance:
            edge.provenance = self._stamp_provenance()
        edge_id = f"e{self._edge_counter}"
        self._edge_counter += 1
        self._edges[edge_id] = edge
        # Populate the target node's slot (the EDGE ARRIVES at target via this slot)
        self._nodes[edge.target].populate_slot(edge.slot, edge_id)
        # Also populate source's reciprocal-axis slot (every edge has 2 endpoints)
        # Convention: source sees the edge in the OPPOSITE polar direction.
        reciprocal = self._reciprocal_slot(edge.slot)
        if reciprocal is not None:
            self._nodes[edge.source].populate_slot(reciprocal, edge_id)
        # Add to NetworkX
        self.G.add_edge(
            edge.source, edge.target, key=edge_id,
            **edge.to_dict()
        )
        return edge_id

    @staticmethod
    def _reciprocal_slot(slot: Slot) -> Optional[Slot]:
        """The opposite slot in the same polar axis.

        E.g., if edge arrives at target via CONTAINER (slot 4),
        from source's perspective it leaves via SUBSTRATE (slot 3).
        Both are vertical-axis but opposite polarity.
        """
        recip = {
            Slot.SUCCESSOR: Slot.PREDECESSOR,
            Slot.PREDECESSOR: Slot.SUCCESSOR,
            Slot.SUBSTRATE: Slot.CONTAINER,
            Slot.CONTAINER: Slot.SUBSTRATE,
            Slot.PEER_COHERENT: Slot.PEER_COHERENT,    # symmetric — same slot
            Slot.PEER_CONTRADICTORY: Slot.PEER_CONTRADICTORY,
            Slot.CODE: Slot.THERMO,
            Slot.THERMO: Slot.CODE,
            Slot.CAUSE: Slot.EFFECT,
            Slot.EFFECT: Slot.CAUSE,
            Slot.SPECIFICATION: Slot.INSTANTIATION,
            Slot.INSTANTIATION: Slot.SPECIFICATION,
        }
        return recip.get(slot)

    # ----- Diagnostics -----

    def compute_prestress(self) -> None:
        """Update each node's prestress_local based on edge confidences."""
        for node_id, node in self._nodes.items():
            count = 0
            for slot in Slot.cables():
                for edge_id in node._slots_populated[slot]:
                    edge = self._edges[edge_id]
                    if edge.confidence in (Confidence.AMBIGUOUS, Confidence.INFERRED):
                        count += 1
            node.metadata["prestress_local"] = count

    def topological_invariants(self) -> dict:
        """Poincaré-inspired topological invariants of the underlying graph.

        Computed on the undirected projection (ignoring edge direction).
        These are stable under continuous deformation — diagnostic of
        fundamental structural properties, not surface details.

        - beta_0: number of connected components (graph fragmentation)
        - beta_1: number of independent cycles (Euler-formula derived)
        - cycle_basis_size: alternative cycle count via NetworkX
        """
        if len(self._nodes) == 0:
            return {"beta_0": 0, "beta_1": 0, "cycle_basis_size": 0}
        UG = self.G.to_undirected()
        beta_0 = nx.number_connected_components(UG)
        # beta_1 via Euler: |E| - |V| + beta_0 (for undirected graph)
        # Note: MultiGraph edge count counts parallel edges; we use simple graph
        SUG = nx.Graph(UG)  # collapse parallel edges
        n_v = SUG.number_of_nodes()
        n_e = SUG.number_of_edges()
        beta_1 = max(0, n_e - n_v + beta_0)
        cycle_basis_size = len(nx.cycle_basis(SUG))
        return {
            "beta_0": beta_0,
            "beta_1": beta_1,
            "cycle_basis_size": cycle_basis_size,
        }

    def stats(self) -> dict:
        """Top-level diagnostics including Grant + Poincaré additions."""
        self.compute_prestress()
        ve_scores = [n.ve_score for n in self._nodes.values()]
        ve_scores_harmonic = [n.ve_score_harmonic for n in self._nodes.values()]
        prestress = [n.prestress_local for n in self._nodes.values()]
        saturation = [n.saturation for n in self._nodes.values()]
        n_struts = sum(1 for e in self._edges.values() if e.mechanical_type == "strut")
        n_cables = sum(1 for e in self._edges.values() if e.mechanical_type == "cable")
        scale_dist = Counter(n.scale for n in self._nodes.values())
        layer_dist = Counter(n.layer.value for n in self._nodes.values())
        slot_usage = Counter()
        for e in self._edges.values():
            slot_usage[e.slot.name] += 1
        topo = self.topological_invariants()

        return {
            "n_nodes": len(self._nodes),
            "n_edges": len(self._edges),
            "n_struts": n_struts,
            "n_cables": n_cables,
            "strut_cable_ratio": round(n_struts / max(1, n_cables), 3),
            "avg_ve_score": round(sum(ve_scores) / max(1, len(ve_scores)), 3),
            "avg_ve_score_harmonic": round(sum(ve_scores_harmonic) / max(1, len(ve_scores_harmonic)), 3),
            "max_ve_score": round(max(ve_scores) if ve_scores else 0, 3),
            "max_ve_score_harmonic": round(max(ve_scores_harmonic) if ve_scores_harmonic else 0, 3),
            "avg_prestress": round(sum(prestress) / max(1, len(prestress)), 3),
            "total_prestress": sum(prestress),
            "avg_saturation": round(sum(saturation) / max(1, len(saturation)), 3),
            "max_saturation": round(max(saturation) if saturation else 0, 3),
            "scale_distribution": dict(scale_dist),
            "layer_distribution": dict(layer_dist),
            "slot_usage": dict(slot_usage),
            # Poincaré topological invariants
            "topology_beta_0_components": topo["beta_0"],
            "topology_beta_1_cycles": topo["beta_1"],
            "topology_cycle_basis_size": topo["cycle_basis_size"],
        }

    def god_nodes(self, threshold: float = 0.8, top_k: int = 12) -> list[tuple[str, float]]:
        """Nodes near vector equilibrium — likely organizing concepts.

        Returns up to top_k nodes with VE_score >= threshold, sorted desc.
        """
        candidates = [
            (nid, n.ve_score) for nid, n in self._nodes.items()
            if n.ve_score >= threshold
        ]
        return sorted(candidates, key=lambda x: -x[1])[:top_k]

    def overloaded_nodes(self, threshold: float = 1.0) -> list[tuple[str, float]]:
        """Nodes with saturation > threshold (>12 edges) — split candidates."""
        return sorted(
            [(nid, n.saturation) for nid, n in self._nodes.items() if n.saturation > threshold],
            key=lambda x: -x[1],
        )

    def orphan_nodes(self, threshold: float = 0.3) -> list[tuple[str, float]]:
        """Nodes with VE_score < threshold — under-developed or stale."""
        return sorted(
            [(nid, n.ve_score) for nid, n in self._nodes.items() if n.ve_score < threshold],
            key=lambda x: x[1],
        )

    def hot_frontiers(self, ve_min: float = 0.6, prestress_min: int = 3) -> list[tuple[str, float, int]]:
        """Nodes with high VE AND high prestress — narrative tension hotspots.

        High VE = well-connected; high prestress = under productive tension.
        These are typically where research is actively pushing.
        """
        self.compute_prestress()
        results = []
        for nid, n in self._nodes.items():
            if n.ve_score >= ve_min and n.prestress_local >= prestress_min:
                results.append((nid, n.ve_score, n.prestress_local))
        return sorted(results, key=lambda x: -(x[1] * (x[2] + 1)))

    def asymmetric_nodes(self, threshold: float = 0.5) -> list[tuple[str, float]]:
        """Nodes with asymmetry > threshold — pure-code or pure-thermo holons."""
        return sorted(
            [(nid, n.asymmetry) for nid, n in self._nodes.items() if n.asymmetry > threshold],
            key=lambda x: -x[1],
        )

    # ----- Society construction (Whitehead + Wittgenstein, Tier 3a) -----

    def materialize_society(
        self,
        proposal: dict,
        scale: int = 2,
    ) -> str:
        """Materialize a society proposal as a structural meta-node.

        Takes a proposal from `diagnostics.consolidate_societies()` and
        creates a structural Node + role_of edges from each functional
        member to the new society.

        Returns the new society node id.

        Whitehead: society = thread of actual occasions sharing characteristic.
        Wittgenstein: meaning emerges from clusters of use, not from
        a-priori definition.
        """
        soc_id = proposal["proposed_structural_id"]
        if soc_id in self._nodes:
            return soc_id  # idempotent — already materialized

        soc_label = f"{proposal['label']} (society of {proposal['n_members']} uses)"
        soc_node = Node(
            id=soc_id,
            label=soc_label,
            scale=scale,
            layer=Layer.STRUCTURAL,
            metadata={
                "constructed_from": "society_proposal",
                "members": proposal["members"],
                "rationale": proposal["rationale"],
            },
        )
        self.add_node(soc_node)

        # Wire each member as role_of (functional → structural)
        from .schema import Slot, Confidence, Edge
        for member_id in proposal["members"]:
            if member_id not in self._nodes:
                continue
            # Use SPECIFICATION slot (strut, type axis) — the society
            # SPECIFIES a pattern that each member INSTANTIATES
            edge = Edge(
                source=member_id,
                target=soc_id,
                slot=Slot.SPECIFICATION,
                confidence=Confidence.INFERRED,
                evidence=f"society membership via family resemblance ≥0.7",
            )
            self.add_edge(edge)
            # Update the functional node's structural_ref
            self._nodes[member_id].structural_ref = soc_id
        return soc_id

    # ----- Persistence -----

    def to_dict(self) -> dict:
        self.compute_prestress()
        return {
            "schema_version": "1.0.0",
            "stats": self.stats(),
            "nodes": [self._nodes[nid].to_dict() for nid in self._nodes],
            "edges": [{"id": eid, **e.to_dict()} for eid, e in self._edges.items()],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<TensegrityGraph nodes={len(self._nodes)} edges={len(self._edges)}>"


# ---- Code-holon meta (read by core/extractors/code_holons.py) ----
from core.holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name='builder',
    scale=1,
    aristotelian_cause='efficient',
    container=['core'],
    substrate=['core.schema', 'networkx'],
    cause=['extractors via add_node/add_edge'],
    effect=['populated TensegrityGraph with all derived metrics'],
    specification=['TensegrityGraph wrapper around NetworkX MultiDiGraph'],
    code='TensegrityGraph class',
    description='Imperative state — assembles nodes/edges into a queryable graph',
)
