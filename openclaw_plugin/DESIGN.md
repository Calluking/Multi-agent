# Plugin design: memory at subagent creation

## Decision

Use a native mixed-capability OpenClaw plugin, not a Skill alone.

| Surface | Responsibility | Why |
|---|---|---|
| `before_tool_call` hook on `sessions_spawn` | Retrieve and inject memory into the child task | Runs on the actual creation path; the coordinator cannot accidentally skip it |
| `subagent_spawned` / `subagent_ended` hooks | Bind injection to the real child and record outcome | Gives lifecycle identity and avoids confusing completion events |
| `multiagent_memory_record` tool | Typed contribution to one bank | Lets Agents challenge/update memory without editing raw bank files |
| `multiagent_memory_inspect` tool | Retrieval preview and diagnosis | Makes injection observable |
| Bundled Skill | Usage semantics | Useful guidance, but deliberately not the enforcement mechanism |

## Three non-duplicated positions

### 1. Private dependency memory — execution state

- Answers: **What must this child receive or produce before handoff?**
- Scope: one child/session/target.
- Typical state: missing, blocked, produced, verified.
- Injected when the child objective overlaps the target or when the record belongs to its parent execution context.

### 2. Shared co-domain contract memory — boundary meaning

- Answers: **What do producer and consumer mean by a compatible interface?**
- Scope: shared by only the participants at that boundary, not broadcast blindly to every Agent.
- Typical content: producer, consumer, artifact, fields, semantics, invariants, boundary tests, version, challenge.
- Injected by semantic relevance to the spawned task.

### 3. Shared testing-practice memory — reusable team procedure

- Answers: **What verification responsibility and evidence standard applies here?**
- Scope: team/practice knowledge selected by task semantics.
- Typical content: rule, invalid substitute, required executable evidence, learned episode.
- Inject-only: it does not add retries or rerouting.

## Spawn flow

```text
Coordinator calls sessions_spawn(task)
            |
            v
before_tool_call hook
  - identify parent session
  - retrieve 3 banks independently
  - append a bounded packet to task
  - store injection id + selected ids
            |
            v
OpenClaw creates child session
            |
            v
subagent_spawned binds injection id -> childSessionKey
            |
            v
Child works and may contribute typed memory records
            |
            v
subagent_ended records a compact episode
```

## Important implementation boundary

Version 0.1 proves the native OpenClaw integration seam. It uses deterministic lexical retrieval and typed JSON persistence. It does **not yet** port the complete benchmark-tested extraction and state machines from `dependency_memory/v4_sparse`; that is the next integration step after runtime validation.
