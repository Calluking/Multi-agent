import { Type } from "typebox";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { MemoryEngine, type MemoryKind, type PluginConfig } from "./memory-engine.js";

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
  artifactIds: Type.Optional(Type.Array(Type.String(), { description: "Stable repository-relative artifact paths or API artifact identities." })),
  interfaceId: Type.Optional(Type.String({ description: "Stable producer-consumer interface identity for co-domain contracts." })),
  subject: Type.Optional(Type.String({ description: "Stable obligation or dependency subject identity." })),
  producerIds: Type.Optional(Type.Array(Type.String(), { description: "Assignments or components that produce this artifact or interface." })),
  consumerIds: Type.Optional(Type.Array(Type.String(), { description: "Assignments or components that consume this artifact or interface." })),
  verificationSubject: Type.Optional(Type.String({ description: "Stable behavior, artifact, or interface verified by a testing record." })),
  priority: Type.Optional(Type.Number()),
  version: Type.Optional(Type.Number()),
  evidence: Type.Optional(Type.Array(Type.String())),
});

export default definePluginEntry({
  id: "multiagent-memory",
  name: "Multi-Agent Memory",
  description: "Inject three complementary memory types into OpenClaw subagent creation.",
  register(api) {
    const config = (api.pluginConfig ?? {}) as PluginConfig;
    const engine = new MemoryEngine(config);
    const pendingByParent = new Map<string, Array<{ injectionId: string; selected: Record<string, string[]> }>>();
    const childLedger = new Map<string, { injectionId: string; selected: Record<string, string[]> }>();
    const initializedRootSessions = new Set<string>();

    if (engine.config.autoInitialize) {
      api.on("before_prompt_build", async (event: any, ctx: any) => {
        const prompt = String(event?.prompt ?? event?.userPrompt ?? event?.message ?? "");
        if (!prompt || prompt.startsWith("/") || prompt.includes("[Subagent Context]")) return event;
        const sessionKey = String(ctx?.sessionKey ?? event?.sessionKey ?? "");
        if (sessionKey && initializedRootSessions.has(sessionKey)) return event;
        if (sessionKey) initializedRootSessions.add(sessionKey);
        const workspace = String(ctx?.workspaceDir ?? event?.workspaceDir ?? "");
        if (workspace) {
          try {
            const taskText = await readFile(resolve(workspace, "TASK.md"), "utf8");
            await engine.initializeFromTask(taskText);
          } catch {
            // Memory initialization is fail-open; the original task proceeds.
          }
        }
        const context = [
          "[Multi-Agent Memory Plugin — task-local initialization]",
          "Memory is sparse and fail-open. Do not create a record merely to satisfy the plugin, and never delay the first Planner spawn because a bank is empty.",
          "The plugin initializes canonical task-local records at the first spawn. Do not create duplicate records. Before a later child, inspect memory and update the existing canonical id only when you have new workspace/command evidence or a contract challenge.",
          "Canonical identity is structured, not prose-derived. Set projectId on task records; artifactIds to repository-relative paths or stable API artifacts; subject on dependency obligations; interfaceId plus producerIds/consumerIds on co-domain contracts; and verificationSubject on testing records. Records with the same kind-specific identity update one canonical entry even when their title or wording differs.",
          "Dependency format: `Required before=<consumer stage>; Required state=<artifact/product state>; Observed=<present|missing|invalid>; Evidence=<observable check/result>; Blocker=<exact current blocker or null>; Next action=<one recovery action>`. Set targetRoles to only the Agent that owns the next action. This memory tracks runtime state; it does not globally gate sessions_spawn.",
          "Co-domain format: `Producer domain=<product component>; Consumer domain=<different product component>; Shared data=<fields and meanings>; Obligations=<both sides>; Invariant=<cross-boundary rule>; Boundary test=<setup, action, observable result>`. Set participants to the two product components and targetRoles only to Agents implementing or verifying this boundary. Use status proposed/challenged/agreed/verified and increment version on revision. Never model Planner/Implementer/Reviewer handoff as a co-domain contract.",
          "Testing format: `Responsibility=<role>; Trigger=<task signal>; Command=<executable check>; Pass evidence=<exit/output/assertion>; Failure action=<diagnose and revise before handoff>`. Set targetRoles. It is inject-only: no retry, rerouting, or spawn gate.",
          "Before each later child spawn, observe the expected workspace artifact/command result and update any relevant dependency or contract record. If there is no relevant co-domain boundary, create no co-domain record.",
          "Use task-specific stable ids prefixed with the task/project name. Keep records concise. This policy must not change requested Agent roles, workflow, retries, or deliverables.",
        ].join("\n");
        return {
          ...event,
          injectedContext: event?.injectedContext ? `${event.injectedContext}\n\n${context}` : context,
          prependContext: event?.prependContext ? `${event.prependContext}\n\n${context}` : context,
        };
      });

    }

    api.on("before_tool_call", async (event, ctx) => {
      if (event.toolName !== "sessions_spawn") return;
      const task = typeof event.params.task === "string" ? event.params.task : "";
      if (!task.trim()) return;
      // before_prompt_build does not expose workspaceDir on every OpenClaw
      // runtime. The first spawn objective is the reliable native seam and
      // normally carries the task/product context prepared by the coordinator.
      await engine.initializeFromTask(task);
      const parent = ctx.sessionKey ?? "unknown-parent";
      const workspace = String((ctx as any)?.workspaceDir ?? "");
      const role = task.toLowerCase().includes("reviewer") ? "reviewer"
        : task.toLowerCase().includes("implementer") ? "implementer"
          : task.toLowerCase().includes("planner") ? "planner" : undefined;
      if (workspace) await engine.observeWorkflow(workspace, role);
      const injectionId = `inject:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      const assignment = typeof (event.params as any).taskName === "string" ? String((event.params as any).taskName)
        : typeof (event.params as any).label === "string" ? String((event.params as any).label) : undefined;
      const { packet, selected, role: inferredRole } = await engine.buildSpawnPacket(task, parent, assignment);
      if (!packet) return;
      const queue = pendingByParent.get(parent) ?? [];
      queue.push({ injectionId, selected: { ...selected, role: inferredRole ? [inferredRole] : [] } });
      pendingByParent.set(parent, queue.slice(-20));
      return { params: { ...event.params, task: `${task}${packet}\nInjection id: ${injectionId}` } };
    }, { priority: 80, timeoutMs: 10_000 });

    api.on("subagent_spawned", async (event: any, ctx: any) => {
      // OpenClaw exposes the parent/requester identity on the subagent hook
      // context, not as parentSessionKey on the event.
      const parent = ctx.requesterSessionKey ?? event.requesterSessionKey ?? "unknown-parent";
      const pending = pendingByParent.get(parent)?.shift();
      if (pending && event.childSessionKey) childLedger.set(event.childSessionKey, pending);
    });

    api.on("subagent_ended", async (event: any) => {
      const childKey = event.targetSessionKey;
      const record = childKey ? childLedger.get(childKey) : undefined;
      if (!record) return;
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
          projectId?: string; artifactIds?: string[]; interfaceId?: string; subject?: string;
          producerIds?: string[]; consumerIds?: string[]; verificationSubject?: string;
        };
        const stored = await engine.upsert({
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
          artifactIds: params.artifactIds,
          interfaceId: params.interfaceId,
          subject: params.subject,
          producerIds: params.producerIds,
          consumerIds: params.consumerIds,
          verificationSubject: params.verificationSubject,
          priority: params.priority,
          version: params.version,
          evidence: params.evidence,
        });
        return { content: [{ type: "text", text: `Stored ${stored.kind} memory ${stored.id}.` }], details: stored };
      },
    });

    api.registerTool({
      name: "multiagent_memory_inspect",
      label: "Inspect Multi-Agent Memory",
      description: "Inspect memory items that would be retrieved for a task or subagent objective.",
      parameters: Type.Object({ query: Type.String() }),
      async execute(_id, rawParams) {
        const params = rawParams as { query: string };
        const result = await engine.inspect(params.query);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: result };
      },
    });
  },
});
