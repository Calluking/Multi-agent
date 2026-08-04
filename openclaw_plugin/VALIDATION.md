# Runtime validation

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
