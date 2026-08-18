---
name: multi-agent-memory
description: Activate universal dependency, co-domain, and testing-practice memory for multi-agent work.
---

# Multi-Agent Memory

First call `memory_capabilities`. Use only mechanisms whose switch is enabled.
Disabled mechanisms are an intentional ablation condition and must not be
simulated in prose or with ad-hoc files.

When dependency memory is enabled, use its tools to maintain the task's real
obligation graph. Do not invent roles, files, checks, or ordering absent from
the request or an accepted delegation.

1. Read the starting request and call `memory_initialize` once. Declare only
   explicit deliverables and explicit dependencies. If the task gives only an
   agent budget, choose a useful topology yourself and declare it as accepted
   spawn assignments before spawning.
   If initialization is rejected, repair its declared schema and retry. When
   Dependency Memory is enabled, native task calls remain blocked until one
   initialization commits successfully; never continue without its graph.
2. Before root work or a native subagent spawn, call `memory_start`. Proceed
   only when it returns `allow`; on `wait`, recover the listed prerequisite.
3. Tell every subagent its obligation ID, exact outputs, and checks. The root
   remains responsible for recording observable results.
   If consequential writable work is discovered after initialization, first
   add it and its incoming edges with `memory_extend_graph`, then gate its
   spawn normally. Work outside the graph is allowed only when the task prompt
   explicitly says `TASK_MODE: auxiliary read-only`; auxiliary work cannot
   modify declared artifacts or satisfy an obligation.
4. After an owner returns, call `memory_observe_artifact` for each output, then
   `memory_verify` for each declared check, then `memory_end`. Call
   `memory_complete` only after evidence is current.
5. Call `memory_inspect` before each dependent spawn and before the final
   response. An agent ending is never completion evidence. A changed artifact
   makes older verification stale and must be reverified.

Independent ready obligations may run in parallel. Never expose private
reasoning through memory; record only assignments, artifacts, checks, and
observable outcomes.

When co-domain memory is enabled, initialize it and create contracts only for
real producer/consumer boundaries grounded in the request, assignments, code,
or artifacts. The producer first proposes a contract containing shared fields,
both sides' obligations, invariants, error semantics, and a real-path check.
The consumer must inspect its sparse projection and either challenge a precise
term or accept it. Resolve every challenge through a versioned producer
revision, then collect separate acceptance from both owners before either side
records implementation evidence. Before integration,
observe current artifacts from both owners, run the exact boundary check, and
obey `codomain_decision`. Co-domain memory gates the crossing, not unrelated
agent spawning. Never substitute disconnected mocks or prose claims for real
producer-to-consumer evidence.

For separate new artifacts, the declared boundary command must execute the
consumer artifact, and that consumer artifact must import or explicitly
reference the producer artifact. A compile-only producer command is not a
producer-consumer boundary check and must remain blocked.

For a new implementation, keep contract negotiation separate from production:
the producer first returns a bounded plan/contract without writing the final
artifact; the consumer reviews it; only after challenge resolution and current
acceptance does the producer implement. Do not ask the producer to create the
entire artifact before the consumer can review the contract.

When testing-practice memory is enabled, call `testing_initialize`, then search
with the current artifact type, action, risk, and verification surface. Treat
the returned one or two practices as guidance only. Declare a verification only
when it comes from the starting request, an actual assignment promise, an
accepted contract, an observed failure, or an explicit adoption. Give every
owner a stable owner ID, call `verification_extract_standard` for that owner
before its native task spawn, and include `Owner ID is: <id>` in the spawn
prompt. The owner is reminded of its observable
behavior, required evidence, and invalid substitutes. Run only the exact
declared command through `verification_run`; never claim PASS from prose or an
earlier artifact version. After failure, preserve evidence, assign one bounded
materially changed repair, and rerun the same acceptance condition. Before the
final response, obey `verification_completion_decision` for authoritative
obligations. Practice retrieval alone never creates a gate or an extra agent.

For every changed or shared interface, derive an interaction matrix before
acceptance: normal input, each explicit error case, every override/default
precedence branch, and backward-compatible use of existing fields or parameters.
Inspect the current implementation to distinguish an existing metadata path
from a newly proposed API. Verification commands must emit a distinct marker
for every required matrix row; merely listing assertions in a tool call is not
evidence. Keep executable verification artifacts until final completion so the
recorded command remains reproducible.

Encode those rows in the mechanism's `interactionCases`. For every existing or
shared interface, also supply `interfaceEvidence` with a workspace-relative
source path and a short exact snippet from the implementation inspected before
the change. Give each evidence item an ID and bind every compatibility case to
that ID, baseline path, symbol, and exact command fragment. The fragment must
exercise that existing field, parameter, or call shape in the declared command;
a newly invented parameter does not satisfy backward compatibility.
