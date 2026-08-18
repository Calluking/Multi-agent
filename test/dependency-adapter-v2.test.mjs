import assert from "node:assert/strict"
import { execFile } from "node:child_process"
import { mkdtemp, readFile, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { promisify } from "node:util"
import plugin from "../adapters/opencode/dependency-memory-v2.mjs"

const execFileAsync = promisify(execFile)

test("native task completion automatically reconciles a declared obligation", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-adapter-v2-"))
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "dependency" })
  await hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([
      { id: "producer", owner: "agent1", title: "produce", outputs: ["artifact.txt"], verifications: [] },
      { id: "consumer", owner: "agent2", title: "consume", outputs: ["result.txt"], verifications: [] },
    ]),
    edges_json: JSON.stringify([{ upstream: "producer", downstream: "consumer", requirement: "requires_complete" }]),
  })
  const args = { prompt: "Your obligation ID is: producer", description: "producer" }
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "c1" }, { args })
  await writeFile(join(directory, "artifact.txt"), "current output")
  const output = { title: "task", output: "agent finished", metadata: {} }
  await hooks["tool.execute.after"]({ tool: "task", sessionID: "s", callID: "c1", args }, output)
  assert.equal(output.metadata.dependencyMemoryV2.completed, true)
  const inspected = JSON.parse(await hooks.tool.memory_inspect.execute({}))
  assert.equal(inspected.obligations.find((item) => item.obligationId === "producer").status, "complete")
  assert.deepEqual(inspected.ready, ["consumer"])
  const events = (await readFile(join(directory, ".multi-agent-memory", "events.jsonl"), "utf8")).trim().split("\n").map(JSON.parse)
  assert.equal(events.filter((event) => event.type === "owner.started" && event.obligationId === "producer").length, 1)
  assert.equal(events.filter((event) => event.type === "obligation.completed" && event.obligationId === "producer").length, 1)
})

test("initialization uses existing python3 and rejects environment or system mutation", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-adapter-v2-safety-"))
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "dependency" })
  const unsafe = (command) => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ id: "verify", owner: "agent1", title: "verify", outputs: ["result.py"], verifications: [{ id: "tests", command, covers: ["result.py"], requiredAssertions: ["PASS"], interactionCases: [{ id: "normal", category: "normal", marker: "PASS" }] }] }]),
    edges_json: "[]",
  })
  await assert.rejects(() => unsafe("python3 -m venv .venv"), /may not install runtimes/)
  await assert.rejects(() => unsafe("touch /usr/bin/python"), /may not install runtimes/)

  await hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ id: "verify", owner: "agent1", title: "verify", outputs: ["result.py"], verifications: [{ id: "tests", command: "python -m pytest -q", covers: ["result.py"], requiredAssertions: ["passed"], interactionCases: [{ id: "normal", category: "normal", marker: "passed" }] }] }]),
    edges_json: "[]",
  })
  const inspected = JSON.parse(await hooks.tool.memory_inspect.execute({}))
  assert.equal(inspected.obligations[0].requiredVerifications[0].command, "python3 -m pytest -q")
})

test("verification applies the same python normalization as initialization", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-normalized-verify-"))
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  const command = "python -c \"print('PASS')\""
  await hooks.tool.memory_initialize.execute({ obligations_json: JSON.stringify([{ id: "work", owner: "agent", title: "work", outputs: ["result.py"], verifications: [{ id: "check", command, covers: ["result.py"], requiredAssertions: ["PASS"], interactionCases: [{ id: "normal", category: "normal", marker: "PASS" }] }] }]), edges_json: "[]" })
  await hooks.tool.memory_start.execute({ obligation_id: "work", owner_id: "agent" }); await writeFile(join(directory, "result.py"), "value = 1\n")
  await hooks.tool.memory_observe_artifact.execute({ obligation_id: "work", path: "result.py" })
  const result = JSON.parse(await hooks.tool.memory_verify.execute({ obligation_id: "work", verification_id: "check", command, covers: ["result.py"] }))
  assert.equal(result.success, true)
})

test("existing interfaces require compatibility cases grounded in exact source", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-adapter-v2-grounding-"))
  await writeFile(join(directory, "existing.py"), "class AudioBlock:\n    format: str | None = None\n")
  await execFileAsync("git", ["init"], { cwd: directory })
  await execFileAsync("git", ["add", "existing.py"], { cwd: directory })
  await execFileAsync("git", ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "baseline"], { cwd: directory })
  await writeFile(join(directory, "existing.py"), "class AudioBlock:\n    format: str | None = None\n    mimetype: str | None = None\n")
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "dependency" })
  const base = { id: "verify", owner: "agent1", title: "verify", outputs: ["existing.py"] }
  await assert.rejects(() => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ ...base, verifications: [{ id: "tests", command: "true", covers: ["existing.py"], requiredAssertions: ["NORMAL"], interactionCases: [{ id: "normal", category: "normal", marker: "NORMAL" }] }] }]), edges_json: "[]",
  }), /compatibility interaction case/)
  await assert.rejects(() => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ ...base, verifications: [{ id: "tests", command: "true", covers: ["existing.py"], requiredAssertions: ["COMPAT"], interactionCases: [{ id: "compat", category: "compatibility", marker: "COMPAT", binding: { evidenceId: "audio", path: "existing.py", symbol: "mimetype", commandFragment: "mimetype" } }], interfaceEvidence: [{ id: "audio", path: "existing.py", contains: "mimetype:" }] }] }]), edges_json: "[]",
  }), /interface evidence not found/)

  await assert.rejects(() => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ ...base, verifications: [{ id: "tests", command: "echo COMPAT mimetype", covers: ["existing.py"], requiredAssertions: ["COMPAT"], interactionCases: [{ id: "compat", category: "compatibility", marker: "COMPAT", binding: { evidenceId: "audio", path: "existing.py", symbol: "format", commandFragment: "format" } }], interfaceEvidence: [{ id: "audio", path: "existing.py", contains: "format: str | None = None" }] }] }]), edges_json: "[]",
  }), /command must exercise/)
})

test("enabled dependency blocks native tasks before successful initialization", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-fail-closed-before-init-"))
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "dependency" })
  const inspected = JSON.parse(await hooks.tool.memory_inspect.execute({}))
  assert.equal(inspected.initialized, false)
  await assert.rejects(
    () => hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "c" }, { args: { prompt: "work" } }),
    /enabled but not initialized/,
  )
})

test("failed initialization remains blocked and a valid retry commits a fresh graph", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-fail-closed-retry-"))
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "dependency" })
  await assert.rejects(() => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ id: "producer", owner: "agent1", title: "produce", outputs: ["artifact.txt"], verifications: [] }]),
    edges_json: JSON.stringify([{ upstream: "missing", downstream: "producer", requirement: "requires_complete" }]),
  }), /unknown obligation/)
  await assert.rejects(
    () => hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "blocked" }, { args: { prompt: "work" } }),
    /enabled but not initialized/,
  )

  const initialized = JSON.parse(await hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([
      { id: "producer", owner: "agent1", title: "produce", outputs: ["artifact.txt"], verifications: [] },
      { id: "consumer", owner: "agent2", title: "consume", outputs: ["result.txt"], verifications: [] },
    ]),
    edges_json: JSON.stringify([{ upstream: "producer", downstream: "consumer", requirement: "requires_complete" }]),
  }))
  assert.equal(initialized.initialized, true)
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "producer" }, { args: { prompt: "Your obligation ID is: producer" } })
  await assert.rejects(
    () => hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "consumer" }, { args: { prompt: "Your obligation ID is: consumer" } }),
    /dependency spawn blocked/,
  )
})

test("initialization errors explain the complete interaction grounding schema", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-schema-help-"))
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  await assert.rejects(() => hooks.tool.memory_initialize.execute({
    obligations_json: JSON.stringify([{ id: "work", owner: "agent", title: "work", outputs: ["out.txt"], verifications: [{ id: "check", command: "echo PASS", covers: ["out.txt"], requiredAssertions: ["PASS"] }] }]),
    edges_json: "[]",
  }), (error) => /interactionCases/.test(error.message) && /interfaceEvidence/.test(error.message) && /commandFragment/.test(error.message))
})

test("disabled dependency leaves native task execution inert", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-disabled-inert-"))
  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const hooks = await plugin({ directory, $: shell }, { mechanisms: "" })
  const result = JSON.parse(await hooks.tool.memory_initialize.execute({ obligations_json: "[]", edges_json: "[]" }))
  assert.equal(result.activated, false)
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "c" }, { args: { prompt: "work" } })
  await assert.rejects(() => readFile(join(directory, ".multi-agent-memory", "run.json"), "utf8"), /ENOENT/)
})

test("initialized dependency rejects ambiguous writable task but permits explicit read-only auxiliary task", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-classification-")); await writeFile(join(directory, "artifact.txt"), "base")
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  await hooks.tool.memory_initialize.execute({ obligations_json: JSON.stringify([{ id: "work-a", owner: "agent-a", title: "a", outputs: ["a.txt"], verifications: [] }, { id: "work-b", owner: "agent-b", title: "b", outputs: ["b.txt"], verifications: [] }]), edges_json: "[]" })
  await assert.rejects(() => hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "u" }, { args: { prompt: "write code" } }), /ambiguous/)
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "a" }, { args: { prompt: "TASK_MODE: auxiliary read-only; inspect code" } })
})

test("native task classification accepts natural backticked obligation ID phrasing", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-natural-id-"))
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  await hooks.tool.memory_initialize.execute({ obligations_json: JSON.stringify([{ id: "feature1-sub", owner: "root", title: "feature", outputs: ["out.txt"], verifications: [] }]), edges_json: "[]" })
  await hooks.tool.memory_start.execute({ obligation_id: "feature1-sub", owner_id: "root" })
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "natural" }, { args: { prompt: "Your obligation ID is `feature1-sub`; implement it." } })
})

test("a single active dependency obligation deterministically classifies its native spawn", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-active-fallback-"))
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  await hooks.tool.memory_initialize.execute({ obligations_json: JSON.stringify([{ id: "only-work", owner: "root", title: "feature", outputs: ["out.txt"], verifications: [] }]), edges_json: "[]" })
  await hooks.tool.memory_start.execute({ obligation_id: "only-work", owner_id: "root" })
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "fallback" }, { args: { prompt: "Implement the feature now." } })
})

test("a single active obligation takes precedence over other ready graph nodes", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dependency-active-priority-"))
  const hooks = await plugin({ directory }, { mechanisms: "dependency" })
  await hooks.tool.memory_initialize.execute({ obligations_json: JSON.stringify([{ id: "active", owner: "root", title: "active", outputs: ["a.txt"], verifications: [] }, { id: "also-ready", owner: "other", title: "ready", outputs: ["b.txt"], verifications: [] }]), edges_json: "[]" })
  await hooks.tool.memory_start.execute({ obligation_id: "active", owner_id: "root" })
  await hooks["tool.execute.before"]({ tool: "task", sessionID: "s", callID: "priority" }, { args: { prompt: "Perform the currently active feature." } })
})
