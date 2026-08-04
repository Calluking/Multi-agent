import { Type } from "typebox";
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

    api.on("before_tool_call", async (event, ctx) => {
      if (event.toolName !== "sessions_spawn") return;
      const task = typeof event.params.task === "string" ? event.params.task : "";
      if (!task.trim()) return;
      const parent = ctx.sessionKey ?? "unknown-parent";
      const injectionId = `inject:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      const { packet, selected } = await engine.buildSpawnPacket(task, parent);
      if (!packet) return;
      const queue = pendingByParent.get(parent) ?? [];
      queue.push({ injectionId, selected });
      pendingByParent.set(parent, queue.slice(-20));
      return { params: { ...event.params, task: `${task}${packet}\nInjection id: ${injectionId}` } };
    }, { priority: 80, timeoutMs: 10_000 });

    api.on("subagent_spawned", async (event: any, ctx: any) => {
      const parent = event.parentSessionKey ?? ctx.sessionKey ?? "unknown-parent";
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
        };
        const stored = await engine.upsert({
          id: params.id,
          kind: params.kind as MemoryKind,
          scope: params.scope,
          title: params.title,
          text: params.text,
          status: params.status,
          tags: params.tags,
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
