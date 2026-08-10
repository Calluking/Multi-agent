# Validation

This document separates runtime/plugin validation from benchmark outcomes. Run the deterministic suite with:

```bash
npm test
```

## Regression suite

| Area | Coverage |
|---|---|
| Workspace and assignment resolution | Native and universal workdir forms |
| Memory persistence | Concurrent writes, deduplication, project/run isolation |
| Handoffs | Artifact observation, readiness gates, bounded recovery |
| Contracts | Proposal, revision, acceptance, stale-version rejection |
| Evidence | Exact commands, artifact-version binding, invalidation |
| Completion | Producer and root completion gates |

All listed regression scripts pass on the current release branch.

## Benchmark snapshot

| Benchmark | Configuration | Result |
|---|---|---|
| MultiAgentBench task 1 | Testing-only ablation | 95/100 evaluator mean |
| CooperBench task 0 | Testing-only ablation | 2/2 evaluator tests passed |
| MultiAgentBench five-task panel | Repaired full plugin | 87/100 |
| CooperBench five-task panel | Repaired full plugin | 20/100; one paired task passed |

The panel scores are retained as honest baselines for future improvements. The focused co-domain work also passes the combined cross-feature composition test, while two individual feature semantics remain known follow-up work.

## Reproduction

Benchmark harnesses and raw reports live under the parent repository's `experiments/` and `desgin/FINAL_VALIDATION.md`. The plugin's own tests are self-contained and do not require benchmark model credentials.

---

## Historical runtime validation

Validated on 2026-08-04 with OpenClaw 2026.6.10.

## Runtime registration

`openclaw plugins inspect multiagent-memory --runtime --json` reported:

- status: `loaded`
- typed hooks: `before_tool_call`, `subagent_spawned`, `subagent_ended`
- tools: `multiagent_memory_record`, `multiagent_memory_inspect`
- hook count: 3
- diagnostics: none

## Task 17 real subagent probe

- Creation path: native `sessions_spawn`
- Child session: `agent:mab-plugin-spawn-probe-t17:subagent:b806e846-f0ff-42fe-ad3d-e15163ba5258`
- The child transcript contained all three plugin-injected sections and a unique injection id.
- Child created `solution.py` and ran it to green.
- Coordinator independently reran `python3 solution.py`.
- Result: exit `0`, `PASS 52 FAIL 0`, `ALL TESTS PASSED (52 checks)`.
- Coordinator repair: none.

## Lifecycle correlation probe

After correcting parent correlation to use `ctx.requesterSessionKey`:

- one native child created `lifecycle_probe.txt` containing `LIFECYCLE_OK`;
- `subagent_spawned` bound the pending injection to the real child key;
- `subagent_ended` wrote `episode:inject:1785829241224:ofcg4x`;
- recorded outcome: `ok`;
- episode retained the three selected memory ids.

## What this proves

The plugin is on the real subagent creation and completion path. It can inject bounded memory before work and persist a correlated episode afterward. It does not yet prove that the generic lexical banks match the effectiveness of the benchmark-specific Python memory implementation across all 20 tasks.

## Universal control-plane validation

The completed pre-benchmark plugin registers these native hooks:

- `before_prompt_build`
- `before_tool_call`
- `after_tool_call`
- `before_agent_finalize`
- `subagent_spawned`
- `subagent_ended`

Runtime inspection reports both memory tools, six typed hooks, and no plugin diagnostics. The local OpenClaw entry explicitly enables `hooks.allowConversationAccess` so the project-scoped completion gate can inspect terminal intent.

The automated suite verifies concurrency, structured deduplication, project/run isolation, arbitrary assignment ownership, artifact observation, version-bound command evidence, readiness and bounded recovery, completion blocking/release, contract version lifecycle, role/assignment targeting, and product co-domain filtering.
