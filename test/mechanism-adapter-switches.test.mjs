import assert from "node:assert/strict"
import { execFile } from "node:child_process"
import { mkdtemp, mkdir, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { promisify } from "node:util"
import dependencyPlugin from "../adapters/opencode/dependency-memory-v2.mjs"
import codomainPlugin from "../adapters/opencode/codomain-memory.mjs"
import testingPlugin from "../adapters/opencode/testing-practice-memory.mjs"

const execFileAsync = promisify(execFile)

test("each adapter independently blocks operational access when switched off", async () => {
  const directory = await mkdtemp(join(tmpdir(), "mechanism-switches-"))
  const stateDir = join(directory, ".multi-agent-memory")
  await mkdir(stateDir)
  await writeFile(join(stateDir, "codomain-run.json"), JSON.stringify({ runId: "stale" }))
  await writeFile(join(stateDir, "testing-run.json"), JSON.stringify({ runId: "stale" }))

  const shell = () => ({ cwd() { return this }, async text() { return "ok" } })
  const dependency = await dependencyPlugin({ directory, $: shell }, { mechanisms: "codomain" })
  const codomain = await codomainPlugin({ directory }, { mechanisms: "dependency" })
  const testing = await testingPlugin({ directory }, { mechanisms: "dependency" })

  assert.deepEqual(JSON.parse(await dependency.tool.memory_inspect.execute({})), { mechanism: "dependency", enabled: false })
  await assert.rejects(() => codomain.tool.codomain_inspect.execute({}), /codomain mechanism is disabled/)
  await assert.rejects(() => testing.tool.practice_search.execute({}), /testing mechanism is disabled/)

  assert.equal(JSON.parse(await dependency.tool.memory_capabilities.execute({})).switches.codomain, true)
  assert.equal(JSON.parse(await codomain.tool.memory_capabilities.execute({})).switches.dependency, true)
  assert.equal(JSON.parse(await testing.tool.memory_capabilities.execute({})).switches.dependency, true)
})

test("co-domain compatibility evidence is bound to Git HEAD, not post-change text", async () => {
  const directory = await mkdtemp(join(tmpdir(), "codomain-baseline-"))
  await writeFile(join(directory, "interface.py"), "class AudioBlock:\n    format: str | None = None\n")
  await execFileAsync("git", ["init"], { cwd: directory })
  await execFileAsync("git", ["add", "interface.py"], { cwd: directory })
  await execFileAsync("git", ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "baseline"], { cwd: directory })
  await writeFile(join(directory, "interface.py"), "class AudioBlock:\n    format: str | None = None\n    mimetype: str | None = None\n")
  const hooks = await codomainPlugin({ directory }, { mechanisms: "codomain" })
  await hooks.tool.codomain_initialize.execute({})
  const contract = {
    contractId: "audio", interfaceId: "audio", sourceEvidence: ["interface.py"],
    producer: { ownerId: "producer", artifacts: ["interface.py"] },
    consumer: { ownerId: "consumer", artifacts: ["interface.py"] },
    semantics: { fields: ["audio"], producerObligations: ["produce"], consumerObligations: ["consume"], invariants: ["compatible"], errorSemantics: ["error"] },
    boundaryVerification: { command: "echo COMPAT mimetype", expectedExitCode: 0, requiredAssertions: ["COMPAT"], interactionCases: [{ id: "compat", category: "compatibility", marker: "COMPAT", binding: { evidenceId: "audio", path: "interface.py", symbol: "mimetype", commandFragment: "mimetype" } }], interfaceEvidence: [{ id: "audio", path: "interface.py", contains: "mimetype:" }] }, risk: "high",
  }
  await assert.rejects(() => hooks.tool.codomain_propose.execute({ author_id: "producer", contract_json: JSON.stringify(contract) }), /interface evidence not found in Git HEAD/)
})

test("co-domain blocks implementation spawn until both participants accept current version", async () => {
  const directory = await mkdtemp(join(tmpdir(), "codomain-implementation-gate-"))
  const hooks = await codomainPlugin({ directory }, { mechanisms: "codomain" }); await hooks.tool.codomain_initialize.execute({})
  const contract = { contractId: "new-api", interfaceId: "api", sourceEvidence: ["request"], producer: { ownerId: "agent1", artifacts: ["solution.py"] }, consumer: { ownerId: "agent2", artifacts: ["solution.py"] }, semantics: { fields: [{ name: "result", type: "string", meaning: "observable result" }], producerObligations: ["produce"], consumerObligations: ["consume"], invariants: ["stable"], errorSemantics: ["nonzero"] }, boundaryVerification: { command: "python3 solution.py", expectedExitCode: 0, requiredAssertions: ["PASS"], interactionCases: [{ id: "normal", category: "normal", marker: "PASS" }] }, risk: "high" }
  await hooks.tool.codomain_propose.execute({ author_id: "agent1", contract_json: JSON.stringify(contract) })
  await hooks.tool.codomain_accept.execute({ contract_id: "new-api", version: 1, author_id: "agent2", evidence_refs: ["review"] })
  await assert.rejects(() => hooks["tool.execute.before"]({ tool: "task" }, { args: { prompt: "Implement solution.py now." } }), /both participants accept/)
  await hooks.tool.codomain_accept.execute({ contract_id: "new-api", version: 1, author_id: "agent1", evidence_refs: ["producer"] })
  await hooks["tool.execute.before"]({ tool: "task" }, { args: { prompt: "Implement solution.py now." } })
})
