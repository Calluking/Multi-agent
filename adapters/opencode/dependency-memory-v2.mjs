import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, join, resolve } from "node:path"
import { promisify } from "node:util"
import { tool } from "@opencode-ai/plugin"
import {
  DependencyMemory,
  JsonlDependencyEventStore,
} from "../../dist/src/dependency/index.js"
import { parseMechanismSwitches } from "../../dist/src/config.js"

const now = () => new Date().toISOString()
const id = () => crypto.randomUUID()
const execFileAsync = promisify(execFile)
const VERIFICATION_TIMEOUT_MS = 120_000
const INTERACTION_SCHEMA_HELP = "interactionCases must be a nonempty array of {id,category,marker}; category is normal|error|precedence|compatibility and marker must also appear in requiredAssertions. When any declared output exists in Git HEAD, include interfaceEvidence:[{id,path,contains}] where contains is a short exact baseline snippet, plus at least one compatibility case with binding:{evidenceId,path,symbol,commandFragment}; commandFragment must contain symbol, occur exactly in the verification command, and the bound path must be in covers. Example: interactionCases:[{id:'existing-call',category:'compatibility',marker:'COMPAT_PASS',binding:{evidenceId:'baseline-api',path:'src/api.py',symbol:'old_arg',commandFragment:'test_old_arg'}}], interfaceEvidence:[{id:'baseline-api',path:'src/api.py',contains:'def api(old_arg):'}]"

function safeVerificationCommand(command) {
  if (typeof command !== "string" || !command.trim()) throw new Error("verification command is required")
  const forbidden = [
    /(^|[;&|]\s*)touch\s+(?:\/usr|\/bin|\/sbin|\/opt|\/etc)\//i,
    /(?:^|\s)(?:sudo|apt(?:-get)?|dnf|yum|apk|pacman)\s/i,
    /(?:^|\s)(?:python\d*(?:\.\d+)?\s+-m\s+venv|virtualenv|conda\s+(?:create|install))\b/i,
    /(?:^|\s)(?:rm|mv|cp|install|ln)\s+[^;&|]*(?:\/usr|\/bin|\/sbin|\/opt|\/etc)\//i,
  ]
  if (forbidden.some((pattern) => pattern.test(command))) {
    throw new Error("verification commands may not install runtimes, create environments, or modify system paths")
  }
  // Ubuntu/WSL commonly ships Python as `python3` without the optional `python`
  // alias. Verification must use the existing runtime, never try to create it.
  return command.replace(/(^|[;&|]\s*)python(?=\s)/g, "$1python3")
}

function requiredAssertions(verification) {
  const assertions = verification.requiredAssertions ?? verification.required_assertions ?? []
  if (!Array.isArray(assertions) || assertions.length === 0 || assertions.some((item) => typeof item !== "string" || !item.trim())) {
    throw new Error("each verification requires nonempty observable output markers in requiredAssertions")
  }
  return assertions
}

async function baselineSource(directory, path) {
  try {
    const { stdout } = await execFileAsync("git", ["-C", directory, "show", `HEAD:${path}`], { maxBuffer: 4 * 1024 * 1024 })
    return stdout
  } catch {
    return null
  }
}

async function validateInteractionGrounding(verification, directory, existingOutputs) {
  const cases = verification.interactionCases ?? []
  if (!Array.isArray(cases) || cases.length === 0) throw new Error(`each verification requires structured interactionCases. ${INTERACTION_SCHEMA_HELP}`)
  for (const item of cases) {
    if (!item?.id || !["normal", "error", "precedence", "compatibility"].includes(item.category) || !item.marker) throw new Error(`each interaction case requires id, category, and marker. ${INTERACTION_SCHEMA_HELP}`)
    if (!verification.requiredAssertions.includes(item.marker)) throw new Error(`interaction marker must be required: ${item.marker}`)
  }
  if (existingOutputs.length === 0) return
  if (!cases.some((item) => item.category === "compatibility")) throw new Error(`an existing output interface requires a compatibility interaction case. ${INTERACTION_SCHEMA_HELP}`)
  const evidence = verification.interfaceEvidence ?? []
  if (!Array.isArray(evidence) || evidence.length === 0) throw new Error(`an existing output interface requires exact interfaceEvidence. ${INTERACTION_SCHEMA_HELP}`)
  for (const item of evidence) {
    if (!item?.id || !item?.path || !item?.contains) throw new Error("interfaceEvidence requires id, path, and exact contains text")
    if (!existingOutputs.includes(item.path)) throw new Error(`interface evidence is not a declared baseline artifact: ${item.path}`)
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
    if (!binding.commandFragment.includes(binding.symbol) || !verification.command.includes(binding.commandFragment)) throw new Error(`compatibility case ${item.id} command must exercise its exact baseline-bound fragment`)
    if (!(verification.covers ?? []).includes(binding.path)) throw new Error(`compatibility case ${item.id} baseline path must be hash-covered`)
  }
}

async function runVerification(command, directory) {
  const normalizedCommand = safeVerificationCommand(command)
  try {
    const { stdout, stderr } = await execFileAsync("bash", ["-lc", normalizedCommand], {
      cwd: directory,
      timeout: VERIFICATION_TIMEOUT_MS,
      maxBuffer: 4 * 1024 * 1024,
    })
    return { success: true, output: `${stdout}${stderr}`, command: normalizedCommand }
  } catch (error) {
    const timedOut = error?.killed === true || error?.code === "ETIMEDOUT"
    return {
      success: false,
      output: timedOut ? `verification timed out after ${VERIFICATION_TIMEOUT_MS}ms` : `${error?.stdout ?? ""}${error?.stderr ?? ""}${error}`,
      command: normalizedCommand,
      timedOut,
    }
  }
}

export default async function dependencyMemoryPlugin({ directory, $ }, options = {}) {
  const mechanisms = parseMechanismSwitches(
    typeof options.mechanisms === "string" ? options.mechanisms : process.env.MAM_MECHANISMS,
  )
  const statePath = join(directory, ".multi-agent-memory", "run.json")
  const eventPath = join(directory, ".multi-agent-memory", "events.jsonl")
  const nativeCalls = new Map()

  async function state() {
    return JSON.parse(await readFile(statePath, "utf8"))
  }

  async function memory() {
    const current = await state()
    return DependencyMemory.open(current.runId, new JsonlDependencyEventStore(eventPath))
  }

  async function initialized() {
    try {
      return (await state()).initialized === true
    } catch (error) {
      if (error?.code !== "ENOENT") throw error
      return false
    }
  }

  async function record(mem, runId, value) {
    await mem.record({ ...value, eventId: id(), runId, observedAt: now() })
  }

  function obligationFromTaskArgs(args) {
    const text = `${args?.prompt ?? ""}\n${args?.description ?? ""}`
    return [
      /obligation\s+ID\s+is\s*:\s*`?([A-Za-z0-9_.:-]+)/i,
      /obligation\s+ID\s+(?:is\s*)?`([^`]+)`/i,
      /obligation\s+`([^`]+)`/i,
      /obligation[_ -]?id\s*[:=]\s*`?([A-Za-z0-9_.:-]+)/i,
    ].map((pattern) => text.match(pattern)?.[1]).find(Boolean)
  }

  function isExplicitAuxiliary(args) {
    const text = `${args?.prompt ?? ""}\n${args?.description ?? ""}`
    return /task[_ -]?mode\s*[:=]\s*auxiliary\b/i.test(text) && /read[- ]only/i.test(text)
  }

  async function reconcileObligation(obligationId, output) {
    const current = await state(); const mem = await memory(); const before = mem.get(obligationId)
    if (!before) return { reconciled: false, reason: "unknown obligation" }
    if (before.completed) return { reconciled: true, completed: true, deduplicated: true }

    for (const requirement of before.requiredOutputs) {
      const absolute = resolve(directory, requirement.artifactId)
      if (!absolute.startsWith(resolve(directory) + "/")) throw new Error("artifact escapes workspace")
      try {
        const bytes = await readFile(absolute)
        const version = createHash("sha256").update(bytes).digest("hex")
        if (before.artifacts[requirement.artifactId]?.version !== version) {
          await record(mem, current.runId, { type: "artifact.observed", obligationId, artifactId: requirement.artifactId, exists: true, version })
        }
      } catch (error) {
        if (error?.code !== "ENOENT") throw error
        if (before.artifacts[requirement.artifactId]) {
          await record(mem, current.runId, { type: "artifact.observed", obligationId, artifactId: requirement.artifactId, exists: false })
        }
      }
    }

    for (const requirement of before.requiredVerifications) {
      const refreshed = mem.get(obligationId)
      const versions = {}
      let coverPresent = true
      for (const path of requirement.covers) {
        const artifact = refreshed?.artifacts[path]
        if (!artifact) { coverPresent = false; break }
        versions[path] = artifact.version
      }
      const old = refreshed?.verifications[requirement.verificationId]
      const alreadyCurrent = coverPresent && old?.success && old.command === requirement.command && requirement.covers.every((path) => old.artifactVersions[path] === versions[path])
      if (alreadyCurrent || !coverPresent) continue
      let success = true
      const result = await runVerification(requirement.command, directory)
      success = result.success && (requirement.requiredAssertions ?? []).every((marker) => result.output.includes(marker))
      await record(mem, current.runId, { type: "verification.observed", obligationId, verificationId: requirement.verificationId, command: requirement.command, success, artifactVersions: versions })
    }

    const afterEvidence = mem.get(obligationId)
    if (afterEvidence?.active) {
      await record(mem, current.runId, { type: "owner.ended", obligationId, ownerId: afterEvidence.ownerId, outcome: "ok" })
    }
    if (mem.completionSatisfied(obligationId)) {
      const latest = mem.get(obligationId)
      if (!latest?.completed) await record(mem, current.runId, { type: "obligation.completed", obligationId })
      return { reconciled: true, completed: true }
    }
    const final = mem.get(obligationId)
    return {
      reconciled: true,
      completed: false,
      status: final?.status,
      missingOutputs: final?.requiredOutputs.filter((item) => !final.artifacts[item.artifactId]).map((item) => item.artifactId),
      message: `Dependency obligation ${obligationId} needs recovery; downstream work remains blocked.`,
      childOutputTail: String(output ?? "").slice(-500),
    }
  }

  return {
    tool: {
      memory_capabilities: tool({
        description: "Report which universal memory mechanisms are enabled and implemented for this run.",
        args: {},
        async execute() {
          return JSON.stringify({
            switches: mechanisms,
            implementation: { dependency: "available", codomain: "not_implemented", testing: "not_implemented" },
          })
        },
      }),
      memory_initialize: tool({
        description: `Activate dependency memory and declare an explicit generic obligation graph. Do not invent requirements absent from the task or accepted assignments. This tool is self-describing; do not inspect plugin source. ${INTERACTION_SCHEMA_HELP}`,
        args: {
          obligations_json: tool.schema.string().describe(`JSON array: [{id,owner,title,outputs:[paths],verifications:[{id,command,covers:[paths],requiredAssertions:[markers],interactionCases:[{id,category,marker,binding?}],interfaceEvidence?:[{id,path,contains}]}]}]. ${INTERACTION_SCHEMA_HELP}`),
          edges_json: tool.schema.string().describe("JSON array: [{upstream,downstream,requirement}], where requirement is requires_accepted, requires_produced, requires_verified, or requires_complete"),
        },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ activated: false, mechanism: "dependency", reason: "disabled by run configuration" })
          if (await initialized()) {
            const existing = await memory()
            return JSON.stringify({ activated: false, reason: "run already initialized", ready: existing.readySet() })
          }
          const obligations = JSON.parse(args.obligations_json)
          const edges = JSON.parse(args.edges_json)
          for (const item of obligations) {
            const existingOutputs = []
            for (const output of item.outputs ?? []) if (await baselineSource(directory, output) !== null) existingOutputs.push(output)
            for (const verification of item.verifications ?? []) {
              verification.command = safeVerificationCommand(verification.command)
              verification.requiredAssertions = requiredAssertions(verification)
              await validateInteractionGrounding(verification, directory, existingOutputs)
            }
          }
          const byId = new Map(obligations.map((item) => [item.id, item]))
          for (const edge of edges) {
            if (!byId.has(edge.upstream) || !byId.has(edge.downstream)) throw new Error(`edge references unknown obligation: ${edge.upstream}->${edge.downstream}`)
            if (edge.requirement === "requires_verified" && (byId.get(edge.upstream).verifications ?? []).length === 0) {
              throw new Error(`requires_verified edge ${edge.upstream}->${edge.downstream} needs an upstream verification declaration; declare one or use the truthful required state`)
            }
          }
          const runId = id()
          await mkdir(dirname(statePath), { recursive: true })
          await writeFile(statePath, JSON.stringify({ runId, mechanisms, initialized: false }, null, 2))
          const mem = await memory()
          for (const item of obligations) {
            await record(mem, runId, {
              type: "obligation.declared",
              obligation: {
                obligationId: item.id, runId, ownerId: item.owner, title: item.title,
                source: { type: "explicit_declaration", evidenceRef: "memory_initialize" },
                requiredOutputs: (item.outputs ?? []).map((artifactId) => ({ artifactId })),
                requiredVerifications: (item.verifications ?? []).map((verification) => ({
                  verificationId: verification.verificationId ?? verification.id,
                  command: verification.command,
                  covers: verification.covers ?? [],
                  requiredAssertions: verification.requiredAssertions,
                  interactionCases: verification.interactionCases,
                  interfaceEvidence: verification.interfaceEvidence,
                })),
              },
            })
          }
          for (const edge of edges) {
            await record(mem, runId, {
              type: "dependency.declared",
              edge: {
                edgeId: `${edge.upstream}->${edge.downstream}`, runId,
                upstreamId: edge.upstream, downstreamId: edge.downstream,
                requirement: edge.requirement, evidenceRef: "memory_initialize",
              },
            })
          }
          await writeFile(statePath, JSON.stringify({ runId, mechanisms, initialized: true }, null, 2))
          return JSON.stringify({ activated: true, runId, initialized: true, ready: mem.readySet() })
        },
      }),
      memory_inspect: tool({
        description: "Inspect dependency-memory ready work, obligations, and blockers.",
        args: {},
        async execute() {
          if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false })
          if (!(await initialized())) return JSON.stringify({ mechanism: "dependency", enabled: true, initialized: false, ready: [], obligations: [] }, null, 2)
          const mem = await memory()
          return JSON.stringify({ mechanism: "dependency", enabled: true, initialized: true, ready: mem.readySet(), obligations: mem.list() }, null, 2)
        },
      }),
      memory_extend_graph: tool({
        description: "Atomically add newly discovered managed work to the dependency graph before spawning it.",
        args: {
          obligation_json: tool.schema.string().describe("JSON {id,owner,title,outputs:[paths],verifications:[...]}"),
          incoming_edges_json: tool.schema.string().describe("JSON [{upstream,requirement,evidenceRef}]"),
        },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false })
          const current = await state(); const mem = await memory(); const item = JSON.parse(args.obligation_json)
          const edges = JSON.parse(args.incoming_edges_json)
          for (const verification of item.verifications ?? []) {
            verification.command = safeVerificationCommand(verification.command)
            verification.requiredAssertions = requiredAssertions(verification)
            const existingOutputs = []
            for (const output of item.outputs ?? []) if (await baselineSource(directory, output) !== null) existingOutputs.push(output)
            await validateInteractionGrounding(verification, directory, existingOutputs)
          }
          await record(mem, current.runId, { type: "obligation.declared", obligation: {
            obligationId: item.id, runId: current.runId, ownerId: item.owner, title: item.title,
            source: { type: "explicit_declaration", evidenceRef: "memory_extend_graph" },
            requiredOutputs: (item.outputs ?? []).map((artifactId) => ({ artifactId })),
            requiredVerifications: (item.verifications ?? []).map((v) => ({ verificationId: v.id ?? v.verificationId, command: v.command, covers: v.covers ?? [], requiredAssertions: v.requiredAssertions, interactionCases: v.interactionCases, interfaceEvidence: v.interfaceEvidence })),
          }})
          try {
            for (const edge of edges) await record(mem, current.runId, { type: "dependency.declared", edge: { edgeId: `${edge.upstream}->${item.id}`, runId: current.runId, upstreamId: edge.upstream, downstreamId: item.id, requirement: edge.requirement, evidenceRef: edge.evidenceRef ?? "dynamic-discovery" } })
          } catch (error) {
            await record(mem, current.runId, { type: "obligation.cancelled", obligationId: item.id, reason: `atomic graph extension rejected: ${error.message}` })
            throw error
          }
          return JSON.stringify({ added: item.id, decision: mem.spawnDecision(item.id), ready: mem.readySet() })
        },
      }),
      memory_start: tool({
        description: "Gate and start one spawn-ready obligation before doing or delegating its work.",
        args: { obligation_id: tool.schema.string(), owner_id: tool.schema.string() },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ decision: "disabled", mechanism: "dependency" })
          const current = await state(); const mem = await memory()
          const decision = mem.spawnDecision(args.obligation_id)
          if (decision.decision === "wait") return JSON.stringify(decision)
          await record(mem, current.runId, { type: "owner.started", obligationId: args.obligation_id, ownerId: args.owner_id })
          return JSON.stringify({ decision: "allow", obligationId: args.obligation_id })
        },
      }),
      memory_observe_artifact: tool({
        description: "Observe and hash a declared artifact after writing it. This records production, not verification.",
        args: { obligation_id: tool.schema.string(), path: tool.schema.string() },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false })
          const current = await state(); const mem = await memory(); const absolute = resolve(directory, args.path)
          if (!absolute.startsWith(resolve(directory) + "/")) throw new Error("artifact escapes workspace")
          try {
            const bytes = await readFile(absolute)
            const version = createHash("sha256").update(bytes).digest("hex")
            await record(mem, current.runId, { type: "artifact.observed", obligationId: args.obligation_id, artifactId: args.path, exists: true, version })
            return JSON.stringify({ exists: true, version })
          } catch (error) {
            if (error?.code !== "ENOENT") throw error
            await record(mem, current.runId, { type: "artifact.observed", obligationId: args.obligation_id, artifactId: args.path, exists: false })
            return JSON.stringify({ exists: false })
          }
        },
      }),
      memory_verify: tool({
        description: "Run a declared deterministic verification command and bind its result to current artifact hashes.",
        args: { obligation_id: tool.schema.string(), verification_id: tool.schema.string(), command: tool.schema.string(), covers: tool.schema.array(tool.schema.string()) },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false })
          const current = await state(); const mem = await memory(); const recordState = mem.get(args.obligation_id)
          const declared = recordState?.requiredVerifications.find((item) => item.verificationId === args.verification_id)
          const command = safeVerificationCommand(args.command)
          if (!declared || declared.command !== command) throw new Error("verification was not declared exactly")
          if (JSON.stringify([...args.covers].sort()) !== JSON.stringify([...declared.covers].sort())) throw new Error("verification covers differ from the declaration")
          const artifactVersions = {}
          for (const path of args.covers) {
            const bytes = await readFile(resolve(directory, path)); artifactVersions[path] = createHash("sha256").update(bytes).digest("hex")
          }
          const result = await runVerification(command, directory)
          const missingAssertions = (declared.requiredAssertions ?? []).filter((marker) => !result.output.includes(marker))
          const success = result.success && missingAssertions.length === 0; const output = result.output
          await record(mem, current.runId, { type: "verification.observed", obligationId: args.obligation_id, verificationId: args.verification_id, command, success, artifactVersions })
          return JSON.stringify({ success, missingAssertions, output: output.slice(-4000) })
        },
      }),
      memory_end: tool({
        description: "Reconcile an owner's termination. Ending does not imply completion.",
        args: { obligation_id: tool.schema.string(), owner_id: tool.schema.string(), outcome: tool.schema.enum(["ok", "error", "timeout", "killed"]) },
        async execute(args) { if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false }); const current = await state(); const mem = await memory(); await record(mem, current.runId, { type: "owner.ended", obligationId: args.obligation_id, ownerId: args.owner_id, outcome: args.outcome }); return JSON.stringify(mem.get(args.obligation_id)) },
      }),
      memory_complete: tool({
        description: "Mark an obligation complete; rejected unless current declared artifacts and verification evidence exist.",
        args: { obligation_id: tool.schema.string() },
        async execute(args) { if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false }); const current = await state(); const mem = await memory(); await record(mem, current.runId, { type: "obligation.completed", obligationId: args.obligation_id }); return JSON.stringify({ ready: mem.readySet(), completed: args.obligation_id }) },
      }),
      memory_recover: tool({
        description: "Assign an explicit recovery owner and changed bounded strategy to an orphaned or failed obligation.",
        args: { obligation_id: tool.schema.string(), owner_id: tool.schema.string(), strategy: tool.schema.string(), evidence_ref: tool.schema.string() },
        async execute(args) {
          if (!mechanisms.dependency) return JSON.stringify({ mechanism: "dependency", enabled: false })
          const current = await state(); const mem = await memory()
          await record(mem, current.runId, { type: "recovery.assigned", obligationId: args.obligation_id, ownerId: args.owner_id, strategy: args.strategy, evidenceRef: args.evidence_ref })
          return JSON.stringify({ decision: mem.spawnDecision(args.obligation_id), recovery: mem.get(args.obligation_id)?.recovery })
        },
      }),
    },
    "tool.execute.before": async (input, output) => {
      if (mechanisms.dependency && input.tool === "task" && !(await initialized())) {
        throw new Error("dependency mechanism is enabled but not initialized: call memory_initialize first; a failed initialization attempt is retryable")
      }
      if (!mechanisms.dependency || input.tool !== "task") return
      let obligationId = obligationFromTaskArgs(output.args)
      if (!obligationId) {
        if (isExplicitAuxiliary(output.args)) return
        const mem = await memory()
        const active = mem.list().filter((item) => item.active)
        const candidates = active.length ? active : mem.list().filter((item) => mem.readySet().includes(item.obligationId))
        if (candidates.length === 1) obligationId = candidates[0].obligationId
        else throw new Error("dependency-managed task is ambiguous: include an existing obligation ID, first add discovered work with memory_extend_graph, or explicitly mark TASK_MODE: auxiliary read-only")
      }
      const current = await state(); const mem = await memory(); const item = mem.get(obligationId)
      if (!item) throw new Error(`native task names unknown dependency obligation ${obligationId}`)
      if (!item.active) {
        const decision = mem.spawnDecision(obligationId)
        if (decision.decision === "wait") throw new Error(`dependency spawn blocked: ${JSON.stringify(decision)}`)
        await record(mem, current.runId, { type: "owner.started", obligationId, ownerId: item.ownerId })
      }
      nativeCalls.set(input.callID, obligationId)
    },
    "tool.execute.after": async (input, output) => {
      if (!mechanisms.dependency) return
      const obligationId = input.tool === "task" ? nativeCalls.get(input.callID) : input.tool === "memory_end" ? input.args?.obligation_id : undefined
      if (!obligationId) return
      nativeCalls.delete(input.callID)
      const result = await reconcileObligation(obligationId, output.output)
      output.metadata = { ...(output.metadata ?? {}), dependencyMemoryV2: result }
      if (!result.completed && result.message) output.output = `${output.output}\n\n[DEPENDENCY MEMORY]\n${result.message}`
    },
  }
}
