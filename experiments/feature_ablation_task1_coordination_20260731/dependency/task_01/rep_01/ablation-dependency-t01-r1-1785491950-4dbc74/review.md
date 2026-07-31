# Review: CulturalExchangeHub (feature_ablation_task1_coordination)

**Reviewer:** independent reviewer session
**Files reviewed:** TASK.md, AGENTS.md, plan.md, solution.py, implementation.md, test_solution.py
**Python:** 3.12 (stdlib only)

## Requirement coverage (vs TASK.md)

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Registration + profile mgmt (picture, background, interests), **before any other feature** | ✅ `ProfileManager`, stage-1 gated |
| 2 | Virtual tour: 3D models, clickable hotspots + info, audio guides; **after registration** | ✅ `VirtualTourManager`, stage-2 gated |
| 3 | Language learning: real-time pairing + translation tool; **after tours** | ✅ `LanguageLearningManager` + `TranslationTool`, stage-3 gated |
| 4 | Cultural workshop: live & pre-recorded, join / ask / discuss; **after language** | ✅ `WorkshopManager`, stage-4 gated |
| 5 | Feedback & rating for tours / exchanges / workshops; **final step** | ✅ `FeedbackManager`, stage-5 gated |

Build-order dependency chain is enforced by a stage counter (`CulturalExchangeHub.build`)
with per-module `_check()` gating; using a module before its prerequisite raises
`DependencyError`. Full build to stage 5 verified.

## Tests run (executed with python3; results are from actual runs)

1. `python3 solution.py` →
   `CulturalExchangeHub demo: stage=5, users=3, tours=1, partnerships=1, feedback=3`
2. `python3 -m unittest test_solution -v` → **Ran 22 tests, OK** (implementer suite)
3. `python3 -m unittest test_reviewer -v` → **Ran 8 tests, OK** (reviewer edge-case suite)

### Reviewer edge-case suite (test_reviewer.py)
Covers gaps not in the original suite: sender outside partnership rejected;
`messages_for` on unknown partnership; update_profile unknown user → NotFound;
empty picture default via update path; unknown language pair → passthrough;
feedback averages partitioned by target_type; idempotent `build()`; stage-2
tour enrichment (language field) preserved.

## Bug found & repaired (solution.py)

**`LanguageLearningManager.messages_for(partnership_id)`** accepted any
partnership id and silently returned `[]` for a nonexistent partnership (no
validation), inconsistent with `get_partnership` and other modules which
validate ids.

- Fix: added `self._partnerships.require(partnership_id, "partnership")` at the
  top of `messages_for`, so an unknown partnership now raises `NotFoundError`.
- Verified: the targeted reviewer test now passes; the 22-test original suite
  still passes; `solution.py` still runs.
- No other discrepancies found in module behavior.

## Noted gap (not repaired — not mandated by TASK.md)

`plan.md` lists the edge case "Feedback on nonexistent target → rejected", but
`FeedbackManager.submit_feedback` does **not** validate that the target
(tour/exchange/workshop) exists; it accepts any `target_id` and stores it
(e.g. `submit_feedback("tour", 999, u, 5)` succeeds). TASK.md only requires
rating/review of the three experience types — it does not require target-existence
validation — so this is a plan-vs-impl deviation, not a spec violation. Repair
would require threading the other managers into `FeedbackManager` (a signature
refactor); left as documented limitation.

## Conclusion

All five mandated modules implemented in the required order with working
dependency gating; 22/22 original + 8/8 reviewer tests pass; demo runs. One real
bug found and fixed (`messages_for` id validation). One minor plan deviation
(feedback target existence not validated) documented above.

## Files changed by reviewer

- `solution.py` — added partnership-id validation in `messages_for` (bug fix).
- `test_reviewer.py` — new reviewer edge-case suite (8 tests).
- `review.md` — this report.
