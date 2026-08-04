import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

export type MemoryKind = "dependency" | "codomain" | "testing";

export type PluginConfig = {
  storeRoot?: string;
  dependencyEnabled?: boolean;
  codomainEnabled?: boolean;
  testingEnabled?: boolean;
  maxItemsPerMemory?: number;
};

export type MemoryItem = {
  id: string;
  kind: MemoryKind;
  scope: "private" | "shared";
  title: string;
  text: string;
  tags?: string[];
  ownerSessionKey?: string;
  status?: string;
  evidence?: string[];
  updatedAt: string;
};

type Bank = { schemaVersion: "0.1"; items: MemoryItem[] };

const EMPTY_BANK: Bank = { schemaVersion: "0.1", items: [] };

function terms(value: string): Set<string> {
  return new Set((value.toLowerCase().match(/[a-z0-9_+-]+|[\u4e00-\u9fff]{1,4}/g) ?? []));
}

function score(item: MemoryItem, query: string, sessionKey?: string): number {
  const queryTerms = terms(query);
  const itemTerms = terms([item.title, item.text, ...(item.tags ?? [])].join(" "));
  let result = 0;
  for (const token of queryTerms) if (itemTerms.has(token)) result += 1;
  if (item.scope === "private" && item.ownerSessionKey === sessionKey) result += 8;
  if (item.status === "unresolved" || item.status === "required") result += 2;
  return result;
}

export class MemoryEngine {
  readonly root: string;
  readonly config: Required<Omit<PluginConfig, "storeRoot">>;
  private readonly writeTails = new Map<MemoryKind, Promise<void>>();

  constructor(config: PluginConfig = {}) {
    this.root = resolve(config.storeRoot ?? ".openclaw/multiagent-memory");
    this.config = {
      dependencyEnabled: config.dependencyEnabled ?? true,
      codomainEnabled: config.codomainEnabled ?? true,
      testingEnabled: config.testingEnabled ?? true,
      maxItemsPerMemory: config.maxItemsPerMemory ?? 3,
    };
  }

  private path(kind: MemoryKind): string {
    return resolve(this.root, `${kind}.json`);
  }

  async load(kind: MemoryKind): Promise<Bank> {
    try {
      const raw = JSON.parse(await readFile(this.path(kind), "utf8")) as Bank;
      return Array.isArray(raw.items) ? raw : structuredClone(EMPTY_BANK);
    } catch {
      return structuredClone(EMPTY_BANK);
    }
  }

  async save(kind: MemoryKind, bank: Bank): Promise<void> {
    const path = this.path(kind);
    await mkdir(dirname(path), { recursive: true });
    const temporary = `${path}.${process.pid}.${Date.now()}.${Math.random().toString(36).slice(2)}.tmp`;
    await writeFile(temporary, JSON.stringify(bank, null, 2) + "\n", "utf8");
    await rename(temporary, path);
  }

  private async withWriteLock<T>(kind: MemoryKind, operation: () => Promise<T>): Promise<T> {
    const previous = this.writeTails.get(kind) ?? Promise.resolve();
    let release!: () => void;
    const current = new Promise<void>((resolveLock) => { release = resolveLock; });
    const tail = previous.then(() => current);
    this.writeTails.set(kind, tail);
    await previous;
    try {
      return await operation();
    } finally {
      release();
      if (this.writeTails.get(kind) === tail) this.writeTails.delete(kind);
    }
  }

  async retrieve(kind: MemoryKind, query: string, sessionKey?: string): Promise<MemoryItem[]> {
    const bank = await this.load(kind);
    return bank.items
      .filter((item) => item.kind === kind)
      // Episodes are retained as learning/audit evidence. They are not team
      // practices and must not be replayed into every later child prompt.
      .filter((item) => !(kind === "testing" && item.tags?.includes("episode")))
      .map((item) => ({ item, score: score(item, query, sessionKey) }))
      .filter((entry) => entry.score > 0 || kind === "testing")
      .sort((a, b) => b.score - a.score || b.item.updatedAt.localeCompare(a.item.updatedAt))
      .slice(0, this.config.maxItemsPerMemory)
      .map((entry) => entry.item);
  }

  async upsert(item: Omit<MemoryItem, "updatedAt">): Promise<MemoryItem> {
    return this.withWriteLock(item.kind, async () => {
      const bank = await this.load(item.kind);
      const stored = { ...item, updatedAt: new Date().toISOString() };
      const index = bank.items.findIndex((candidate) => candidate.id === item.id);
      if (index >= 0) bank.items[index] = stored;
      else bank.items.push(stored);
      await this.save(item.kind, bank);
      return stored;
    });
  }

  async buildSpawnPacket(task: string, parentSessionKey?: string): Promise<{
    packet: string;
    selected: Record<MemoryKind, string[]>;
  }> {
    const selected: Record<MemoryKind, string[]> = { dependency: [], codomain: [], testing: [] };
    const sections: string[] = [];
    const enabled: Array<[MemoryKind, boolean, string]> = [
      ["dependency", this.config.dependencyEnabled, "PRIVATE DEPENDENCY MEMORY — only this child’s target, prerequisites, blockers, and acceptance evidence"],
      ["codomain", this.config.codomainEnabled, "SHARED CO-DOMAIN CONTRACT MEMORY — interfaces and semantics agreed across producer/consumer boundaries"],
      ["testing", this.config.testingEnabled, "TEAM TESTING PRACTICE MEMORY — reusable verification responsibilities and valid evidence"],
    ];
    for (const [kind, isEnabled, heading] of enabled) {
      if (!isEnabled) continue;
      const items = await this.retrieve(kind, task, parentSessionKey);
      selected[kind] = items.map((item) => item.id);
      if (!items.length) continue;
      sections.push([heading, ...items.map((item) => `- [${item.id}] ${item.title}: ${item.text}`)].join("\n"));
    }
    if (!sections.length) return { packet: "", selected };
    return {
      selected,
      packet: [
        "\n\n--- MULTI-AGENT MEMORY CONTEXT (plugin-injected) ---",
        ...sections,
        "Use these records as current working context. Do not claim completion without observable artifact/test evidence. If a record is wrong or stale, report a typed update through multiagent_memory_record instead of silently ignoring it.",
        "--- END MULTI-AGENT MEMORY CONTEXT ---",
      ].join("\n\n"),
    };
  }

  async inspect(query: string, sessionKey?: string): Promise<Record<MemoryKind, MemoryItem[]>> {
    return {
      dependency: await this.retrieve("dependency", query, sessionKey),
      codomain: await this.retrieve("codomain", query, sessionKey),
      testing: await this.retrieve("testing", query, sessionKey),
    };
  }
}
