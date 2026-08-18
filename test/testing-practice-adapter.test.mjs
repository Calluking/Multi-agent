import assert from "node:assert/strict"
import { mkdtemp, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import plugin from "../adapters/opencode/testing-practice-memory.mjs"

test("testing adapter executes exact command and binds current artifact evidence", async () => {
  const directory = await mkdtemp(join(tmpdir(), "testing-practice-adapter-"))
  await writeFile(join(directory, "artifact.txt"), "current")
  const hooks = await plugin({ directory }, { mechanisms: "testing" })
  await hooks.tool.testing_initialize.execute({})
  await hooks.tool.verification_declare.execute({
    verification_id: "acceptance", source_type: "starting_request", source_ref: "prompt:test",
    authoritative: true, owner_id: "verifier", artifacts: ["artifact.txt"], practice_refs: [],
    command: "test -s artifact.txt && echo ARTIFACT_NONEMPTY", required_assertions: ["ARTIFACT_NONEMPTY"], boundary: false, max_retries: 1,
  })
  const result = JSON.parse(await hooks.tool.verification_run.execute({ verification_id: "acceptance", command: "test -s artifact.txt && echo ARTIFACT_NONEMPTY", assertions_observed: ["ARTIFACT_NONEMPTY"], real_path: true }))
  assert.equal(result.exitCode, 0)
  assert.equal(result.state, "passed")
  assert.equal(result.completion.decision, "allow")
})

test("zero exit without required output marker is failed evidence", async () => {
  const directory = await mkdtemp(join(tmpdir(), "testing-practice-marker-"))
  await writeFile(join(directory, "artifact.txt"), "current")
  const hooks = await plugin({ directory }, { mechanisms: "testing" })
  await hooks.tool.testing_initialize.execute({})
  await hooks.tool.verification_declare.execute({ verification_id: "marker", source_type: "starting_request", source_ref: "prompt:test", authoritative: true, owner_id: "verifier", artifacts: ["artifact.txt"], practice_refs: [], command: "true", required_assertions: ["EXPECTED_MARKER"], boundary: false, max_retries: 1 })
  const result = JSON.parse(await hooks.tool.verification_run.execute({ verification_id: "marker", command: "true", assertions_observed: ["EXPECTED_MARKER"], real_path: true }))
  assert.equal(result.exitCode, 1)
  assert.deepEqual(result.missingAssertions, ["EXPECTED_MARKER"])
  assert.equal(result.state, "failed")
})

test("empty owner standard cannot be acknowledged before managed spawn", async () => {
  const directory = await mkdtemp(join(tmpdir(), "testing-empty-owner-"))
  const hooks = await plugin({ directory }, { mechanisms: "testing" })
  await hooks.tool.testing_initialize.execute({})
  await assert.rejects(() => hooks.tool.verification_extract_standard.execute({ owner_id: "agent1" }), /no testing standard is assigned/)
})

test("an extracted owner mentioned unambiguously in a task prompt is classified", async () => {
  const directory = await mkdtemp(join(tmpdir(), "testing-owner-fallback-")); await writeFile(join(directory, "artifact.txt"), "x")
  const hooks = await plugin({ directory }, { mechanisms: "testing" })
  await hooks.tool.testing_initialize.execute({})
  await hooks.tool.verification_declare.execute({ verification_id: "agent1-std", source_type: "assignment_promise", source_ref: "assignment", authoritative: true, owner_id: "agent1", artifacts: ["artifact.txt"], practice_refs: [], command: "echo PASS", required_assertions: ["PASS"], boundary: false, max_retries: 1 })
  await hooks.tool.verification_extract_standard.execute({ owner_id: "agent1" })
  await hooks["tool.execute.before"]({ tool: "task" }, { args: { prompt: "You are agent1; perform your assigned work." } })
})
