# Boethian-maxim violation-detection ablation — report

**Snapshot:** `tensegrity_graph_phase9_complete.json`
**SHA-256:** `dc7bf9d51f3e42b8a1d72c61462e9b3a24567622b5798a1a94269c57d1953739`
**Date run:** 2026-05-02
**Reproducibility:** `python publication/violation_ablation.py`

## Method

For each of the 12 IVM-slot maxims declared in `core/maxims.py`, we make a deep-copy of the phase-9 graph, inject one synthetic edge crafted to violate that maxim's `validation_rule`, run the engine (`validate_graph`), and check whether the engine's output references our injected edge id (`__violation_test_{SLOT}__`). Each test is run on a fresh copy so injections do not interfere across slots. Edges that the builder pre-validates (CAUSE self-loop) are inserted directly into the in-memory graph dictionary, bypassing builder-level checks, so the maxim engine — not the builder — is what we measure. Temporal-order tests override the endpoint nodes' `active_since` fields, since these are not preserved through JSON round-trip.

## Per-slot detection table

| Slot                | Injected | Caught | Matches | Severity      | Endpoints / note |
|---------------------|----------|--------|--------:|---------------|------------------|
| SUCCESSOR           | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1_section_4 |
| PREDECESSOR         | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1_section_4 |
| SUBSTRATE           | yes      | yes    |       1 | VIOLATION     | src=P1 tgt=D-057 |
| CONTAINER           | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1 |
| PEER_COHERENT       | yes      | yes    |       1 | STRICT        | src=holon_code_node_types tgt=P1 |
| PEER_CONTRADICTORY  | yes      | yes    |       1 | STRICT        | src=holon_code_node_types tgt=P1 |
| CODE                | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1 |
| THERMO              | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1_section_4 |
| CAUSE               | yes      | yes    |       1 | STRICT        | src=D-057 tgt=D-057 |
| EFFECT              | N/A      | —      |       0 | —             | no validation_rule in MAXIMS registry — N/A |
| SPECIFICATION       | yes      | yes    |       1 | VIOLATION     | src=P1 tgt=D-057 |
| INSTANTIATION       | yes      | yes    |       1 | VIOLATION     | src=D-057 tgt=P1 |

**Slots with injected violation:** 11 / 12
**Slots caught:** 11 / 11
**Detection rate (caught / injected):** **1.000 (11/11)**
**Baseline `n_violations` on the uncorrupted phase-9 snapshot:** 0

## Findings

The ablation confirms the engine is not silent by accident. For every slot whose maxim defines a `validation_rule` (11 of the 12), the engine detects a deliberately-injected violation on the first try, with the correct severity tag (`VIOLATION` for the asymmetric scale-direction and EXTRACTED-on-structural rules; `STRICT` for the cross-scale category-error tier on `PEER_*` and the self-loop on `CAUSE`). The lateral peer rules behave as the comment in `_validate_peer_coherent_same_scale` predicts: a Δ≥2 cross-scale jump is reported as `STRICT` rather than the milder `WARN` tier reserved for Δ=1 vocabulary-overlap noise. The CAUSE self-loop is caught at the maxim layer even though `builder.add_edge` would normally reject it earlier — the maxim is a true second line of defence, not a tautological echo of builder validation. The one slot without a verdict (`EFFECT`) is missing a validator by deliberate design, not by oversight: the registry comment notes that "causes are known through their effects" is observational, not normative — there is no malformed-edge pattern to catch on the EFFECT side that would not already be caught on the reciprocal CAUSE side.

## Caveats

This ablation tests **structural** detection: scale ordering, temporal order, layer-vs-confidence pairing, self-loop on causal slot, and cross-scale category errors on lateral slots. It does **not** test (a) **semantic drift** — an edge whose endpoints are correctly typed but whose evidence string misrepresents the relation; (b) **defeasible reasoning** — cases where the maxim should be overruled by domain context (Spinoza's *causa sui* would correctly trip the CAUSE self-loop check, but the rule has no exception clause); (c) **multi-edge contradictions** beyond the contraries-coherent pair already covered by `_validate_peer_contradictory`; (d) **inference correctness**, only inference *firing* — the 335 active proposals in phase-9 are not audited here; and (e) **provenance integrity** — a violation could be injected with a forged evidence string and the engine would still flag it geometrically without commenting on provenance quality.

## Suggested §5.2 paragraph (80-120 words)

> To verify that the zero-violation result on the released snapshot reflects engine coverage rather than engine silence, we ran a synthetic-injection ablation: for each of the eleven slot maxims that define a `validation_rule` in `core/maxims.py`, we deep-copied the graph, injected one edge crafted to trip exactly that maxim, and re-ran `validate_graph`. The engine detected every injected violation on the first pass (11 / 11), with appropriate severity tagging — `STRICT` for the cross-scale `PEER_COHERENT` / `PEER_CONTRADICTORY` category-error tier and the `CAUSE` self-loop, `VIOLATION` for the scale-direction and EXTRACTED-on-structural rules. The twelfth slot (`EFFECT`) carries no validator by design, since "causes are known through their effects" is observational. The harness lives at `publication/violation_ablation.py` and is reproducible from the same snapshot SHA verified in §5.1.
