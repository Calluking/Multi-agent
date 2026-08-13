# CooperBench integration

For copy-paste setup, execution, evaluation, and validity checks, see
[`RUNBOOK.md`](RUNBOOK.md).

This integration starts from CooperBench's native CLI and evaluator. The
verified baseline uses the repository's `mini_swe_agent_v2`, Docker backend,
and DeepSeek without importing or patching CooperBench.

## Verified DeepSeek solo baseline

Prerequisites in WSL:

```bash
cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
uv pip install 'httpx[socks]'
docker info
docker ps | grep redis
test -n "$DEEPSEEK_API_KEY"
test -n "$DEEPSEEK_BASE_URL"
```

Run and evaluate the default task:

```bash
cd /path/to/Multi-Agent_Contract_Protocol
bash benchmarks/cooperbench/run_deepseek_solo.sh
```

Use a unique run name or override the task without editing the script:

```bash
RUN_NAME=deepseek-two TASK_ID=17070 \
  bash benchmarks/cooperbench/run_deepseek_solo.sh
```

`TASK_ID` must contain digits only (`17070`, not `task17070`). Results remain
in the CooperBench checkout under `logs/<run-name>/solo/`.

### Reproduced result

On 2026-08-12, `deepseek-codex-one` completed all three feature pairs for
`llama_index_task/17070` in 9m45s. CooperBench's native evaluator reported:

| Feature pair | Result |
| --- | --- |
| `[1,2]` | fail |
| `[1,3]` | pass |
| `[2,3]` | pass |
| Overall | **2/3 (66.7%)** |

This is a valid agent-level failure, not a timeout or harness failure.

## Scope boundary

The verified command uses `--setting solo`. It validates CooperBench setup,
DeepSeek access, task execution, patch production, and native evaluation. It
does **not** measure MACP: a solo run has no multi-agent handoff for the plugin
to govern.

Plugin on/off comparisons must therefore use the same CooperBench revision,
task, feature pairs, model, agent adapter, backend, concurrency, and evaluator,
with a multi-agent setting and an explicit MACP-capable adapter. Until that
adapter exists and its trace invariants pass, solo results must not be labeled
as plugin results.

## OpenClaw + MACP cooperative adapter

`run_openclaw_macp.py` runs one CooperBench feature pair through an OpenClaw
coordinator and exactly two feature-owner children. It copies the official task
image's base repository for each owner, never exposes golden patches, and emits
CooperBench's standard cooperative `agent<feature>.patch` files.

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py with_plugin \
  --name macp-deepseek-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2

cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
cooperbench eval -n macp-deepseek-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
```

Use `without_plugin` and a different run name for the matched control. Task
image, model, prompt, child topology, patch format, and native evaluator stay
fixed; only the OpenClaw plugin toggle changes.

The plugin-enabled `llama_index_task/17070 [1,2]` smoke produced two non-empty
patches and CooperBench's native evaluator passed both features (100%). It also
exposed and fixed three generic lifecycle issues: peer-relative artifact path
resolution, false verification from `pytest --version`, and test failures hidden
by successful shell pipelines such as `pytest ... | tail`.

The replacement will be built incrementally against an unmodified official
CooperBench checkout. No full A/B benchmark run is permitted until each gate
below passes with one frozen model and configuration.

## Validation gates

1. Run the native CooperBench baseline without importing MACP. **Passed.**
2. Run an OpenClaw coordinator with two feature owners. **Passed with plugin.**
3. Run the identical adapter with the plugin disabled. **Passed.**
4. Enable dependency memory and validate its trace invariant. **Passed.**
5. Enable co-domain memory and validate its trace invariant. **Discovery passed; combined-tree enforcement pending.**
6. Enable testing-practice memory and validate its trace invariant. **Record creation passed; combined-tree enforcement pending.**
7. Require two non-empty standard cooperative patches. **Passed.**
8. Run `cooperbench eval` and retain its native output. **Passed: 100% for `[1,2]`.**
9. Execute matched disabled/enabled trials with every non-plugin variable fixed. **Runnable five-pair baseline complete: 2/5 versus 2/5.**

The frozen baseline and its raw-memory interpretation are documented in
[`RUNBOOK.md`](RUNBOOK.md). In particular, successful handoff collection must
not be confused with verified integration correctness: the current repair
target is to require one merged integration tree and current evidence for all
co-domain and testing obligations before coordinator completion.

## Fixed-comparison rule

The enabled and disabled conditions must use the same CooperBench revision,
task, model identifier, harness version, prompt, tools, timeout, retries,
concurrency, and evaluator. The only allowed difference is MACP enablement and
its documented hook injection.

Historical failed-run notes are not benchmark scores.

The correctness-gate repair and its native-evaluator smoke result are recorded
in the final section of [`RUNBOOK.md`](RUNBOOK.md). The adapter exports the
verified integrated artifact while retaining raw producer patches separately.
