---
name: multiagent-memory
description: Use when coordinating subagents whose work has dependencies, cross-domain interfaces, or verification responsibilities.
---

# Multi-Agent Memory

The plugin automatically injects selected memory when `sessions_spawn` is called. Do not manually paste the entire memory bank into child prompts.

Before spawning:

1. Write a concrete child objective: expected artifact, relevant producer/consumer boundary, and verification evidence.
2. Use `multiagent_memory_inspect` only when you need to preview retrieval or diagnose a surprising injection.
3. Call `sessions_spawn` normally. The plugin appends the relevant private dependency, shared co-domain contract, and team testing-practice records.

During or after work, use `multiagent_memory_record` only for a durable typed fact:

- `dependency/private`: current prerequisite, blocker, target state, or acceptance evidence for one execution context.
- `codomain/shared`: producer/consumer fields, semantics, invariants, boundary tests, challenge, or agreed revision.
- `testing/shared`: reusable verification rule or evidence standard confirmed by an execution episode.

Do not store free-form chat, guesses, secrets, or an unverified success claim.
