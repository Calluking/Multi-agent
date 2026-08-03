# Inject-only Testing Practice Memory — Task 11 Example

## Mechanism boundary

Testing Practice Memory is a prompt-time intervention only:

```text
existing Agent start
  -> retrieve role-relevant semantic practices
  -> append a compact working-memory packet
  -> run the existing Agent turn once
  -> observe the outcome and store a compact episode
  -> continue the original workflow
```

It adds no Agent call, completion gate, rerouting, or automatic retry. Dependency
and co-domain memory were disabled in this test.

## Toggle

The feature runner now exposes all eight combinations of three independent flags:

| Condition | Dependency | Co-domain | Testing practice |
|---|:---:|:---:|:---:|
| `baseline` | off | off | off |
| `dependency` | on | off | off |
| `codomain` | off | on | off |
| `both` | on | on | off |
| `testing` | off | off | on |
| `dependency_testing` | on | off | on |
| `codomain_testing` | off | on | on |
| `all_three` | on | on | on |

## Why Task 11

The original baseline's central Testing/TDD fault was a false green result: the
task required machine learning over historical and current performance, but the
Planner, Implementer, tests, and Reviewer accepted fixed averages, variance, and
threshold heuristics as ML. The suite passed without testing fitted state or
data-dependent behavior.

## Retrieved memory

The corrected role-aware retriever selected:

| Role | Practice memories |
|---|---|
| Planner | `reject_semantic_substitute` |
| Implementer | `reject_semantic_substitute`, `require_executed_evidence` |
| Reviewer | `reject_semantic_substitute`, `independent_requirement_audit` |

Total injected text was 3,740 characters. The result explicitly records:

```json
{
  "mode": "inject_only",
  "extra_agent_calls": 0,
  "rerouting": false,
  "automatic_retry": false
}
```

## Baseline versus final ON run

| Observation | Memory OFF | Memory ON |
|---|---|---|
| Mean Task Score | 4.75 / 5 | 4.25 / 5 |
| Workflow complete | yes | yes |
| Default `python3 solution.py` | exit 0 | exit 0 |
| ML implementation | fixed statistical heuristics | fitted data-dependent statistical model |
| Defining-capability test | absent | present |
| Independent counterexample | absent | trending vs flat history |
| Reviewer claim | heuristic accepted as ML | learned behavior directly probed |
| Testing/TDD fault under the baseline criterion | present | not observed |

The ON run fitted a model from gameplay history and tested that changed historical
patterns changed predictions. The Reviewer independently tested trending and flat
histories, repaired a separate multi-game defect, reran the default entrypoint,
and reported the model's capability boundary instead of claiming a stronger form
of ML.

## Development iteration

The first ON development run demonstrated the desired semantic correction but
scored 3.50 because the generated CLI required a subcommand, so the harness's
default `python3 solution.py` invocation exited 2. Inspection also showed that a
Reviewer-only memory had leaked into the Implementer packet.

The implementation was then corrected at the retrieval layer:

1. Practices are now filtered by eligible role before ranking.
2. Executed-evidence memory now requires the exact default entrypoint used by the
   task or harness.

The final ON run exited 0 and scored 4.25. This was a mechanism-development
iteration between separate benchmark runs, not runtime retry or Agent rerouting.

## Interpretation

This single task verifies the intended causal path:

```text
historical false-green practice
  -> role-aware retrieval
  -> prompt injection
  -> acceptance target changes
  -> implementation exposes fitted state
  -> tests use a counterexample
  -> Reviewer verifies learned behavior
```

It does not establish overall score improvement. The stricter implementation
received a lower single-run Task Score than baseline (4.25 versus 4.75), despite
removing the audited Testing/TDD fault. More tasks and repetitions are required
to evaluate usefulness, cost, and regressions.

## Reproduction

```bash
cd dependency_memory/v4_sparse

python3 run_feature_ablation.py \
  --tasks 11 --condition baseline \
  --root ../../../experiments/testing_memory_task11_20260731/off

python3 run_feature_ablation.py \
  --tasks 11 --condition testing \
  --root ../../../experiments/testing_memory_task11_20260731/on_v2
```

