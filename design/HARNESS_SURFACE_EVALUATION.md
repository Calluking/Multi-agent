# Universal Memory Protocol: Harness Surface Evaluation

## Decision

The system should be a **universal multi-agent memory protocol** distributed as a
plugin/backend package with four surfaces:

```text
Universal memory protocol
├── backend/core
├── activation skill
├── explicit memory tools
└── optional generic runtime hooks
```

It should not be a benchmark-specific adapter, fixed workflow, or collection of
benchmark-specific prompts.

## Intended user flow

The protocol is activated from the starting task prompt:

```text
Use $multi-agent-memory to complete this task.

[task]
```

Activation must:

1. create or resume a memory run;
2. attach the run to the current project/workspace;
3. expose the three memory mechanisms;
4. expose explicit memory tools;
5. make the protocol's operating rules available to the agent.

Activation must **not** create a planner, implementer, reviewer, fixed artifact
graph, or assumed handoff sequence.

The initial dependency graph is derived only from the explicit task. Further
obligations are added only from actual assignments, declarations, artifacts,
commands, and handoffs observed during execution.

## Responsibility split

### Backend/core

The backend is the mechanism implementation and owns:

- dependency obligations and graph state;
- co-domain contract state and negotiation history;
- reusable testing-practice memory;
- run/project identity and isolation;
- normalized event ingestion and replay;
- artifact versions and hashes;
- verification evidence;
- sparse agent projections;
- readiness, handoff, recovery, and completion decisions.

The backend must be harness-independent. It consumes normalized events and
returns state transitions, projections, and gate decisions.

```text
normalized event
    -> backend state transition
    -> projection, evidence update, or gate decision
```

### Activation skill

The skill is the user-facing activation surface because the desired workflow
starts from one prompt. It teaches the agent:

- that the memory protocol is active;
- how to inspect state and blockers;
- when to declare assignments, handoffs, contracts, and verification;
- that agent claims are not evidence;
- that the protocol does not prescribe a particular team topology.

The skill provides guidance and activation. It must not be the sole enforcement
mechanism.

### Explicit tools

Tools provide information or actions that the harness cannot reliably infer:

- activate or inspect a run;
- declare an ambiguous assignment;
- declare a handoff;
- propose, challenge, revise, or accept a shared contract;
- declare a required verification command;
- inspect blockers and recovery state.

Tools must not let an agent falsely mark an artifact as verified, ready, or
complete. Those states require backend-observed evidence.

### Generic runtime hooks

Hooks improve observation and enforcement when the harness provides them. They
are not the activation surface and must not contain benchmark policy.

Useful generic observations include:

- agent or subagent creation;
- assignment delivery;
- tool calls and results;
- file changes;
- command completion;
- handoff messages;
- agent termination;
- completion attempts.

Where supported, hooks may also block or revise actions. Where unsupported, the
protocol must degrade explicitly to advisory or partially enforced operation.

## Harness findings

### OpenCode

OpenCode supports:

- JavaScript/TypeScript plugins;
- project and global plugin loading;
- plugin hooks for tool execution, commands, files, messages, and sessions;
- custom tools;
- Markdown skills loaded through the native `skill` tool.

References:

- <https://opencode.ai/docs/plugins>
- <https://opencode.ai/docs/skills>

### OpenClaw

OpenClaw supports:

- installable plugins;
- plugin-provided skills;
- custom tools;
- prompt and tool hooks;
- agent finalization hooks;
- subagent spawn and termination hooks;
- gateway lifecycle hooks.

References:

- <https://github.com/openclaw/openclaw/blob/main/docs/plugins/hooks.md>
- <https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md>

## Compatibility conclusion

The proposed identity is implementable in both harnesses:

```text
same protocol core
same activation semantics
same memory tools
same normalized event model
different native loading and hook registration
```

The only harness-specific code should be a thin generic runtime bridge that
maps native lifecycle events into the shared backend event model. It must not
know benchmark names, expected roles, expected files, task topology, or
evaluation rules.

The activation syntax may differ by harness:

```text
OpenCode: native skill invocation
OpenClaw: $multi-agent-memory or installed skill invocation
```

That is packaging syntax, not mechanism logic.

## Capability levels

The protocol must declare the capabilities available in the current harness:

```text
Level 0: backend + skill + explicit tools
         guidance and inspectable state

Level 1: plus lifecycle observation
         automatic artifact, command, and agent tracking

Level 2: plus action interception
         readiness, handoff, and completion gates

Level 3: plus continuation/recovery control
         automatic repair scheduling and incomplete-turn recovery
```

The system must never claim that a gate was enforced when the active harness
could only report it.

## Cross-harness acceptance target

The same task and activation prompt should be runnable in both harnesses:

```text
same task + same protocol invocation
    -> equivalent memory state
    -> equivalent obligation decisions
    -> equivalent evidence rules
```

Differences should be attributable only to declared harness capabilities, not
to benchmark-specific logic or hidden workflow assumptions.

## Repository references inspected

- OpenCode checkout: `/home/luzh/opencode`
- OpenClaw checkout: `/home/luzh/openclaw`
- Existing plugin implementation: `openclaw_plugin/`
- V2 mechanism specifications: `design/v2/`
