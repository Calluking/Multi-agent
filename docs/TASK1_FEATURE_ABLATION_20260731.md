# Task 1: Dependency × Cross-domain Memory Smoke Test

Date: 2026-07-31  
Branch: `experiment/cross-domain-interface-memory`  
Model: `deepseek/deepseek-v4-flash`

## Feature matrix

| Condition | Dependency memory | Cross-domain memory |
|---|---:|---:|
| `baseline` | off | off |
| `dependency` | on | off |
| `codomain` | off | on |
| `both` | on | on |

## Valid Task 1 runs

| Condition | Mean Task Score | Workflow complete | Runnable | Dependency recovery | Shared boundaries | Verified boundaries |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` | 4.75/5 | yes | yes | no | 0 | 0 |
| `dependency` | 5.00/5 | yes | yes | yes | 0 | 0 |
| `codomain` | 5.00/5 | yes | yes | no | 1 | 1 |
| `both` | 5.00/5 | yes | yes | no blocker observed | 1 | 1 |

All four valid runs used identical Task, official-task, and AGENTS input hashes.

The `dependency` run observed an incomplete Implementer turn with no `solution.py`, stored one
`artifact_missing` blocker, injected the M3 recovery memory, and recovered to a complete runnable
workflow. In the valid `both` run, the Implementer completed after transient provider retries, so the
dependency observer correctly emitted no blocker and no recovery prompt. The cross-domain mechanism
still produced and verified one shared producer-to-consumer boundary.

## Infrastructure-invalid run

The first `both` attempt scored 1.00/5 but is excluded from the mechanism comparison because the
Implementer recovery, integration specialist, and Reviewer received provider-side `503 Service is too
busy` failures. The raw failed run is retained under the original experiment root. The runner now
retries only transient 503/provider-saturation errors up to three attempts and records them in
`transient_retries.jsonl`.

## Locations

- First four-condition execution (including invalid first `both`):
  `/home/luzh/Multi-agent/experiments/feature_ablation_task1_20260731`
- Valid `both` retry:
  `/home/luzh/Multi-agent/experiments/feature_ablation_task1_both_retry_20260731`

This is a one-task smoke test, not a statistical performance claim. Repetitions and additional tasks
are required before estimating an effect size.
