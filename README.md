# Universal Multi-Agent Memory

A harness-neutral control plane for multi-agent coding workflows. It provides
three independently switchable mechanisms and an OpenCode adapter layer:

- **Dependency memory** maintains a live obligation graph, gates native agent
  spawning on prerequisites, observes artifacts, and requires current
  executable evidence before releasing dependents.
- **Co-Domain memory** negotiates versioned producer/consumer contracts before
  implementation and verifies the real integration crossing afterward.
- **Testing-Practice memory** gives each owner a scoped verification standard,
  preserves failure evidence, and blocks completion until current artifacts
  pass authoritative checks.

The mechanisms contain no benchmark names, golden patches, task IDs, or
benchmark-specific adapters. The backend state machines in `src/` are separate
from the harness integration in `adapters/`.

## Status

This branch is the clean v2 implementation snapshot. OpenCode is the currently
implemented harness adapter. The backend and protocol are designed so another
harness can expose the same lifecycle operations without changing mechanism
semantics.

## Install and verify

Requirements: Node.js 20 or newer and npm.

```bash
npm ci
npm test
```

`npm test` builds the TypeScript backends and runs the backend plus adapter
conformance suite.

## OpenCode setup

Add the three local adapters to a workspace `.opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "file:///absolute/path/adapters/opencode/dependency-memory-v2.mjs",
    "file:///absolute/path/adapters/opencode/codomain-memory.mjs",
    "file:///absolute/path/adapters/opencode/testing-practice-memory.mjs"
  ]
}
```

Copy `skills/multi-agent-memory/SKILL.md` to the harness skill directory, then
start a task with one additional line:

```text
Use $multi-agent-memory to complete this task.
```

Select mechanisms outside the task prompt:

```bash
MAM_MECHANISMS=all
MAM_MECHANISMS=dependency
MAM_MECHANISMS=codomain
MAM_MECHANISMS=testing
MAM_MECHANISMS=none
```

Comma-separated combinations are also supported. Disabled mechanisms do not
read stale state, inject guidance, or enforce gates.

## Repository layout

- `src/` — harness-neutral TypeScript memory banks and state transitions
- `adapters/opencode/` — OpenCode tools and lifecycle hooks
- `skills/multi-agent-memory/` — single-line activation workflow
- `design/` — normative mechanism and implementation specifications
- `test/` — backend, adapter, toggle, and protocol conformance tests

Start with [SYNCHRONIZED_STATE.md](design/SYNCHRONIZED_STATE.md), then read the
mechanism-specific design and implementation documents.

## Experimental discipline

Task quality and mechanism conformance are separate outcomes. A generated
solution may fail a benchmark even when spawning, negotiation, evidence, and
completion gates behave correctly. Comparisons should use matched prompts with
only the activation line added and should record resolved switches, model,
harness version, prompt hash, and implementation revision.

## License

Licensed under the [Mulan Permissive Software License, Version 2](LICENSE).
