"""Wittgensteinian family-resemblance search — semantic without embeddings.

> "El significado de una palabra es su uso en el lenguaje" (Inv. Filosóficas §43)
> "Family resemblance" (Inv. §65-67): things that count as 'games' don't share a
> single essential trait, but overlap in a network of similarities.

This module operationalizes that doctrine: two CONCEPTS are similar to the
extent that they OVERLAP IN HOW THEY ARE USED across the project's corpus.
No vector embeddings, no neural model — just the patterns of co-occurrence
that the `concepts` extractor already captured as `concept_X_in_doc_Y`
functional-use nodes with `n_hits` counts per document.

Concrete: each curated concept C has a use-vector u(C) where u(C)[d] = n_hits
of C in document d, normalized. Similarity(C1, C2) = some overlap measure
between u(C1) and u(C2). Three measures provided:

  - cosine          — angle between use-vectors (standard in IR)
  - jaccard         — set-overlap of documents (ignores frequencies)
  - kullback_leibler — symmetric KL divergence over the use distributions

The OUTPUT is an ordered list of (concept_id, score, shared_docs) tuples —
fully interpretable: you can trace WHY two concepts are similar to specific
documents that use both. Compare to embeddings, where similarity is opaque.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional


def build_use_vectors(graph_dict: dict) -> dict[str, dict[str, int]]:
    """Build per-concept use-vectors from functional-use nodes.

    Returns a dict: concept_id → {doc_name → n_hits}
    """
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for n in graph_dict["nodes"]:
        md = n.get("metadata") or {}
        if md.get("node_type") != "concept_functional_use":
            continue
        concept_id = n.get("structural_ref")
        doc = md.get("in_document")
        n_hits = md.get("n_hits", 0)
        if concept_id and doc:
            out[concept_id][doc] = n_hits
    return dict(out)


def cosine(u1: dict[str, int], u2: dict[str, int]) -> float:
    """Cosine of two sparse use-vectors."""
    if not u1 or not u2:
        return 0.0
    shared = set(u1) & set(u2)
    dot = sum(u1[d] * u2[d] for d in shared)
    n1 = math.sqrt(sum(v * v for v in u1.values()))
    n2 = math.sqrt(sum(v * v for v in u2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def jaccard(u1: dict[str, int], u2: dict[str, int]) -> float:
    """Jaccard index over the document SETS — ignores frequencies."""
    s1 = set(u1)
    s2 = set(u2)
    if not s1 and not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def kl_symmetric(u1: dict[str, int], u2: dict[str, int]) -> float:
    """Jensen-Shannon-like symmetric divergence over normalized distributions.

    Returns a SIMILARITY in [0, 1] (1 - JS_divergence / log(2)) so it composes
    with cosine/jaccard which are also similarities.
    """
    if not u1 or not u2:
        return 0.0
    docs = set(u1) | set(u2)
    s1 = sum(u1.values()) or 1
    s2 = sum(u2.values()) or 1
    p = {d: (u1.get(d, 0) / s1) for d in docs}
    q = {d: (u2.get(d, 0) / s2) for d in docs}
    m = {d: (p[d] + q[d]) / 2 for d in docs}
    js = 0.0
    for d in docs:
        if p[d] > 0 and m[d] > 0:
            js += 0.5 * p[d] * math.log(p[d] / m[d])
        if q[d] > 0 and m[d] > 0:
            js += 0.5 * q[d] * math.log(q[d] / m[d])
    # JS ∈ [0, log 2]; convert to similarity ∈ [0, 1]
    return max(0.0, 1.0 - js / math.log(2))


SIMILARITY_FNS = {
    "cosine": cosine,
    "jaccard": jaccard,
    "kl": kl_symmetric,
}


def family_resemblance(
    graph_dict: dict,
    target_concept_id: str,
    measure: str = "cosine",
    top_k: int = 10,
    min_score: float = 0.05,
) -> list[dict]:
    """Find concepts most similar to `target_concept_id` by use-pattern overlap.

    Returns list of dicts ordered by score:
        [{concept_id, canonical, score, shared_docs, shared_doc_count, ...}, ...]

    The `shared_docs` field is the actual list of documents both concepts
    appear in — provides the WHY of the similarity in interpretable terms.
    """
    if measure not in SIMILARITY_FNS:
        raise ValueError(f"Unknown measure '{measure}'. Try one of {list(SIMILARITY_FNS)}.")
    sim_fn = SIMILARITY_FNS[measure]
    use_vectors = build_use_vectors(graph_dict)
    if target_concept_id not in use_vectors:
        return []
    target_vec = use_vectors[target_concept_id]
    # Index canonical names per concept (from the structural concept node)
    canonical_lookup = {
        n["id"]: (n.get("metadata") or {}).get("canonical", "")
        for n in graph_dict["nodes"]
        if (n.get("metadata") or {}).get("node_type") == "concept"
    }
    out = []
    for cid, vec in use_vectors.items():
        if cid == target_concept_id:
            continue
        score = sim_fn(target_vec, vec)
        if score < min_score:
            continue
        shared = sorted(set(target_vec) & set(vec))
        out.append({
            "concept_id": cid,
            "canonical": canonical_lookup.get(cid, ""),
            "score": round(score, 4),
            "n_shared_docs": len(shared),
            "n_target_docs": len(target_vec),
            "n_other_docs": len(vec),
            "shared_docs": shared[:8],   # top-8 for context, not exhaustive
        })
    out.sort(key=lambda x: -x["score"])
    return out[:top_k]


def family_clusters(
    graph_dict: dict,
    measure: str = "cosine",
    threshold: float = 0.4,
) -> list[list[dict]]:
    """Greedy single-link clustering of concepts by family resemblance.

    Returns list of clusters, each a list of {concept_id, canonical} dicts.
    Two concepts are in the same cluster if their similarity >= threshold.
    Sorted by cluster size descending.
    """
    use_vectors = build_use_vectors(graph_dict)
    sim_fn = SIMILARITY_FNS[measure]
    canonical_lookup = {
        n["id"]: (n.get("metadata") or {}).get("canonical", "")
        for n in graph_dict["nodes"]
        if (n.get("metadata") or {}).get("node_type") == "concept"
    }
    cids = list(use_vectors.keys())
    parent = {c: c for c in cids}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        parent[find(a)] = find(b)
    for i, c1 in enumerate(cids):
        for c2 in cids[i + 1:]:
            if sim_fn(use_vectors[c1], use_vectors[c2]) >= threshold:
                union(c1, c2)
    clusters: dict[str, list[str]] = defaultdict(list)
    for c in cids:
        clusters[find(c)].append(c)
    out = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        out.append([
            {"concept_id": m, "canonical": canonical_lookup.get(m, "")}
            for m in sorted(members)
        ])
    out.sort(key=lambda c: -len(c))
    return out


# ---- This module's own __holon__ ----
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="wittgenstein_search",
    scale=1,
    aristotelian_cause="formal",
    container=["core"],
    substrate=["core.schema"],
    effect=["family-resemblance scores between curated concepts based on co-occurrence"],
    description="Semantic similarity over concepts via Wittgensteinian use-pattern overlap (no embeddings)",
)
