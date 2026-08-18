import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  compileRequiredTopology,
  DependencyMemory,
  InMemoryDependencyEventStore,
  JsonlDependencyEventStore,
  type DependencyEvent,
  type RequiredTopology,
} from "../src/dependency/index.js";

const NOW = "2026-08-17T00:00:00.000Z";

type EventPayload = DependencyEvent extends infer E
  ? E extends DependencyEvent
    ? Omit<E, "eventId" | "runId" | "observedAt">
    : never
  : never;

function event<T extends EventPayload>(
  runId: string,
  eventId: string,
  value: T,
): DependencyEvent {
  return { ...value, runId, eventId, observedAt: NOW } as unknown as DependencyEvent;
}

async function memoryFromTopology(task: RequiredTopology, runId: string) {
  const store = new InMemoryDependencyEventStore();
  const memory = await DependencyMemory.open(runId, store);
  for (const item of compileRequiredTopology(task, runId, NOW)) await memory.record(item);
  return { memory, store };
}

const sequentialTopology: RequiredTopology = {
  id: "sequential-build",
  topology_policy: "required",
  stages: [
    { id: "agent1", responsibility: "create initial artifact", depends_on: [], required_outputs: ["solution.py"], verification: { id: "run-solution", command: "python3 solution.py", covers: ["solution.py"] } },
    { id: "agent2", responsibility: "revise functionality", depends_on: ["agent1"], required_outputs: ["solution.py"], verification: { id: "run-solution", command: "python3 solution.py", covers: ["solution.py"] } },
    { id: "agent3", responsibility: "verify final artifact", depends_on: ["agent2"], required_outputs: ["solution.py"], verification: { id: "run-solution", command: "python3 solution.py", covers: ["solution.py"] } },
  ],
};

const parallelJoinTopology: RequiredTopology = {
  id: "parallel-join",
  topology_policy: "required",
  stages: [
    { id: "feature-a", responsibility: "implement feature A", depends_on: [], required_outputs: ["shared.py"], verification: { id: "feature-a-tests", command: "python3 -m pytest -q test_shared.py", covers: ["shared.py"] } },
    { id: "feature-b", responsibility: "implement feature B", depends_on: [], required_outputs: ["shared.py"], verification: { id: "feature-b-tests", command: "python3 -m pytest -q test_shared.py", covers: ["shared.py"] } },
    { id: "integrator", responsibility: "integrate both features", depends_on: ["feature-a", "feature-b"], required_outputs: ["shared.py"], verification: { id: "combined-tests", command: "python3 -m pytest -q test_shared.py", covers: ["shared.py"] } },
  ],
};

async function satisfy(
  memory: DependencyMemory,
  runId: string,
  stage: string,
  artifactId: string,
  verificationId: string,
  command: string,
  version: string,
) {
  const obligationId = `${runId}:${stage}`;
  await memory.record(event(runId, `${stage}:start:${version}`, {
    type: "owner.started",
    obligationId,
    ownerId: stage,
  }));
  await memory.record(event(runId, `${stage}:artifact:${version}`, {
    type: "artifact.observed",
    obligationId,
    artifactId,
    exists: true,
    version,
  }));
  await memory.record(event(runId, `${stage}:verify:${version}`, {
    type: "verification.observed",
    obligationId,
    verificationId,
    command,
    success: true,
    artifactVersions: { [artifactId]: version },
  }));
  await memory.record(event(runId, `${stage}:end:${version}`, {
    type: "owner.ended",
    obligationId,
    ownerId: stage,
    outcome: "ok",
  }));
  await memory.record(event(runId, `${stage}:complete:${version}`, {
    type: "obligation.completed",
    obligationId,
  }));
}

test("a required chain releases exactly one stage at a time", async () => {
  const task = sequentialTopology;
  const runId = "mab-chain";
  const { memory } = await memoryFromTopology(task, runId);
  assert.deepEqual(memory.readySet(), [`${runId}:agent1`]);
  assert.equal(memory.spawnDecision(`${runId}:agent2`).decision, "wait");

  await satisfy(memory, runId, "agent1", "solution.py", "run-solution", "python3 solution.py", "sha:a1");
  assert.deepEqual(memory.readySet(), [`${runId}:agent2`]);

  await satisfy(memory, runId, "agent2", "solution.py", "run-solution", "python3 solution.py", "sha:a2");
  assert.deepEqual(memory.readySet(), [`${runId}:agent3`]);
});

test("parallel feature owners are ready while their integrator waits for both", async () => {
  const task = parallelJoinTopology;
  const runId = "cooper-join";
  const { memory } = await memoryFromTopology(task, runId);
  assert.deepEqual(memory.readySet(), [
    `${runId}:feature-a`,
    `${runId}:feature-b`,
  ]);
  assert.equal(memory.spawnDecision(`${runId}:integrator`).decision, "wait");

  const artifact = "shared.py";
  const command = "python3 -m pytest -q test_shared.py";
  await satisfy(memory, runId, "feature-a", artifact, "feature-a-tests", command, "sha:f1");
  assert.equal(memory.spawnDecision(`${runId}:integrator`).decision, "wait");
  await satisfy(memory, runId, "feature-b", artifact, "feature-b-tests", command, "sha:f2");
  assert.deepEqual(memory.readySet(), [`${runId}:integrator`]);
});

test("a post-verification edit invalidates completion and blocks its consumer", async () => {
  const task = sequentialTopology;
  const runId = "stale-chain";
  const { memory } = await memoryFromTopology(task, runId);
  await satisfy(memory, runId, "agent1", "solution.py", "run-solution", "python3 solution.py", "sha:v1");
  assert.equal(memory.spawnDecision(`${runId}:agent2`).decision, "allow");

  await memory.record(event(runId, "agent1:edited:v2", {
    type: "artifact.observed",
    obligationId: `${runId}:agent1`,
    artifactId: "solution.py",
    exists: true,
    version: "sha:v2",
  }));
  assert.equal(memory.get(`${runId}:agent1`)?.status, "stale");
  assert.equal(memory.spawnDecision(`${runId}:agent2`).decision, "wait");
});

test("an owner ending without evidence becomes orphaned and can receive recovery", async () => {
  const task = sequentialTopology;
  const runId = "recovery-chain";
  const { memory } = await memoryFromTopology(task, runId);
  await memory.record(event(runId, "agent1:start", {
    type: "owner.started",
    obligationId: `${runId}:agent1`,
    ownerId: "agent1",
  }));
  await memory.record(event(runId, "agent1:end", {
    type: "owner.ended",
    obligationId: `${runId}:agent1`,
    ownerId: "agent1",
    outcome: "ok",
  }));
  assert.equal(memory.get(`${runId}:agent1`)?.status, "orphaned");
  assert.equal(memory.spawnDecision(`${runId}:agent2`).decision, "wait");

  await memory.record(event(runId, "agent1:recovery", {
    type: "recovery.assigned",
    obligationId: `${runId}:agent1`,
    ownerId: "agent1-retry",
    strategy: "write a bounded checkpoint before expanding the implementation",
    evidenceRef: "event:agent1:end",
  }));
  assert.equal(memory.spawnDecision(`${runId}:agent1`).decision, "allow");
  assert.equal(memory.projectForOwner("agent1-retry")[0]?.recovery?.retryCount, 1);
});

test("event replay is idempotent and isolated by run", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-memory-"));
  const store = new JsonlDependencyEventStore(join(directory, "events.jsonl"));
  const task = sequentialTopology;
  const runId = "persistent-chain";
  const memory = await DependencyMemory.open(runId, store);
  const events = compileRequiredTopology(task, runId, NOW);
  for (const item of events) await memory.record(item);
  await memory.record(events[0] as DependencyEvent);

  const replayed = await DependencyMemory.open(runId, store);
  assert.equal(replayed.list().length, 3);
  assert.equal(replayed.listEdges().length, 2);
  assert.deepEqual(replayed.readySet(), [`${runId}:agent1`]);
  assert.equal((await store.load("another-run")).length, 0);
});

test("a cyclic edge is rejected before it reaches persistent storage", async () => {
  const task = sequentialTopology;
  const runId = "cycle-check";
  const { memory, store } = await memoryFromTopology(task, runId);
  const persistedBefore = store.events.length;
  await assert.rejects(memory.record(event(runId, "cycle-edge", {
    type: "dependency.declared",
    edge: {
      edgeId: `${runId}:agent3->agent1`,
      runId,
      upstreamId: `${runId}:agent3`,
      downstreamId: `${runId}:agent1`,
      requirement: "requires_complete",
      evidenceRef: "test:cycle",
    },
  })), /cycle/);
  assert.equal(store.events.length, persistedBefore);
  assert.equal(memory.listEdges().length, 2);
});

test("requires_verified cannot be vacuously satisfied without a declared check", async () => {
  const runId = "non-vacuous-verification";
  const store = new InMemoryDependencyEventStore();
  const memory = await DependencyMemory.open(runId, store);
  for (const owner of ["producer", "consumer"]) {
    await memory.record(event(runId, `declare:${owner}`, {
      type: "obligation.declared",
      obligation: {
        obligationId: owner,
        runId,
        ownerId: owner,
        title: owner,
        source: { type: "explicit_declaration", evidenceRef: "test" },
        requiredOutputs: [{ artifactId: `${owner}.txt` }],
        requiredVerifications: [],
      },
    }));
  }
  await assert.rejects(memory.record(event(runId, "bad-verified-edge", {
    type: "dependency.declared",
    edge: {
      edgeId: "producer->consumer",
      runId,
      upstreamId: "producer",
      downstreamId: "consumer",
      requirement: "requires_verified",
      evidenceRef: "test",
    },
  })), /no declared verification/);
  assert.equal(store.events.length, 2);
});

test("undeclared artifacts cannot enter dependency memory", async () => {
  const runId = "declared-artifacts-only";
  const memory = await DependencyMemory.open(runId, new InMemoryDependencyEventStore());
  await memory.record(event(runId, "declare", { type: "obligation.declared", obligation: { obligationId: "work", runId, ownerId: "agent", title: "work", source: { type: "explicit_declaration", evidenceRef: "test" }, requiredOutputs: [{ artifactId: "out.txt" }], requiredVerifications: [] } }));
  await assert.rejects(memory.record(event(runId, "bad-artifact", { type: "artifact.observed", obligationId: "work", artifactId: "other.txt", exists: true, version: "sha" })), /not a declared output/);
});
