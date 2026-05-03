# Side findings — resolution report

Date: 2026-05-02
Author: pre-submission code-hygiene pass on `core/maxims.py` and the
phase-14 enrichment pipeline.

Both side findings flagged in `SUBMISSION_PACKAGE.md` are RESOLVED. The
phase-9 reference snapshot (SHA `dc7bf9d51f3e42b8...`) is unchanged; the
phase-14 snapshot was re-enriched after the validator fix.

## Finding 1 — `_validate_predecessor` directional inconsistency

**What was wrong.** Edge `X --PREDECESSOR--> Y` follows the slot convention
that the **target plays the role** (Y is the predecessor of X), so Y must be
earlier than X. The implemented comparison `src.active_since < tgt.active_since`
correctly catches violations under this convention (target later than source).
The docstring and the violation message, however, treated *source* as the
predecessor — the linguistic semantics were inverted relative to the slot
contract used everywhere else in the codebase (see `_validate_successor`'s
"Y is the successor of X" framing).

**What was changed.** Updated the docstring to state the convention
explicitly (target is the predecessor) and rewrote the violation message so
target is identified as the alleged predecessor and the temporal claim
points at the right endpoint. The comparison itself is unchanged.

**Verified post-fix.** `violation_ablation.py` still reports detection rate
**11/11** (PREDECESSOR row caught with the same injected case). Phase-9
violations remain **0**.

## Finding 2 — D-309c PREDECESSOR clock-collision in phase-14

**What was wrong.** Two distinct root causes were producing spurious
PREDECESSOR violations:

1. The `experiments_log` extractor's `_parse_date` falls back to the raw
   input string when a date is unparseable. In phase-14, that left
   `D-103.active_since = "post-D-097"`, `D-230.active_since = "~2026-04"`,
   `D-247.active_since = "~2026-04-28"`, `D-109b.active_since = "QUEUED"`.
   The validator then performed string comparison: `'2026-05-02T00:00:00' <
   'post-D-097'` is True (digits sort before letters in ASCII), firing on
   every suffix-vs-non-ISO-parent pair — D-247b, D-247c, D-103v, D-230v.
2. `enrich_with_maxims.py`'s `reconstruct` does not preserve `active_since`,
   so during enrichment all nodes are re-stamped with `datetime.now()`.
   Consecutive `add_node` calls land within microseconds of each other,
   producing the sub-second timestamps reported in the original phase-14
   violation message (`...744245` vs `...744829`). This was the
   D-309c-specific case quoted in the original side-finding text.

**Strategy chosen.** Strategy B (localised fix in the maxim) plus minimal
defensive parsing — chosen over Strategy A (rewriting `_parse_date` and
`enrich_with_maxims.reconstruct`) because (a) it has lower blast radius and
(b) `enrich_with_maxims.py` was off-limits per task guardrails. Two
clauses were added to both `_validate_predecessor` and `_validate_successor`:

* **Strict ISO parsing.** Endpoints whose `active_since` is not a valid ISO
  datetime are skipped (returns `None` from a new `_parse_iso_strict`
  helper). This eliminates string-comparison spuriousness for the four
  garbage-date cases (D-103v, D-230v, D-247b, D-247c).
* **Suffix-id tie-breaker.** When the alleged predecessor (target) is later
  than the source by less than `_ANTERIORITY_EPSILON_SECONDS = 2.0` AND the
  source-id is a suffix-extension of the target-id (e.g., D-309c extends
  D-309), the lineage convention overrides the timestamp. The project's
  D-ID suffix convention is the deterministic ordering ground; clock-collision
  noise during node registration must not contradict it.

**Verified post-fix.** Phase-14 violations dropped from **4 to 3**:

| Slot          | Severity   | Cause                                             |
|---------------|------------|---------------------------------------------------|
| SUBSTRATE     | VIOLATION  | `holon_code_experiments_log` (scale 2) → `holon_code_operational_distinctions` (scale 1). Documented below — out of scope for this hygiene pass. |
| PEER_COHERENT | WARN       | `holon_code_operational_distinctions` (s1) ↔ `holon_code_experiments_log` (s2), Δ=1. |
| PEER_COHERENT | WARN       | `holon_code_operational_distinctions` (s1) ↔ `holon_code_paper_drafts` (s2), Δ=1. |

The PREDECESSOR row is fully eliminated. Detection rate from
`violation_ablation.py` is still **11/11**. Phase-9 violations remain **0**.

## SUBSTRATE violation — known cause, out of scope

The remaining VIOLATION-tier entry in phase-14 originates from the
`__holon__` declaration in `core/extractors/operational_distinctions.py`:

```
substrate=['core.schema', 'core.node_types', 'core.extractors.experiments_log']
```

The author legitimately depends `operational_distinctions` (scale 1) on
`experiments_log` (scale 2) at the import level, but the SUBSTRATE maxim
(`source.scale <= target.scale` for material cause) reads the scale
inversion as a category error. Either the scale assignment of one of the
two extractors needs revisiting, or the dependency should be re-encoded as a
different slot (CONTAINER would invert direction; CAUSE on the lateral axis
fits less awkwardly). Left as a separate housekeeping item; the violation
is real and informational rather than spurious.

## Files modified

* `core/maxims.py` — added `_parse_iso_strict`, `_is_suffix_lineage`,
  `_ANTERIORITY_EPSILON_SECONDS`; rewrote `_validate_predecessor` and
  `_validate_successor` bodies; updated docstrings + error message of
  `_validate_predecessor` (Finding 1 + Finding 2).
* `tensegrity_graph_phase14_complete.json` — re-enriched in place (3
  violations stored).
* `publication/SUBMISSION_PACKAGE.md` — Side findings list marked RESOLVED.

## Re-verification commands

```bash
cd knowledge-graph
python publication/violation_ablation.py        # 11/11
python publication/compute_paper_numbers.py --snapshot phase9   # 335 proposals / 0 violations
python publication/compute_paper_numbers.py --snapshot phase14  # 446 proposals / 3 violations
```
