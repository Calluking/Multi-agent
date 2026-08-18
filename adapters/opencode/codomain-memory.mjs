import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, join, resolve } from "node:path"
import { promisify } from "node:util"
import { tool } from "@opencode-ai/plugin"
import { CoDomainMemory, JsonlCoDomainEventStore } from "../../dist/src/codomain/index.js"
import { parseMechanismSwitches } from "../../dist/src/config.js"

const execFileAsync = promisify(execFile)
const now = () => new Date().toISOString()
const id = () => crypto.randomUUID()
const TIMEOUT_MS = 120_000
const CONTRACT_SCHEMA_HELP = "interactionCases must be nonempty {id,category,marker} entries; category is normal|error|precedence|compatibility and marker must exactly occur in requiredAssertions. Use compatibility+binding+interfaceEvidence only for artifacts that already exist in Git HEAD. New artifacts must not cite baseline interfaceEvidence. Proposal author_id must equal producer.ownerId, producer and consumer ownerIds must differ, and semantics.fields entries require {name,type,meaning}. The boundary command must itself emit every required marker; for separate new artifacts it must execute the consumer artifact, which imports/references the producer artifact."

function safeCommand(command) {
  if (typeof command !== "string" || !command.trim()) throw new Error("boundary verification command is required")
  if (/(?:^|\s)(?:sudo|apt(?:-get)?|dnf|yum|apk|pacman|virtualenv)\s/i.test(command) ||
      /python\d*(?:\.\d+)?\s+-m\s+venv\b/i.test(command) ||
      /(?:\/usr|\/bin|\/sbin|\/opt|\/etc)\//.test(command)) {
    throw new Error("boundary verification may not install runtimes, create environments, or modify system paths")
  }
  return command.replace(/(^|[;&|]\s*)python(?=\s)/g, "$1python3")
}

async function baselineSource(directory, path) {
  try {
    const { stdout } = await execFileAsync("git", ["-C", directory, "show", `HEAD:${path}`], { maxBuffer: 4 * 1024 * 1024 })
    return stdout
  } catch {
    return null
  }
}

async function validateBoundaryVerification(requirement, directory, baselinePaths = []) {
  requirement.command = safeCommand(requirement.command)
  const assertions = requirement.requiredAssertions ?? requirement.required_assertions ?? []
  if (!Array.isArray(assertions) || assertions.length === 0 || assertions.some((item) => typeof item !== "string" || !item.trim())) throw new Error("boundary verification requires nonempty observable output markers")
  requirement.requiredAssertions = assertions
  const cases = requirement.interactionCases ?? []
  if (!Array.isArray(cases) || cases.length === 0) throw new Error(`boundary verification requires structured interactionCases. ${CONTRACT_SCHEMA_HELP}`)
  for (const item of cases) {
    if (!item?.id || !["normal", "error", "precedence", "compatibility"].includes(item.category) || !item.marker) throw new Error(`each interaction case requires id, category, and marker. ${CONTRACT_SCHEMA_HELP}`)
    if (!assertions.includes(item.marker)) throw new Error(`interaction marker must be required: ${item.marker}. ${CONTRACT_SCHEMA_HELP}`)
  }
  const evidence = requirement.interfaceEvidence ?? []
  if (baselinePaths.length && !cases.some((item) => item.category === "compatibility")) throw new Error("an existing baseline interface requires a compatibility interaction case")
  if (baselinePaths.length && (!Array.isArray(evidence) || evidence.length === 0)) throw new Error("an existing baseline interface requires exact interfaceEvidence")
  for (const item of evidence) {
    if (!item?.id || !item?.path || !item?.contains) throw new Error("interfaceEvidence requires id, path, and exact contains text")
    if (!baselinePaths.includes(item.path)) throw new Error(`interface evidence is not a declared baseline artifact: ${item.path}`)
    const source = await baselineSource(directory, item.path)
    if (source === null || !source.includes(item.contains)) throw new Error(`interface evidence not found in Git HEAD for ${item.path}`)
  }
  const evidenceById = new Map(evidence.map((item) => [item.id, item]))
  for (const item of cases.filter((candidate) => candidate.category === "compatibility")) {
    const binding = item.binding
    if (!binding?.evidenceId || !binding?.path || !binding?.symbol || !binding?.commandFragment) throw new Error(`compatibility case ${item.id} requires binding with evidenceId, path, symbol, and commandFragment`)
    const cited = evidenceById.get(binding.evidenceId)
    if (!cited || cited.path !== binding.path) throw new Error(`compatibility case ${item.id} references unknown or mismatched baseline evidence`)
    const source = await baselineSource(directory, binding.path)
    const escaped = binding.symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    const symbol = new RegExp(`(?:^|[^A-Za-z0-9_])${escaped}(?:$|[^A-Za-z0-9_])`)
    if (source === null || !symbol.test(source) || !symbol.test(cited.contains)) throw new Error(`compatibility case ${item.id} baseline symbol is not in cited Git HEAD evidence`)
    if (!binding.commandFragment.includes(binding.symbol) || !requirement.command.includes(binding.commandFragment)) throw new Error(`compatibility case ${item.id} command must exercise its exact baseline-bound fragment`)
    if (!baselinePaths.includes(binding.path)) throw new Error(`compatibility case ${item.id} must bind a declared baseline artifact`)
  }
  return requirement
}

export default async function codomainMemoryPlugin({ directory }, options = {}) {
  const mechanisms = parseMechanismSwitches(typeof options.mechanisms === "string" ? options.mechanisms : process.env.MAM_MECHANISMS)
  const statePath = join(directory, ".multi-agent-memory", "codomain-run.json")
  const eventPath = join(directory, ".multi-agent-memory", "codomain-events.jsonl")

  async function state() {
    if (!mechanisms.codomain) throw new Error("codomain mechanism is disabled")
    return JSON.parse(await readFile(statePath, "utf8"))
  }
  async function memory() { const current = await state(); return CoDomainMemory.open(current.runId, new JsonlCoDomainEventStore(eventPath)) }
  async function record(mem, runId, value) { await mem.record({ ...value, eventId: id(), runId, observedAt: now() }) }
  function workspacePath(path) {
    const root = resolve(directory); const absolute = resolve(directory, path)
    if (absolute !== root && !absolute.startsWith(`${root}/`)) throw new Error("artifact escapes workspace")
    return absolute
  }
  function isImplementationTask(args) {
    const text = `${args?.prompt ?? ""}\n${args?.description ?? ""}`
    if (/\bdo\s+not\s+(?:write|implement|modify|create)\b/i.test(text)) return false
    return /\b(?:write|implement|modify|create|fix|optimi[sz]e)\b/i.test(text)
  }

  return { tool: {
    memory_capabilities: tool({ description: "Report enabled universal memory mechanisms.", args: {}, async execute() {
      return JSON.stringify({ switches: mechanisms, implementation: { dependency: "not_in_this_adapter", codomain: "available", testing: "not_implemented" } })
    }}),
    codomain_initialize: tool({ description: "Initialize Co-Domain Memory once for this run.", args: {}, async execute() {
      if (!mechanisms.codomain) return JSON.stringify({ activated: false, mechanism: "codomain", reason: "disabled" })
      try { const current = await state(); return JSON.stringify({ activated: false, reason: "already initialized", runId: current.runId }) }
      catch (error) { if (error?.code !== "ENOENT") throw error }
      const runId = id(); await mkdir(dirname(statePath), { recursive: true }); await writeFile(statePath, JSON.stringify({ runId, mechanisms }, null, 2))
      return JSON.stringify({ activated: true, runId })
    }}),
    codomain_propose: tool({ description: `Propose one evidence-grounded producer/consumer plan before implementation. This tool is self-describing; do not inspect plugin source. ${CONTRACT_SCHEMA_HELP}`, args: {
      author_id: tool.schema.string(), contract_json: tool.schema.string().describe("JSON {contractId,interfaceId,sourceEvidence,producer:{ownerId,artifacts},consumer:{ownerId,artifacts},semantics:{fields,producerObligations,consumerObligations,invariants,errorSemantics},boundaryVerification:{command,expectedExitCode,requiredAssertions:[markers],interactionCases:[{id,category,marker,binding:{evidenceId,path,symbol,commandFragment}}],interfaceEvidence:[{id,path,contains:exact_Git_HEAD_text}]},risk}. Compatibility cases require an exact baseline-bound command fragment.")
    }, async execute(args) {
      const current = await state(); const mem = await memory(); const contract = JSON.parse(args.contract_json)
      const sharedArtifact = contract.producer.artifacts.some((path) => contract.consumer.artifacts.includes(path))
      const baselinePaths = []
      for (const path of [...new Set([...contract.producer.artifacts, ...contract.consumer.artifacts])]) if (await baselineSource(directory, path) !== null) baselinePaths.push(path)
      contract.runId = current.runId; contract.version = 1; contract.boundaryVerification = await validateBoundaryVerification(contract.boundaryVerification, directory, baselinePaths)
      if (sharedArtifact) contract.risk = "high"
      await record(mem, current.runId, { type: "contract.proposed", contract, authorId: args.author_id })
      return JSON.stringify(mem.get(contract.contractId), null, 2)
    }}),
    codomain_challenge: tool({ description: "Challenge a precise current-version contract term as producer or consumer.", args: {
      contract_id: tool.schema.string(), base_version: tool.schema.number(), challenge_id: tool.schema.string(), author_id: tool.schema.string(), target: tool.schema.enum(["field","producer_obligation","consumer_obligation","invariant","error_semantics","verification"]), detail: tool.schema.string(), evidence_refs: tool.schema.array(tool.schema.string())
    }, async execute(args) { const current = await state(); const mem = await memory(); await record(mem, current.runId, { type: "contract.challenged", contractId: args.contract_id, baseVersion: args.base_version, challenge: { challengeId: args.challenge_id, authorId: args.author_id, target: args.target, detail: args.detail, evidenceRefs: args.evidence_refs } }); return JSON.stringify(mem.get(args.contract_id), null, 2) }}),
    codomain_revise: tool({ description: "Revise the current contract semantics and resolve cited open challenges.", args: {
      contract_id: tool.schema.string(), base_version: tool.schema.number(), author_id: tool.schema.string(), semantics_json: tool.schema.string(), verification_json: tool.schema.string(), source_evidence: tool.schema.array(tool.schema.string()), resolves_challenge_ids: tool.schema.array(tool.schema.string())
    }, async execute(args) { const current = await state(); const mem = await memory(); const item = mem.get(args.contract_id); if (!item) throw new Error("unknown contract"); const baselinePaths = []; for (const path of [...new Set([...item.definition.producer.artifacts, ...item.definition.consumer.artifacts])]) if (await baselineSource(directory, path) !== null) baselinePaths.push(path); const boundaryVerification = await validateBoundaryVerification(JSON.parse(args.verification_json), directory, baselinePaths); await record(mem, current.runId, { type: "contract.revised", contractId: args.contract_id, baseVersion: args.base_version, authorId: args.author_id, semantics: JSON.parse(args.semantics_json), boundaryVerification, sourceEvidence: args.source_evidence, resolvesChallengeIds: args.resolves_challenge_ids }); return JSON.stringify(mem.get(args.contract_id), null, 2) }}),
    codomain_accept: tool({ description: "Record participant-specific acceptance of the current version.", args: { contract_id: tool.schema.string(), version: tool.schema.number(), author_id: tool.schema.string(), evidence_refs: tool.schema.array(tool.schema.string()) }, async execute(args) { const current = await state(); const mem = await memory(); await record(mem, current.runId, { type: "contract.accepted", contractId: args.contract_id, version: args.version, authorId: args.author_id, evidenceRefs: args.evidence_refs }); return JSON.stringify(mem.get(args.contract_id), null, 2) }}),
    codomain_inspect: tool({ description: "Inspect full contracts or a sparse participant projection.", args: { owner_id: tool.schema.string().optional() }, async execute(args) { const mem = await memory(); return JSON.stringify(args.owner_id ? mem.projectForOwner(args.owner_id) : mem.list(), null, 2) }}),
    codomain_observe_artifact: tool({ description: "Hash a declared producer or consumer artifact from the real workspace.", args: { contract_id: tool.schema.string(), owner_id: tool.schema.string(), path: tool.schema.string() }, async execute(args) { const current = await state(); const mem = await memory(); const bytes = await readFile(workspacePath(args.path)); const version = createHash("sha256").update(bytes).digest("hex"); await record(mem, current.runId, { type: "artifact.observed", contractId: args.contract_id, ownerId: args.owner_id, artifactId: args.path, version }); return JSON.stringify({ path: args.path, version }) }}),
    codomain_verify: tool({ description: "Run the exact contract check over current artifacts from both owners. Crossing is derived from the declared command and compatibility bindings.", args: { contract_id: tool.schema.string(), version: tool.schema.number(), command: tool.schema.string(), evidence_refs: tool.schema.array(tool.schema.string()) }, async execute(args) {
      const current = await state(); const mem = await memory(); const item = mem.get(args.contract_id); if (!item) throw new Error("unknown contract")
      const command = safeCommand(args.command); if (command !== item.definition.boundaryVerification.command) throw new Error("verification was not declared exactly")
      const artifactVersions = {}; for (const path of [...new Set([...item.definition.producer.artifacts, ...item.definition.consumer.artifacts])]) { const bytes = await readFile(workspacePath(path)); artifactVersions[path] = createHash("sha256").update(bytes).digest("hex") }
      let exitCode = 0; let output = ""; try { const result = await execFileAsync("bash", ["-lc", command], { cwd: directory, timeout: TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024 }); output = `${result.stdout}${result.stderr}` } catch (error) { exitCode = error?.code === "ETIMEDOUT" || error?.killed ? 124 : Number.isInteger(error?.code) ? error.code : 1; output = `${error?.stdout ?? ""}${error?.stderr ?? ""}${error}` }
      const missingAssertions = (item.definition.boundaryVerification.requiredAssertions ?? []).filter((marker) => !output.includes(marker)); if (exitCode === 0 && missingAssertions.length) exitCode = 1
      const cases = item.definition.boundaryVerification.interactionCases ?? []
      const producerArtifacts = item.definition.producer.artifacts
      const consumerArtifacts = item.definition.consumer.artifacts
      const shared = producerArtifacts.filter((path) => consumerArtifacts.includes(path))
      let realPath = cases.some((entry) => entry.binding?.commandFragment && command.includes(entry.binding.commandFragment))
      if (!realPath && shared.length) realPath = shared.some((path) => command.includes(path))
      if (!realPath && producerArtifacts.length && consumerArtifacts.length) {
        for (const consumerPath of consumerArtifacts.filter((path) => command.includes(path))) {
          const consumerSource = (await readFile(workspacePath(consumerPath), "utf8")).toString()
          if (producerArtifacts.some((path) => {
            const moduleName = path.split("/").at(-1).replace(/\.[^.]+$/, "")
            return consumerSource.includes(path) || new RegExp(`(?:from|import)\\s+${moduleName.replace(/[.*+?^${}()|[\\]\\]/g, "\\$&")}(?:\\s|\\.|$)`).test(consumerSource)
          })) { realPath = true; break }
        }
      }
      await record(mem, current.runId, { type: "boundary.verified", contractId: args.contract_id, version: args.version, command, exitCode, realPath, artifactVersions, evidenceRefs: args.evidence_refs })
      return JSON.stringify({ exitCode, missingAssertions, output: output.slice(-4000), decision: mem.integrationDecision(args.contract_id) })
    }}),
    codomain_decision: tool({ description: "Gate only the real producer-consumer integration boundary.", args: { contract_id: tool.schema.string() }, async execute(args) { const mem = await memory(); return JSON.stringify(mem.integrationDecision(args.contract_id)) }}),
  },
  "tool.execute.before": async (input, output) => {
    if (!mechanisms.codomain || input.tool !== "task" || !isImplementationTask(output.args)) return
    let mem
    try { mem = await memory() } catch (error) { if (error?.code === "ENOENT") return; throw error }
    const pending = mem.list().filter((item) => item.agreementState !== "accepted")
    if (pending.length) throw new Error(`co-domain implementation spawn blocked until both participants accept the current contract: ${pending.map((item) => item.definition.contractId).join(", ")}`)
  }}
}
