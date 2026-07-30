# Shared interface memory: Tasks 1–5 development loop

This report records the iterative development set. Tasks 1–5 were deliberately
used for mechanism tuning and must not be treated as held-out evidence.

## Baseline

| Task | 1 | 2 | 3 | 4 | 5 | Mean | Complete workflows |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline score | 85 | 20 | 80 | 80 | 75 | 68 | 4/5 |

All five tasks had a confirmed baseline cross-domain fault.

## Iterations

| Version | Main change | Scores (Tasks 1–5) | Mean | Complete workflows | Observed result |
|---|---|---|---:|---:|---|
| X1 | Planner-generated shared contracts; all selected records injected | 80, 100, 20, 85, 100 | 77 | 4/5 | Fixed Tasks 2 and 5; easy-boundary selection and Task 3 incomplete turn |
| X2 | Dedicated task-level generator; strict external/risk ranking; one detailed injection | 100, 20, 20, 20, 100 | 52 | 2/5 | Better boundary selection but severe execution regressions |
| X3 | Fold generation into planner; one detailed contract | 90, 85, 90, 90, 100 | 91 | 5/5 | Best single run; strict faults still remained on Tasks 1, 3, and 4 |
| X4 | Five-record coverage inventory and simulation rejection | 90, 20, 20, 90, 80 | 60 | 3/5 | Reintroduced context overload |
| X5 | X3 implementation load plus strict reviewer coverage gate | 95, 20, 85, 100, 100 | 80 | 4/5 | More honest audits and repairs, but Task 2 incomplete |
| X6 | Targeted post-implementation integration Agent | 100, 85, 90, 90, 95 | 92 | 4/5 | Highest score, but wrong highest-risk record often retrieved; Task 2 handoff incomplete |
| X7 | Deterministic public interface-pattern memory | 20, 85, 75, 85, 90 | 71 | 4/5 | Pattern guidance increased prompt cost and Task 1 failed |
| X3 confirmation | Fresh workspaces and sessions, unchanged X3 | 100, 75, 20, 20, 100 | 63 | 3/5 | Original 5/5 result did not reproduce |
| X8 | Generate one evidence-grounded record only after runnable implementation | 70, 90, 20, 100, 100 | 76 | 4/5 | Useful concrete repairs, but irrelevant Task 1 record and Task 3 failure |

## Converged failure patterns

1. **Proactive memory competes with implementation capacity.** Larger inventories,
   extra generation requirements, and broad audit instructions correlate with
   incomplete turns before `solution.py` is persisted.
2. **Boundary selection is unreliable.** Agent generation often chooses an easy
   internal boundary (CRUD, build order, persistence, authentication) instead of
   the difficult product boundary (external data, real-time UI, multi-party state).
3. **Selected-boundary success is not task coverage.** Agents can verify every
   stored record while required unselected crossings remain absent.
4. **Self-audit is optimistic.** Later strict audit prompts exposed simulation-only
   real-time, ML, visualization, and external-service implementations that earlier
   reviewers marked fully verified.
5. **Runtime variance is large.** The same X3 configuration changed from 5/5 to
   3/5 workflow completion on a fresh repetition. Single runs cannot select a method.
6. **Reactive sparse repair is safer but incomplete.** X8 avoids burdening initial
   implementation and repairs one observed boundary, but a one-record selector can
   still choose the wrong target and cannot rescue a missing artifact by itself.

## Current conclusion

No tested version is yet a validated improvement for cross-domain collaboration.
X3 is the lowest-complexity proactive candidate; X8 is the most defensible reactive
architecture. Neither is stable enough for the 15-task held-out set.

The next experiment should stop changing prompts and instead use matched repeated
controls with fixed call budgets, plus an independent boundary-coverage evaluator.
The evaluator must derive required crossings from the task independently of the
memory generator and must not accept the Agent's own `interface_audit.json` as truth.
