# Multi-Agent Contract Protocol

> A memory-backed protocol that keeps collaborating agents aligned on prerequisites, interface contracts, and executable evidence.

[![OpenClaw Plugin](https://img.shields.io/badge/OpenClaw-native%20plugin-6f42c1)](https://github.com/openclaw/openclaw)
[![Tests](https://img.shields.io/badge/regression%20suites-13%20passing-2ea44f)](./VALIDATION.md)
[![MultiAgentBench](https://img.shields.io/badge/MultiAgentBench-task%20passed-2ea44f)](../desgin/FINAL_VALIDATION.md)
[![CooperBench](https://img.shields.io/badge/CooperBench-34%20tests%20passed-2ea44f)](../desgin/FINAL_VALIDATION.md)

![Multi-Agent Contract Protocol coordinating verified agent handoffs](https://gitcode.com/lukchiwang/Multi-Agent_Contract_Protocol/-/raw/main/openclaw_plugin/docs/assets/macp-hero.png)

Multi-Agent Memory turns memory from passive prompt context into an active coordination layer. It observes the real OpenClaw agent lifecycle, injects only the memory relevant to each assignment, blocks consumers whose prerequisites are not ready, sends prematurely finishing producers back to complete their artifacts, and refuses final completion until the workflow has objective evidence.

The protocol is designed to be CLI-independent. OpenClaw is the first adapter; the contract model can be reused by any runtime that exposes agent spawn, tool-call, and completion events.

The plugin is role-agnostic: `planner`, `implementer`, and `reviewer` are supported, but arbitrary assignment names and peer topologies work as well. That lets the same control plane serve sequential workflows such as MultiAgentBench and parallel/cooperative workflows such as CooperBench.

## Why this exists

Ordinary agent memory helps an agent remember information. Multi-agent execution also needs to remember **who owes what to whom, which version is current, and what evidence makes a handoff safe**.

Without an enforcement layer, a team can still fail even when the relevant fact is stored:

- an implementer acknowledges an assignment but never writes the requested files;
- a reviewer starts before the implementation exists;
- two peers silently disagree about a shared interface;
- an old passing test is reused after the artifact changes;
- the coordinator declares success while obligations remain unresolved.

This plugin converts those conditions into lifecycle gates rather than suggestions.

## System at a glance

![Architecture overview showing OpenClaw agents, lifecycle hooks, enforcement, and the three typed memory banks](https://gitcode.com/lukchiwang/Multi-Agent_Contract_Protocol/-/raw/main/openclaw_plugin/docs/assets/architecture-overview.svg)

The three banks have deliberately different jobs:

| Memory | Question answered | Scope | Examples |
|---|---|---|---|
| Dependency | What must be available before this handoff? | Private to a workflow edge | producer, consumer, artifact path, state, recovery owner |
| Co-domain contract | What does compatibility mean at this shared boundary? | Shared only by participating assignments | fields, semantics, invariants, version, acceptance, boundary evidence |
| Testing practice | What procedure and evidence establish correctness? | Reusable team knowledge | exact command, invalid substitutes, learned execution episode |

## The enforced lifecycle

![Enforced lifecycle from assignment through producer checkpoint, consumer gate, and root completion](https://gitcode.com/lukchiwang/Multi-Agent_Contract_Protocol/-/raw/main/openclaw_plugin/docs/assets/enforced-lifecycle.svg)

![Handoff sequence from spawn to verified completion](https://gitcode.com/lukchiwang/Multi-Agent_Contract_Protocol/-/raw/main/openclaw_plugin/docs/assets/handoff-sequence.svg)

This producer-finalization checkpoint is important. Dependency memory does not merely tell a later reviewer that something is missing; it prevents the responsible child from ending after an acknowledgment when its owned artifact or verification obligation is still unresolved.

## Control-plane gates

The lifecycle has three deliberate enforcement boundaries: a producer checkpoint before a child exits, a consumer gate before a dependent assignment starts, and a root completion gate before the coordinator reports success. Every boundary re-observes the workspace instead of trusting a status claim.

### What the plugin observes

| OpenClaw seam | Plugin action |
|---|---|
| `before_prompt_build` | Initializes task-local memory and adds control-plane guidance to the root session |
| `before_tool_call` on `sessions_spawn` | Resolves identity/workspace, observes artifacts, enforces recovery and readiness, injects memory |
| `after_tool_call` | Records exact-command results and binds successful evidence to current artifact hashes |
| `before_agent_finalize` for children | Blocks acknowledgment-only completion when producer obligations remain |
| `before_agent_finalize` for root | Blocks terminal completion while artifacts or contracts remain unresolved |
| `subagent_spawned` | Binds the pending packet to the real child session and assignment |
| `subagent_ended` | Records lifecycle outcome, recovery ownership, and a compact execution episode |

## Evidence is version-bound

A successful command is not permanent truth. Verification is accepted only when it matches the configured command and the current artifact version.

The evidence lifecycle is intentionally reversible: **blocked → produced → verified → ready**. A file edit after verification moves the artifact back to **produced**; a failed command or timed-out child moves it to **blocked** and assigns recovery ownership.

For shared interfaces, contracts follow a similarly explicit lifecycle: proposal → challenge/revision → acceptance → verification. Stale-version transitions are rejected, and real boundary evidence is required before workflow completion.

## Universal assignment model

The plugin does not hard-code a three-role pipeline. Each spawn can register an arbitrary assignment ID, workspace, produced artifacts, consumers, and contracts.

The same assignment model supports both shapes:

- **Sequential:** planner → implementer → reviewer
- **Cooperative:** independent peers → integration owner → combined verification

## Safety and failure behavior

- **Observer-owned readiness:** workflow artifacts cannot be marked ready through the generic memory tool.
- **Project/run isolation:** one benchmark run cannot satisfy or block another run accidentally.
- **Bounded recovery:** failed owners receive a changed-strategy recovery obligation; repeated identical retries are not unlimited.
- **Scoped retrieval:** memory banks are ranked independently and only a bounded packet is injected.
- **Atomic persistence:** writes are serialized per bank and committed through temporary-file rename.
- **Fail-open initialization:** failure to derive initial task memory does not corrupt the original OpenClaw request.
- **Fail-closed handoffs:** known unresolved workflow obligations block the relevant consumer or completion boundary.

## Quick start

```bash
git clone https://gitcode.com/lukchiwang/Multi-Agent_Contract_Protocol.git
cd Multi-Agent_Contract_Protocol/openclaw_plugin
npm install
npm test
npm run build
```

The OpenClaw adapter is configured through `openclaw.plugin.json`. Dependency, co-domain, and testing memory can be enabled independently for ablation studies or incremental adoption.

## Examples

See [`examples/`](./examples/) for sequential planner/implementer/reviewer workflows, cooperative peer handoffs, and memory-mechanism toggles.

## Validation

Benchmark results and reproducible evaluator commands are documented in [`VALIDATION.md`](./VALIDATION.md). The regression suite covers workspace resolution, concurrent writes, project isolation, artifact observation, contract lifecycle, readiness gates, completion gates, and exact-command evidence.

## Installation

### Prerequisites

- OpenClaw with native plugin support
- Node.js and npm
- An OpenClaw gateway configuration that permits conversation-aware hooks

### Build and link

```bash
cd /home/luzh/Multi-agent/openclaw_plugin
npm install
npm test

openclaw plugins install --link "$PWD"
openclaw plugins enable multiagent-memory
openclaw gateway restart
openclaw plugins inspect multiagent-memory --runtime --json
```

The final inspection should report the plugin hooks and tools with no diagnostics. This package is a mixed Hook + Tool plugin built with `definePluginEntry`; runtime inspection is the authoritative registration check.

### Configuration

```json5
{
  plugins: {
    entries: {
      "multiagent-memory": {
        enabled: true,
        hooks: {
          allowConversationAccess: true
        },
        config: {
          storeRoot: "/home/luzh/.openclaw/multiagent-memory",
          autoInitialize: true,
          dependencyEnabled: true,
          codomainEnabled: true,
          testingEnabled: true,
          maxItemsPerMemory: 3,
          maxRecoveryAttempts: 2
        }
      }
    }
  },
  tools: {
    allow: [
      "multiagent_memory_record",
      "multiagent_memory_inspect",
      "multiagent_contract_transition"
    ]
  }
}
```

Optional development seed data can be installed with:

```bash
mkdir -p /home/luzh/.openclaw/multiagent-memory
cp seed/*.json /home/luzh/.openclaw/multiagent-memory/
```

## Memory tools

The plugin exposes three typed tools:

| Tool | Purpose |
|---|---|
| `multiagent_memory_record` | Add or update dependency, contract, or testing-practice knowledge; cannot forge observer-owned workflow readiness |
| `multiagent_memory_inspect` | Preview scoped retrieval and diagnose what would be injected |
| `multiagent_contract_transition` | Propose, challenge, revise, accept, or verify a versioned shared interface contract |

The bundled skill explains correct tool semantics. The hooks—not the skill—enforce execution safety.

## Validation

The local test command builds the TypeScript plugin and runs eleven behavioral suites:

```bash
cd /home/luzh/Multi-agent/openclaw_plugin
npm test
```

Covered behaviors include concurrent writes, deduplication, project isolation, universal assignment adaptation, artifact observation, version-bound verification, producer/consumer readiness, lifecycle recovery, completion gating, contract state transitions, targeting, and co-domain filtering.

End-to-end internal evidence:

| Benchmark | Topology | Result |
|---|---|---|
| Universal prompt suite | five varied multi-agent topologies | **5/5** mechanisms and external checks passed |
| MultiAgentBench five-task adaptation | planner → implementer → reviewer | **4.20/5** evaluator mean; 5/5 valid runs |
| CooperBench-derived five-task harness | two peers → integration | **5/10** feature tests; 2/5 complete pairs |

The CooperBench-derived number is not an official CooperBench score. The failed experimental official adapter has been removed; [`benchmarks/cooperbench`](./benchmarks/cooperbench/) documents the gated rebuild required before CooperBench support can be claimed. See [validation details](./VALIDATION.md) and the [architecture design](./DESIGN.md).

## Repository layout

```text
openclaw_plugin/
├── src/
│   ├── index.ts             # OpenClaw hooks and registered memory tools
│   ├── memory-engine.ts     # retrieval, lifecycle gates, observation, persistence
│   └── schema.ts            # typed memory records and tool schemas
├── skills/                  # bundled agent-facing usage guidance
├── seed/                    # optional initial memory-bank records
├── test/                    # behavioral regression suites
├── benchmarks/
│   ├── multiagentbench/     # working coding-task adaptation and judge
│   └── cooperbench/         # clean-restart gates; adapter not yet implemented
├── DESIGN.md                # detailed design decisions
├── VALIDATION.md            # plugin validation notes
└── openclaw.plugin.json     # plugin manifest and configuration schema
```

## Design principle

> Memory should not only help agents remember the plan. It should make unsafe handoffs impossible to mistake for progress.

This plugin ports the ideal dependency-memory architecture into OpenClaw’s native lifecycle and generalizes it from one benchmark workflow to arbitrary multi-agent assignments.

## Presentation references

The documentation style was informed by the clear, architecture-first introductions used by [TencentDB Agent Memory](https://github.com/TencentCloud/tencentdb-agent-memory) and [openGauss oGMemory](https://gitcode.com/opengauss/oGMemory). Multi-Agent Memory has a different focus: lifecycle enforcement and coordination across multiple executing agents rather than a general-purpose memory service alone.
