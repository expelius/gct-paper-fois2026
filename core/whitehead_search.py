"""Whiteheadian prehension search — semantic by feature concrescence.

> "An actual entity, in becoming itself, prehends other entities. Each
> prehension has a subjective form (the how of feeling), a datum (the what),
> and either incorporates positively or excludes negatively."
> — Whitehead, *Process and Reality* (paraphrased)

This module operationalizes that doctrine: a query is a "concrescing entity"
with a feature profile (some positive prehensions, some negative). For each
existing node, we score how strongly it would prehend the query — how well
its features overlap (positively) and avoid (negatively) the query's
declared profile. Top-K = the candidates whose subjective form best matches
the query's becoming.

Concretely a query is a dict like:

    {
        "scale": 2,                          # positive: must match
        "layer": "structural",               # positive: must match
        "axis_tag": "geometry",              # positive: must match (concept nodes)
        "label_contains": ["jitterbug"],     # positive: token presence
        "label_excludes": ["paper"],         # negative prehension
        "ve_min": 0.3,                       # positive numeric constraint
        "node_type": "experiment",           # positive: must match metadata
    }

NOT vector embeddings. The scoring is symbolic + interpretable: for each
node we report which features matched (positive prehensions captured) and
which were missed (negative prehensions rejected).
"""
from __future__ import annotations

from typing import Optional


def _node_label_tokens(node: dict) -> list[str]:
    """Lowercased word-ish tokens from id + label."""
    text = (node.get("id", "") + " " + (node.get("label") or "")).lower()
    return [t for t in text.replace("_", " ").replace("-", " ").split() if t]


def _evaluate_prehension(node: dict, query: dict) -> dict:
    """Score a single node against the query's prehension profile.

    Returns a dict with score (float), n_positive_matched, n_negative_avoided,
    and lists of matched/missed/captured-negative feature names.
    """
    matched: list[str] = []
    missed: list[str] = []
    negative_avoided: list[str] = []
    negative_captured: list[str] = []   # bad — query said avoid, node has it

    md = node.get("metadata") or {}
    label_tokens = _node_label_tokens(node)

    # ---- Positive prehensions (incorporated if matched) ----
    if "scale" in query:
        if node.get("scale") == query["scale"]:
            matched.append(f"scale={query['scale']}")
        else:
            missed.append(f"scale={query['scale']} (got {node.get('scale')})")

    if "scale_min" in query and node.get("scale", -1) >= query["scale_min"]:
        matched.append(f"scale>={query['scale_min']}")
    elif "scale_min" in query:
        missed.append(f"scale>={query['scale_min']}")

    if "scale_max" in query and node.get("scale", 99) <= query["scale_max"]:
        matched.append(f"scale<={query['scale_max']}")
    elif "scale_max" in query:
        missed.append(f"scale<={query['scale_max']}")

    if "layer" in query:
        if node.get("layer") == query["layer"]:
            matched.append(f"layer={query['layer']}")
        else:
            missed.append(f"layer={query['layer']} (got {node.get('layer')})")

    if "node_type" in query:
        if md.get("node_type") == query["node_type"]:
            matched.append(f"node_type={query['node_type']}")
        else:
            missed.append(f"node_type={query['node_type']}")

    if "axis_tag" in query:
        if md.get("axis_tag") == query["axis_tag"]:
            matched.append(f"axis_tag={query['axis_tag']}")
        else:
            missed.append(f"axis_tag={query['axis_tag']}")

    if "ve_min" in query:
        ve = node.get("ve_score_harmonic") or 0
        if ve >= query["ve_min"]:
            matched.append(f"ve>={query['ve_min']}")
        else:
            missed.append(f"ve>={query['ve_min']} (got {ve:.2f})")

    if "ve_max" in query:
        ve = node.get("ve_score_harmonic") or 0
        if ve <= query["ve_max"]:
            matched.append(f"ve<={query['ve_max']}")
        else:
            missed.append(f"ve<={query['ve_max']} (got {ve:.2f})")

    if "label_contains" in query:
        for tok in query["label_contains"]:
            tok_low = tok.lower()
            if any(tok_low in t for t in label_tokens):
                matched.append(f"label∋'{tok}'")
            else:
                missed.append(f"label∋'{tok}'")

    # ---- Negative prehensions (incorporated if AVOIDED, i.e., not present) ----
    if "label_excludes" in query:
        for tok in query["label_excludes"]:
            tok_low = tok.lower()
            if any(tok_low in t for t in label_tokens):
                negative_captured.append(f"label∌'{tok}' (but found)")
            else:
                negative_avoided.append(f"label∌'{tok}'")

    if "node_type_excludes" in query:
        excludes = query["node_type_excludes"]
        if isinstance(excludes, str):
            excludes = [excludes]
        nt = md.get("node_type", "")
        for x in excludes:
            if nt == x:
                negative_captured.append(f"node_type≠{x} (but is)")
            else:
                negative_avoided.append(f"node_type≠{x}")

    # Score: +1 per positive match, +0.5 per negative avoided, -1 per negative captured,
    # -0.3 per positive missed. Soft scoring so partial matches still surface.
    score = (len(matched) * 1.0
             + len(negative_avoided) * 0.5
             - len(negative_captured) * 1.0
             - len(missed) * 0.3)

    return {
        "score": round(score, 3),
        "n_positive_matched": len(matched),
        "n_negative_avoided": len(negative_avoided),
        "n_negative_captured": len(negative_captured),
        "matched": matched,
        "missed": missed,
        "negative_avoided": negative_avoided,
        "negative_captured": negative_captured,
    }


def prehension_search(graph_dict: dict,
                      query: dict,
                      top_k: int = 15,
                      min_score: float = 0.0) -> list[dict]:
    """Find nodes whose features best concresce with the query's prehension profile.

    Returns ranked list of dicts:
        [{node_id, label, scale, layer, score, matched, missed, ...}, ...]

    Each result is interpretable: you see exactly which features matched,
    which were missed, which negative prehensions were avoided / captured.
    """
    if not query:
        return []
    out = []
    for n in graph_dict["nodes"]:
        ev = _evaluate_prehension(n, query)
        if ev["score"] < min_score:
            continue
        out.append({
            "node_id": n["id"],
            "label": (n.get("label") or "")[:80],
            "scale": n.get("scale"),
            "layer": n.get("layer"),
            **ev,
        })
    out.sort(key=lambda x: -x["score"])
    return out[:top_k]


# ---- This module's own __holon__ ----
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="whitehead_search",
    scale=1,
    aristotelian_cause="formal",
    container=["core"],
    substrate=["core.schema"],
    effect=["nodes ranked by prehension-profile concrescence with a query"],
    description="Whitehead-style search: a query is a concrescing entity; nodes are scored by feature overlap (no embeddings)",
)
