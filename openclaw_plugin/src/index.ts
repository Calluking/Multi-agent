import { Type } from "typebox";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { MemoryEngine, type ContractAction, type MemoryKind, type PluginConfig } from "./memory-engine.js";

function numericExitCode(value: unknown, depth = 0): number | undefined {
  if (depth > 4 || value === null || typeof value !== "object") return undefined;
  const record = value as Record<string, unknown>;
  for (const key of ["exitCode", "exit_code", "code", "statusCode"]) {
    if (typeof record[key] === "number") return record[key] as number;
  }
  for (const nested of Object.values(record)) {
    const found = numericExitCode(nested, depth + 1);
    if (found !== undefined) return found;
  }
  return undefined;
}

function commandFrom(params: Record<string, unknown>): string | undefined {
  for (const key of ["command", "cmd", "code"]) {
    if (typeof params[key] === "string" && params[key].trim()) return params[key].trim();
  }
  return undefined;
}

const RecordParameters = Type.Object({
  id: Type.String({ description: "Stable memory item id." }),
  kind: Type.Union([Type.Literal("dependency"), Type.Literal("codomain"), Type.Literal("testing")]),
  scope: Type.Union([Type.Literal("private"), Type.Literal("shared")]),
  title: Type.String(),
  text: Type.String(),
  status: Type.Optional(Type.String()),
  tags: Type.Optional(Type.Array(Type.String())),
  targetRoles: Type.Optional(Type.Array(Type.String(), { description: "Roles that should receive this item, for example implementer or reviewer." })),
  participants: Type.Optional(Type.Array(Type.String(), { description: "Product components/domains that share this contract." })),
  projectId: Type.Optional(Type.String({ description: "Stable project or task identity used for canonicalization." })),
  runId: Type.Optional(Type.String({ description: "Stable execution/run identity used to isolate task-local state." })),
  artifactIds: Type.Optional(Type.Array(Type.String(), { description: "Stable repository-relative artifact paths or API artifact identities." })),
  interfaceId: Type.Optional(Type.String({ description: "Stable producer-consumer interface identity for co-domain contracts." })),
  subject: Type.Optional(Type.String({ description: "Stable obligation or dependency subject identity." })),
  producerIds: Type.Optional(Type.Array(Type.String(), { description: "Assignments or components that produce this artifact or interface." })),
  consumerIds: Type.Optional(Type.Array(Type.String(), { description: "Assignments or components that consume this artifact or interface." })),
  verificationSubject: Type.Optional(Type.String({ description: "Stable behavior, artifact, or interface verified by a testing record." })),
  verificationCommand: Type.Optional(Type.String({ description: "Exact command whose result verifies the current artifact versions." })),
  priority: Type.Optional(Type.Number()),
  version: Type.Optional(Type.Number()),
  evidence: Type.Optional(Type.Array(Type.String())),
});

const ContractTransitionParameters = Type.Object({
  id: Type.String(),
  scope: Type.Union([Type.Literal("private"), Type.Literal("shared")]),
  title: Type.String(),
  text: Type.String(),
  action: Type.Union([
    Type.Literal("propose"), Type.Literal("challenge"), Type.Literal("revise"),
    Type.Literal("accept"), Type.Literal("verify"),
  ]),
  baseVersion: Type.Optional(Type.Number()),
  projectId: Type.String(),
  runId: Type.Optional(Type.String()),
  artifactIds: Type.Array(Type.String()),
  interfaceId: Type.String(),
  producerIds: Type.Array(Type.String()),
  consumerIds: Type.Array(Type.String()),
  targetRoles: Type.Optional(Type.Array(Type.String())),
  participants: Type.Optional(Type.Array(Type.String())),
  priority: Type.Optional(Type.Number()),
  evidence: Type.Optional(Type.Array(Type.String())),
});

export default definePluginEntry({
  id: "multiagent-memory",
  name: "Multi-Agent Memory",
  description: "Inject three complementary memory types into OpenClaw subagent creation.",
  register(api) {
    const config = (api.pluginConfig ?? {}) as PluginConfig;
    const engine = new MemoryEngine(config);
    type PendingInjection = {
      injectionId: string;
      selected: Record<string, string[]>;
      assignment?: string;
      workspace?: string;
      projectId?: string;
      runId?: string;
    };
    const pendingByParent = new Map<string, PendingInjection[]>();
    const childLedger = new Map<string, PendingInjection>();
    const initializedRootSessions = new Set<string>();
    const rootSessionKeys = new Set<string>();
    const workspaceBySession = new Map<string, string>();
    const projectBySession = new Map<string, string>();
    const projectByRun = new Map<string, string>();
    const runBySession = new Map<string, string>();

    if (engine.config.autoInitialize) {
      api.on("before_prompt_build", async (event: any, ctx: any) => {
        const prompt = String(event?.prompt ?? event?.userPrompt ?? event?.message ?? "");
        if (!prompt || prompt.startsWith("/") || prompt.includes("[Subagent Context]")) return event;
        const sessionKey = String(ctx?.sessionKey ?? event?.sessionKey ?? "");
        const isChildSession = Boolean(ctx?.requesterSessionKey ?? event?.requesterSessionKey)
          || sessionKey.includes(":subagent:");
        if (isChildSession) return event;
        if (sessionKey && initializedRootSessions.has(sessionKey)) return event;
        if (sessionKey) {
          initializedRootSessions.add(sessionKey);
          rootSessionKeys.add(sessionKey);
        }
        const workspace = String(ctx?.workspaceDir ?? event?.workspaceDir ?? "");
        if (workspace) {
          try {
            const taskText = await readFile(resolve(workspace, "TASK.md"), "utf8");
            const runId = sessionKey || undefined;
            const projectId = await engine.initializeFromTask(taskText, runId);
            if (sessionKey) {
              projectBySession.set(sessionKey, projectId);
              runBySession.set(sessionKey, sessionKey);
              projectByRun.set(sessionKey, projectId);
            }
          } catch {
            // Memory initialization is fail-open; the original task proceeds.
          }
        }
        const context = [
          "[Multi-Agent Memory Plugin — automatic control plane]",
          "Follow the requested agent workflow directly. Spawn the assigned producer when its inputs are ready, wait for its artifact, then retry the intended downstream spawn.",
          "Do not inspect or edit the plugin store, and do not call memory tools to mark dependency artifacts ready, resolved, accepted, or verified. The plugin observes files and command results automatically at spawn and completion boundaries.",
          "If a spawn is blocked, follow the gate reason: resume the named recovery owner, make a materially changed repair, rerun the stated verification, then retry the blocked spawn.",
          "Use multiagent_contract_transition only when a child packet explicitly identifies a shared product/API contract requiring proposal, revision, acceptance, or real boundary verification. Never use contract transitions for workflow artifacts such as plan.md, solution.py, implementation.md, review.md, or PATCH_READY.md.",
        ].join("\n");
        return {
          ...event,
          injectedContext: event?.injectedContext ? `${event.injectedContext}\n\n${context}` : context,
          prependContext: event?.prependContext ? `${event.prependContext}\n\n${context}` : context,
        };
      });

    }

    api.on("before_tool_call", async (event, ctx) => {
      let observedWorkspace = String((ctx as any)?.workspaceDir ?? event.params.workdir
        ?? event.params.cwd ?? "");
      if (ctx.sessionKey && observedWorkspace) workspaceBySession.set(ctx.sessionKey, observedWorkspace);
      if (event.toolName !== "sessions_spawn") return;
      const task = typeof event.params.task === "string" ? event.params.task : "";
      if (!task.trim()) return;
      if (!observedWorkspace) {
        // Coordinators commonly state the assigned workspace explicitly in a
        // native spawn objective even when the hook context omits workspaceDir.
        // Recover that path so artifact readiness remains observer-owned.
        observedWorkspace = task.match(/(?:working|work)\s+(?:only\s+)?in\s+`?(\/[^`\s),]+)/i)?.[1]?.trim()
          ?? task.match(/workspace(?:\s+root)?[^/\n]*(\/[^)\n]+)/i)?.[1]?.trim()
          ?? "";
      }
      if (ctx.sessionKey && observedWorkspace) {
        workspaceBySession.set(ctx.sessionKey, observedWorkspace);
      }
      // before_prompt_build does not expose workspaceDir on every OpenClaw
      // runtime. The first spawn objective is the reliable native seam and
      // normally carries the task/product context prepared by the coordinator.
      const parent = ctx.sessionKey ?? "unknown-parent";
      const runId = runBySession.get(parent) ?? parent;
      // Keep every spawn in a root session on one stable project identity.
      // Child objectives vary by role, so hashing each spawn's task text
      // creates a fresh dependency graph and makes produced prerequisites
      // appear missing again. Prefer the root TASK.md when it is available.
      let projectId = projectBySession.get(parent) ?? projectByRun.get(runId);
      if (!projectId) {
        let projectTask = task;
        if (observedWorkspace) {
          try {
            projectTask = await readFile(resolve(observedWorkspace, "TASK.md"), "utf8");
          } catch {
            // Fall back to the spawn objective when no task artifact exists.
          }
        }
        projectId = await engine.initializeFromTask(projectTask, runId);
      }
      projectBySession.set(parent, projectId);
      runBySession.set(parent, runId);
      projectByRun.set(runId, projectId);
      // Native sessions_spawn commonly provides workdir/cwd on the tool call
      // while omitting workspaceDir from hook context.
      const workspace = observedWorkspace;
      const role = task.toLowerCase().includes("reviewer") ? "reviewer"
        : task.toLowerCase().includes("implementer") ? "implementer"
          : task.toLowerCase().includes("planner") ? "planner" : undefined;
      const assignment = typeof (event.params as any).taskName === "string" ? String((event.params as any).taskName)
        : typeof (event.params as any).label === "string" ? String((event.params as any).label) : undefined;
      const consumerId = assignment ?? role;
      if (assignment) {
        await engine.registerAssignment({ projectId, runId, assignmentId: assignment, task, workspace });
      }
      if (workspace) await engine.observeWorkflow(workspace, consumerId, projectId, runId);
      if (consumerId) {
        const recovery = await engine.recoveryAdmission(consumerId, projectId, runId);
        if (!recovery.allowed) {
          return {
            block: true,
            blockReason: `Multi-agent recovery gate blocked ${consumerId}: ${recovery.reason}. `
              + "Escalate for explicit task-level intervention instead of repeating the failed strategy.",
          };
        }
      }
      const blockers = await engine.readinessBlockers(consumerId, projectId, runId);
      if (blockers.length) {
        const detail = blockers.map((item) =>
          `${item.id} (${item.lifecycleState ?? item.status ?? "unresolved"}; recovery owner=${item.recoveryOwnerId ?? item.producerIds?.[0] ?? "unassigned"})`).join(", ");
        return {
          block: true,
          blockReason: `Multi-agent readiness gate blocked ${consumerId}: ${detail}. Spawn or resume the recovery owner, produce/verify the prerequisite, then retry this consumer.`,
        };
      }
      const injectionId = `inject:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      const { packet, selected, role: inferredRole } = await engine.buildSpawnPacket(
        task, parent, assignment, projectId, runId);
      if (!packet) return;
      const queue = pendingByParent.get(parent) ?? [];
      queue.push({
        injectionId,
        selected: { ...selected, role: inferredRole ? [inferredRole] : [] },
        assignment: consumerId,
        workspace,
        projectId,
        runId,
      });
      pendingByParent.set(parent, queue.slice(-20));
      return { params: { ...event.params, task: `${task}${packet}\nInjection id: ${injectionId}` } };
    }, { priority: 80, timeoutMs: 10_000 });

    api.on("after_tool_call", async (event, ctx) => {
      const command = commandFrom(event.params);
      if (!command) return;
      const workspace = String((ctx as any)?.workspaceDir ?? event.params.workdir
        ?? event.params.cwd ?? (ctx.sessionKey ? workspaceBySession.get(ctx.sessionKey) : "") ?? "");
      if (!workspace) return;
      const exitCode = event.error ? 1 : numericExitCode(event.result);
      if (exitCode === undefined) return;
      await engine.recordVerification(workspace, {
        command,
        exitCode,
        source: `after-tool-call:${event.toolName}`,
        output: event.result === undefined ? undefined : JSON.stringify(event.result),
        error: event.error,
        projectId: ctx.sessionKey ? projectBySession.get(ctx.sessionKey) : undefined,
        runId: ctx.sessionKey ? runBySession.get(ctx.sessionKey) : undefined,
      });
    }, { priority: 80, timeoutMs: 10_000 });

    api.on("before_agent_finalize", async (event) => {
      const sessionKey = event.sessionKey ?? "";
      if (!sessionKey || sessionKey.includes(":subagent:")
        || !rootSessionKeys.has(sessionKey) || event.stopHookActive) return;
      const terminalIntent = /\b(done|complete|completed|finished|final|successfully|all tests pass(?:ed)?)\b/i
        .test(event.lastAssistantMessage ?? "");
      if (!terminalIntent) return;
      const projectId = projectBySession.get(sessionKey);
      const runId = runBySession.get(sessionKey);
      const workspace = event.cwd ?? workspaceBySession.get(sessionKey);
      if (!projectId || !runId) return;
      if (workspace) await engine.observeWorkflow(workspace, undefined, projectId, runId);
      const blockers = await engine.completionBlockers(projectId, runId);
      if (!blockers.length) return;
      const summary = blockers.map((item) =>
        `${item.id}[${item.lifecycleState ?? item.status ?? "unresolved"}]`).join(", ");
      return {
        action: "revise" as const,
        reason: `Multi-agent completion gate found unresolved obligations: ${summary}`,
        retry: {
          idempotencyKey: `multiagent-completion:${projectId}:${runId}`,
          maxAttempts: 1,
          instruction: `Do not report completion. Resolve these exact obligations first: ${summary}. `
            + "Resume or spawn the recorded recovery owner, use a materially changed strategy after failure, rerun the configured verification command, and verify every shared contract with real boundary evidence.",
        },
      };
    }, { priority: 80, timeoutMs: 10_000 });

    api.on("subagent_spawned", async (event: any, ctx: any) => {
      // OpenClaw exposes the parent/requester identity on the subagent hook
      // context, not as parentSessionKey on the event.
      const parent = ctx.requesterSessionKey ?? event.requesterSessionKey ?? "unknown-parent";
      const pending = pendingByParent.get(parent)?.shift();
      if (pending && event.childSessionKey) {
        childLedger.set(event.childSessionKey, pending);
        if (pending.workspace) workspaceBySession.set(event.childSessionKey, pending.workspace);
        if (pending.projectId) projectBySession.set(event.childSessionKey, pending.projectId);
        if (pending.runId) runBySession.set(event.childSessionKey, pending.runId);
      }
    });

    api.on("subagent_ended", async (event: any) => {
      const childKey = event.targetSessionKey;
      const record = childKey ? childLedger.get(childKey) : undefined;
      if (!record) return;
      await engine.recordLifecycleOutcome({
        selectedIds: record.selected.dependency ?? [],
        assignment: record.assignment,
        outcome: event.outcome ?? event.reason ?? "unknown",
        error: event.error,
      });
      await engine.upsert({
        id: `episode:${record.injectionId}`,
        kind: "testing",
        scope: "shared",
        projectId: "runtime-episodes",
        verificationSubject: `episode:${record.injectionId}`,
        title: "Subagent execution episode",
        text: `outcome=${event.outcome ?? event.reason ?? "unknown"}; selected=${JSON.stringify(record.selected)}`,
        status: event.outcome ?? event.reason ?? "unknown",
        evidence: event.error ? [String(event.error)] : [],
        tags: ["subagent", "episode"],
      });
      childLedger.delete(childKey);
      if (childKey) workspaceBySession.delete(childKey);
      if (childKey) projectBySession.delete(childKey);
      if (childKey) runBySession.delete(childKey);
    });

    api.registerTool({
      name: "multiagent_memory_record",
      label: "Record Multi-Agent Memory",
      description: "Create or update a typed dependency, co-domain contract, or testing-practice memory item.",
      parameters: RecordParameters,
      async execute(_id, rawParams) {
        const params = rawParams as {
          id: string; kind: MemoryKind; scope: "private" | "shared";
          title: string; text: string; status?: string; tags?: string[]; evidence?: string[];
          targetRoles?: string[]; participants?: string[]; priority?: number; version?: number;
          projectId?: string; runId?: string; artifactIds?: string[]; interfaceId?: string; subject?: string;
          producerIds?: string[]; consumerIds?: string[]; verificationSubject?: string;
          verificationCommand?: string;
        };
        const memory = {
          id: params.id,
          kind: params.kind as MemoryKind,
          scope: params.scope,
          title: params.title,
          text: params.text,
          status: params.status,
          tags: params.tags,
          targetRoles: params.targetRoles,
          participants: params.participants,
          projectId: params.projectId,
          runId: params.runId,
          artifactIds: params.artifactIds,
          interfaceId: params.interfaceId,
          subject: params.subject,
          producerIds: params.producerIds,
          consumerIds: params.consumerIds,
          verificationSubject: params.verificationSubject,
          verificationCommand: params.verificationCommand,
          priority: params.priority,
          version: params.version,
          evidence: params.evidence,
        };
        const stored = await engine.upsert(memory);
        return { content: [{ type: "text", text: `Stored ${stored.kind} memory ${stored.id}.` }], details: stored };
      },
    });

    api.registerTool({
      name: "multiagent_contract_transition",
      label: "Transition Multi-Agent Contract",
      description: "Apply a typed, version-checked lifecycle transition to a co-domain contract. Never use for dependency readiness.",
      parameters: ContractTransitionParameters,
      async execute(_id, rawParams) {
        const params = rawParams as {
          id: string; scope: "private" | "shared"; title: string; text: string;
          action: ContractAction; baseVersion?: number; projectId: string; runId?: string;
          artifactIds: string[]; interfaceId: string; producerIds: string[]; consumerIds: string[];
          targetRoles?: string[]; participants?: string[]; priority?: number; evidence?: string[];
        };
        const stored = await engine.applyContractAction({
          id: params.id, kind: "codomain", scope: params.scope, title: params.title, text: params.text,
          projectId: params.projectId, runId: params.runId, artifactIds: params.artifactIds,
          interfaceId: params.interfaceId, producerIds: params.producerIds, consumerIds: params.consumerIds,
          targetRoles: params.targetRoles, participants: params.participants, priority: params.priority,
          evidence: params.evidence,
        }, params.action, params.baseVersion);
        return { content: [{ type: "text", text: `Contract ${stored.id} is ${stored.status} at version ${stored.version}.` }], details: stored };
      },
    });

    api.registerTool({
      name: "multiagent_memory_inspect",
      label: "Inspect Multi-Agent Memory",
      description: "Inspect memory items that would be retrieved for a task or subagent objective.",
      parameters: Type.Object({
        query: Type.String(),
        projectId: Type.Optional(Type.String()),
        runId: Type.Optional(Type.String()),
      }),
      async execute(_id, rawParams) {
        const params = rawParams as { query: string; projectId?: string; runId?: string };
        const result = await engine.inspect(params.query, undefined, params.projectId, params.runId);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: result };
      },
    });
  },
});
