# CooperBench runbook

This integration keeps CooperBench itself unmodified. Run commands from WSL.

## 1. Prerequisites

```bash
cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
uv pip install 'httpx[socks]'
docker info
docker ps | grep redis
test -n "$DEEPSEEK_API_KEY"
test -n "$DEEPSEEK_BASE_URL"
```

The CooperBench task ID is numeric: use `17070`, not `task17070`.

## 2. Verify the official solo baseline

From this plugin repository:

```bash
RUN_NAME=deepseek-solo-17070 TASK_ID=17070 \
  bash benchmarks/cooperbench/run_deepseek_solo.sh
```

The script runs CooperBench's official `mini_swe_agent_v2` with the Docker
backend and then invokes the native evaluator. Results are stored in:

```text
~/cooperbench-run/CooperBench/logs/deepseek-solo-17070/solo/
```

## 3. Run an OpenClaw cooperative feature pair

Plugin disabled:

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py without_plugin \
  --name openclaw-off-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2
```

Plugin enabled:

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py with_plugin \
  --name openclaw-macp-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2
```

Evaluate each run with CooperBench, not a custom scorer:

```bash
cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
cooperbench eval -n openclaw-off-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
cooperbench eval -n openclaw-macp-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
```

## 4. Valid comparison rules

Keep the CooperBench revision, task, feature pair, model, prompt, topology,
timeouts, retries, Docker backend, and evaluator identical. Only plugin
enablement may differ. Do not score missing/partial patches as an agent-quality
result when the trace contains a gateway lock, provider timeout, or interrupted
coordinator. Preserve the run directory and stderr for diagnosis.

## 5. Frozen runnable baseline (commit `7713026`)

The current adapter is runnable end to end with the commands above. A frozen
five-pair comparison used these cases:

| Task | Feature pair |
| --- | --- |
| `17070` | `1,2` |
| `17070` | `1,3` |
| `17070` | `2,3` |
| `17244` | `1,2` |
| `17244` | `1,3` |

Native CooperBench evaluation produced **2/5 without the plugin and 2/5 with
the plugin**. The plugin nevertheless changed control-plane behavior: clean
coordinator completion improved from 1/5 to 5/5, two harvested producer
handoffs improved from 1/5 to 5/5, and session-lock failures fell from 4/5 to
0/5.

This is the preserved runnable baseline, not proof that all three memory
mechanisms enforce implementation correctness.

## 6. Known correctness-enforcement gap

Inspect the memory store after an enabled run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path('~/.openclaw/multiagent-memory').expanduser()
for kind in ('dependency', 'codomain', 'testing'):
    bank = json.loads((root / f'{kind}.json').read_text())
    rows = [item for item in bank.get('items', [])
            if 'cooperbench' in json.dumps(item).lower()]
    print(kind, [(row.get('id'), row.get('status')) for row in rows])
PY
```

In the frozen five-pair run, dependency memory observed all 10 producer
handoffs, but only 2/5 co-domain contracts and 2/10 producer testing records
were verified. Some coordinators still finalized while contracts remained
`agreed` and tests remained `required`.

Therefore interpret this revision as follows:

- dependency/handoff enforcement is working;
- co-domain discovery is working, but combined-tree verification is incomplete;
- testing-practice records are created, but combined-tree evidence is not yet
  enforced reliably;
- a valid correctness comparison requires applying both producer patches to
  one integration tree, running every producer boundary suite there, repairing
  failures, and blocking completion until co-domain and composition-testing
  records are verified.

Do not publish the 2/5 versus 2/5 result as evidence that MACP improves or does
not improve implementation quality. It is a reproducible adapter baseline for
the next enforcement repair.

## 7. Correctness-gate repair validation

The subsequent adapter revision keeps the commands in section 3 unchanged and
adds a clean `integration/` checkout. Both producer patches must be composed
there, every producer-declared command must pass there, and joint tests are
required when both features alter one API. Peer-local tests cannot verify
co-domain or composition-testing memory.

The official patch export now represents the mutually accepted integrated
artifact for both cooperative participants. Raw owner contributions remain as
`agent<feature>.producer.patch` for attribution and debugging.

Validated smoke run:

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py with_plugin \
  --name macp-fixed-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2

cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
cooperbench eval -n macp-fixed-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
```

Observed evidence: two submitted producer handoffs; both exact producer suites
passed with 46 tests in the same integration tree; four focused joint tests
passed; co-domain and composition-testing records reached `verified`; and the
native CooperBench evaluator reported **1/1 passed**.

The repaired revision was then validated on the complete frozen five-pair set:

| Task | Feature pair | Native evaluation |
| --- | --- | --- |
| `17070` | `1,2` | pass |
| `17070` | `1,3` | pass |
| `17070` | `2,3` | pass |
| `17244` | `1,2` | pass |
| `17244` | `1,3` | pass |

Final result: **5/5 passed**. Every case was launched from one root task prompt;
the coordinator autonomously spawned both feature owners, collected their
handoffs, integrated the changes, ran combined-tree verification, and completed
only after the dependency, co-domain, and testing gates were satisfied.
