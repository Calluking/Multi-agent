import assert from "node:assert/strict";
import test from "node:test";
import {
  CoDomainMemory,
  InMemoryCoDomainEventStore,
  type CoDomainEvent,
  type ContractDefinition,
  type ContractSemantics,
} from "../src/codomain/index.js";

const RUN = "codomain-run";
const NOW = "2026-08-17T00:00:00.000Z";
type Payload = CoDomainEvent extends infer E ? E extends CoDomainEvent ? Omit<E, "eventId" | "runId" | "observedAt"> : never : never;
const event = <T extends Payload>(eventId: string, value: T) => ({ ...value, eventId, runId: RUN, observedAt: NOW }) as unknown as CoDomainEvent;

const semantics = (meaning = "stable registered-user identity"): ContractSemantics => ({
  fields: [{ name: "user_id", type: "string", meaning }],
  producerObligations: ["return user_id after successful creation"],
  consumerObligations: ["treat missing user_id as protocol failure"],
  invariants: ["the same user_id identifies the entity on both sides"],
  errorSemantics: ["duplicate registration returns conflict without creating state"],
});

const definition = (): ContractDefinition => ({
  contractId: `${RUN}:backend->frontend:user-response`, runId: RUN, interfaceId: "user-response",
  sourceEvidence: ["assignment:backend", "assignment:frontend"],
  producer: { ownerId: "backend", artifacts: ["server/users.py"] },
  consumer: { ownerId: "frontend", artifacts: ["web/user-client.ts"] },
  semantics: semantics(),
  boundaryVerification: { command: "python tests/test_user_boundary.py", expectedExitCode: 0 },
  risk: "high", version: 1,
});

async function proposed() {
  const store = new InMemoryCoDomainEventStore(); const memory = await CoDomainMemory.open(RUN, store);
  await memory.record(event("propose", { type: "contract.proposed", contract: definition(), authorId: "backend" }));
  return { memory, store };
}

async function acceptBoth(memory: CoDomainMemory, version = 1) {
  for (const owner of ["backend", "frontend"]) await memory.record(event(`accept:${version}:${owner}`, {
    type: "contract.accepted", contractId: definition().contractId, version, authorId: owner, evidenceRefs: [`message:${owner}`],
  }));
}

async function observeBoth(memory: CoDomainMemory, suffix = "v1") {
  await memory.record(event(`artifact:backend:${suffix}`, { type: "artifact.observed", contractId: definition().contractId, ownerId: "backend", artifactId: "server/users.py", version: `sha:backend:${suffix}` }));
  await memory.record(event(`artifact:frontend:${suffix}`, { type: "artifact.observed", contractId: definition().contractId, ownerId: "frontend", artifactId: "web/user-client.ts", version: `sha:frontend:${suffix}` }));
}

test("keywords or same-owner components cannot instantiate a contract", async () => {
  const store = new InMemoryCoDomainEventStore(); const memory = await CoDomainMemory.open(RUN, store);
  const invalid = definition(); invalid.consumer.ownerId = "backend"; invalid.sourceEvidence = [];
  await assert.rejects(memory.record(event("keyword-contract", { type: "contract.candidate", contract: invalid })), /source evidence|distinct owners/);
  assert.equal(memory.list().length, 0); assert.equal(store.events.length, 0);
});

test("an observed candidate requires explicit participant promotion to proposed", async () => {
  const store = new InMemoryCoDomainEventStore(); const memory = await CoDomainMemory.open(RUN, store);
  await memory.record(event("candidate", { type: "contract.candidate", contract: definition() }));
  assert.equal(memory.get(definition().contractId)?.agreementState, "candidate");
  await memory.record(event("promote", { type: "contract.proposed", contract: definition(), authorId: "backend" }));
  assert.equal(memory.get(definition().contractId)?.agreementState, "proposed");
  assert.equal(memory.list().length, 1);
});

test("producer and consumer receive different sparse views; unrelated owners receive none", async () => {
  const { memory } = await proposed();
  const producer = memory.projectForOwner("backend")[0]; const consumer = memory.projectForOwner("frontend")[0];
  assert.equal(producer?.role, "producer"); assert.equal(consumer?.role, "consumer");
  assert("consumerAssumptions" in (producer ?? {})); assert(!("errorSemantics" in (producer ?? {})));
  assert("errorSemantics" in (consumer ?? {})); assert(!("consumerAssumptions" in (consumer ?? {})));
  assert.deepEqual(memory.projectForOwner("unrelated-agent"), []);
});

test("a precise challenge blocks acceptance until a current-version revision resolves it", async () => {
  const { memory } = await proposed(); const id = definition().contractId;
  await memory.record(event("challenge", { type: "contract.challenged", contractId: id, baseVersion: 1, challenge: {
    challengeId: "missing-null-rule", authorId: "frontend", target: "error_semantics", detail: "null user_id behavior is undefined", evidenceRefs: ["web/user-client.ts:42"],
  } }));
  assert.equal(memory.integrationDecision(id).decision, "block");
  await assert.rejects(acceptBoth(memory), /open challenges/);
  await memory.record(event("revise", { type: "contract.revised", contractId: id, baseVersion: 1, authorId: "backend", semantics: semantics("stable non-null registered-user identity"), boundaryVerification: definition().boundaryVerification, sourceEvidence: ["server/users.py:55"], resolvesChallengeIds: ["missing-null-rule"] }));
  assert.equal(memory.get(id)?.definition.version, 2);
  await assert.rejects(memory.record(event("stale-revise", { type: "contract.revised", contractId: id, baseVersion: 1, authorId: "backend", semantics: semantics(), boundaryVerification: definition().boundaryVerification, sourceEvidence: ["old-message"], resolvesChallengeIds: [] })), /stale contract version/);
  await acceptBoth(memory, 2); assert.equal(memory.get(id)?.agreementState, "accepted");
});

test("only a real-path check over current artifacts verifies the boundary", async () => {
  const { memory } = await proposed(); const id = definition().contractId;
  await acceptBoth(memory); await observeBoth(memory);
  const evidence = { type: "boundary.verified" as const, contractId: id, version: 1, command: "python tests/test_user_boundary.py", exitCode: 0, artifactVersions: { "server/users.py": "sha:backend:v1", "web/user-client.ts": "sha:frontend:v1" }, evidenceRefs: ["command:1"] };
  await assert.rejects(memory.record(event("fake-check", { ...evidence, realPath: false })), /disconnected/);
  await memory.record(event("real-check", { ...evidence, realPath: true }));
  assert.equal(memory.get(id)?.verificationState, "verified"); assert.equal(memory.integrationDecision(id).decision, "allow");
});

test("artifact and semantic changes make old verification stale", async () => {
  const { memory } = await proposed(); const id = definition().contractId;
  await acceptBoth(memory); await observeBoth(memory);
  await memory.record(event("verify", { type: "boundary.verified", contractId: id, version: 1, command: "python tests/test_user_boundary.py", exitCode: 0, realPath: true, artifactVersions: { "server/users.py": "sha:backend:v1", "web/user-client.ts": "sha:frontend:v1" }, evidenceRefs: ["command:1"] }));
  await memory.record(event("backend-edit", { type: "artifact.observed", contractId: id, ownerId: "backend", artifactId: "server/users.py", version: "sha:backend:v2" }));
  assert.equal(memory.get(id)?.verificationState, "stale"); assert.equal(memory.integrationDecision(id).decision, "block");
  await memory.record(event("semantic-revision", { type: "contract.revised", contractId: id, baseVersion: 1, authorId: "backend", semantics: semantics("new meaning"), boundaryVerification: definition().boundaryVerification, sourceEvidence: ["request:revision"], resolvesChallengeIds: [] }));
  assert.equal(memory.get(id)?.verificationState, "stale"); assert.deepEqual(memory.get(id)?.acceptedBy, []);
});

test("event replay is idempotent and preserves resolved state", async () => {
  const { memory, store } = await proposed(); await acceptBoth(memory); await memory.record(store.events[0] as CoDomainEvent);
  const replayed = await CoDomainMemory.open(RUN, store);
  assert.equal(replayed.list().length, 1); assert.equal(replayed.get(definition().contractId)?.agreementState, "accepted");
});
