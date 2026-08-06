import { access, mkdir, readFile, rename, stat, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";

export type MemoryKind = "dependency" | "codomain" | "testing";

export type PluginConfig = {
  storeRoot?: string;
  autoInitialize?: boolean;
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
  targetRoles?: string[];
  participants?: string[];
  projectId?: string;
  artifactIds?: string[];
  interfaceId?: string;
  subject?: string;
  producerIds?: string[];
  consumerIds?: string[];
  verificationSubject?: string;
  lifecycleState?: "planned" | "in_progress" | "blocked" | "produced" | "verified" | "ready";
  artifactObservations?: ArtifactObservation[];
  priority?: number;
  version?: number;
  status?: string;
  evidence?: string[];
  updatedAt: string;
};

export type ArtifactObservation = {
  artifactId: string;
  exists: boolean;
  size?: number;
  modifiedAt?: string;
  sha256?: string;
  observedAt: string;
  source: string;
};

export type Bank = { schemaVersion: "0.1"; items: MemoryItem[] };

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
  // State/priority refines an already relevant match; it must never make an
  // unrelated item retrievable by itself.
  if (result === 0) return 0;
  if (item.status === "unresolved" || item.status === "required") result += 2;
  return result;
}

export function inferRole(value: string): string | undefined {
  const text = value.toLowerCase();
  // Explicit assignment outranks artifact mentions. Implementer prompts often
  // mention plan.md and Reviewer prompts mention every predecessor artifact.
  if (/you are (?:the )?reviewer\b|role\s*[=:]\s*reviewer|responsible only for (?:executable )?verification/.test(text)) return "reviewer";
  if (/you are (?:the )?implementer\b|role\s*[=:]\s*implementer|responsible only for solution/.test(text)) return "implementer";
  if (/you are (?:the )?planner\b|role\s*[=:]\s*planner|responsible only for plan/.test(text)) return "planner";
  if (/\breviewer\b|review\.md|executable verification/.test(text)) return "reviewer";
  if (/\bimplementer\b|implementation\.md/.test(text)) return "implementer";
  if (/\bplanner\b|plan\.md/.test(text)) return "planner";
  return undefined;
}

function normalizedRoles(item: MemoryItem): string[] {
  const explicit = item.targetRoles ?? [];
  const tagged = (item.tags ?? [])
    .filter((tag) => tag.toLowerCase().startsWith("role:"))
    .map((tag) => tag.slice(5));
  return [...new Set([...explicit, ...tagged].map((role) => role.toLowerCase()))];
}

function isRelevantToRole(item: MemoryItem, role?: string): boolean {
  const roles = normalizedRoles(item);
  if (!roles.length) return true;
  return Boolean(role && roles.includes(role.toLowerCase()));
}

function isCurrent(item: MemoryItem): boolean {
  return !["superseded", "rejected", "closed"].includes((item.status ?? "").toLowerCase());
}

function isProductCodomain(item: MemoryItem): boolean {
  const value = `${item.title}\n${item.text}`;
  const producer = value.match(/producer domain\s*=\s*([^;\n]+)/i)?.[1] ?? "";
  const consumer = value.match(/consumer domain\s*=\s*([^;\n]+)/i)?.[1] ?? "";
  if (!producer || !consumer) return false;
  const endpoints = `${producer}\n${consumer}`;
  return !/\b(planner|planning|implementer|implementation|reviewer|review|verification|tooling)\b|plan\.md|solution\.py|implementation\.md|review\.md/i.test(endpoints);
}

function normalizeIdentity(value: string): string {
  return value.toLowerCase().replace(/\\/g, "/").replace(/\s+/g, " ").trim();
}

function normalizedSet(values: string[] | undefined): string[] {
  return [...new Set((values ?? []).map(normalizeIdentity).filter(Boolean))].sort();
}

function definedFields<T extends object>(value: T): Partial<T> {
  return Object.fromEntries(Object.entries(value).filter(([, field]) => field !== undefined)) as Partial<T>;
}

export function canonicalKey(item: MemoryItem): string {
  const project = normalizeIdentity(item.projectId ?? "");
  const owner = item.scope === "private" ? normalizeIdentity(item.ownerSessionKey ?? "") : "shared";
  const artifacts = normalizedSet(item.artifactIds).join("|");
  if (project) {
    if (item.kind === "dependency" && (item.subject || artifacts)) {
      return ["v1", item.kind, project, normalizeIdentity(item.subject ?? ""), artifacts, owner].join("::");
    }
    if (item.kind === "codomain" && (item.interfaceId || artifacts)) {
      return ["v1", item.kind, project, normalizeIdentity(item.interfaceId ?? ""), artifacts, owner].join("::");
    }
    if (item.kind === "testing" && item.verificationSubject) {
      return ["v1", item.kind, project, normalizeIdentity(item.verificationSubject),
        normalizedSet(item.targetRoles).join("|"), owner].join("::");
    }
  }

  // Old banks remain readable and retain exact normalized deduplication until
  // a record is updated with explicit structured identity.
  const normalize = (value: string) => value.toLowerCase().replace(/\s+/g, " ").trim();
  const tags = [...new Set((item.tags ?? []).map((tag) => tag.toLowerCase().trim()))].sort();
  const roles = [...new Set((item.targetRoles ?? []).map((role) => role.toLowerCase().trim()))].sort();
  return ["legacy",
    item.kind,
    item.scope,
    normalize(item.title),
    normalize(item.text),
    tags.join("|"),
    roles.join("|"),
    item.ownerSessionKey ?? "",
  ].join("::");
}

export class MemoryEngine {
  readonly root: string;
  readonly config: Required<Omit<PluginConfig, "storeRoot">>;
  private readonly writeTails = new Map<MemoryKind, Promise<void>>();

  constructor(config: PluginConfig = {}) {
    this.root = resolve(config.storeRoot ?? ".openclaw/multiagent-memory");
    this.config = {
      autoInitialize: config.autoInitialize ?? true,
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

  async retrieve(kind: MemoryKind, query: string, sessionKey?: string, role = inferRole(query)): Promise<MemoryItem[]> {
    const bank = await this.load(kind);
    return bank.items
      .filter((item) => item.kind === kind)
      .filter(isCurrent)
      .filter((item) => isRelevantToRole(item, role))
      .filter((item) => kind !== "codomain" || isProductCodomain(item))
      // Episodes are retained as learning/audit evidence. They are not team
      // practices and must not be replayed into every later child prompt.
      .filter((item) => !(kind === "testing" && item.tags?.includes("episode")))
      .map((item) => ({ item, score: score(item, query, sessionKey) }))
      // Sparse retrieval is essential: an unrelated practice or interface is
      // worse than no memory because it consumes context and changes behavior.
      .filter((entry) => entry.score > 0)
      .sort((a, b) => (b.item.priority ?? 0) - (a.item.priority ?? 0)
        || b.score - a.score || (b.item.version ?? 0) - (a.item.version ?? 0)
        || b.item.updatedAt.localeCompare(a.item.updatedAt))
      .slice(0, this.config.maxItemsPerMemory)
      .map((entry) => entry.item);
  }

  async upsert(item: Omit<MemoryItem, "updatedAt">): Promise<MemoryItem> {
    return this.withWriteLock(item.kind, async () => {
      const bank = await this.load(item.kind);
      const stored = { ...item, updatedAt: new Date().toISOString() };
      const exactIndex = bank.items.findIndex((candidate) => candidate.id === item.id);
      if (exactIndex >= 0) {
        bank.items[exactIndex] = { ...bank.items[exactIndex], ...definedFields(stored) };
        await this.save(item.kind, bank);
        return bank.items[exactIndex];
      }

      const fp = canonicalKey(stored);
      const semIndex = bank.items.findIndex((candidate) => canonicalKey(candidate) === fp);
      if (semIndex >= 0) {
        bank.items[semIndex] = { ...stored, id: bank.items[semIndex].id };
        await this.save(item.kind, bank);
        return bank.items[semIndex];
      } else {
        bank.items.push(stored);
      }
      await this.save(item.kind, bank);
      return stored;
    });
  }

  async initializeFromTask(taskText: string): Promise<void> {
    if (await this.initializeFromCooperativeAssignments(taskText)) return;
    const project = taskText.match(/called\s+([A-Za-z][A-Za-z0-9_-]+)/i)?.[1] ?? "task";
    const empty = async (kind: MemoryKind) => (await this.load(kind)).items.length === 0;
    if (this.config.dependencyEnabled && await empty("dependency")) {
      await this.upsert({
        id: `${project}:plan-artifact`, kind: "dependency", scope: "private",
        projectId: project, artifactIds: ["plan.md"], subject: "plan-artifact-readiness",
        title: `${project} planning target`, targetRoles: ["planner", "implementer"], priority: 100,
        text: "Required before=implementation; Required state=plan.md exists and reflects TASK.md; Observed=missing; Evidence=workspace file check; Blocker=plan.md absent; Next action=write and inspect plan.md",
        status: "unresolved", evidence: [], tags: [project, "artifact", "plan.md"],
      });
      await this.upsert({
        id: `${project}:implementation-artifacts`, kind: "dependency", scope: "private",
        projectId: project, artifactIds: ["solution.py", "implementation.md"], subject: "implementation-artifact-readiness",
        title: `${project} implementation target`, targetRoles: ["implementer", "reviewer"], priority: 100,
        text: "Required before=review; Required state=solution.py and implementation.md exist; Observed=missing; Evidence=workspace file check and executable command; Blocker=implementation artifacts absent; Next action=implement the complete TASK.md scope and run its primary verification",
        status: "unresolved", evidence: [], tags: [project, "artifact", "solution.py", "implementation.md"],
      });
      await this.upsert({
        id: `${project}:review-artifact`, kind: "dependency", scope: "private",
        projectId: project, artifactIds: ["review.md"], subject: "review-artifact-readiness",
        title: `${project} verification target`, targetRoles: ["reviewer"], priority: 100,
        text: "Required before=completion; Required state=review.md records an independently executed command, exit status, and result; Observed=missing; Evidence=workspace file check; Blocker=review evidence absent; Next action=run independent verification, repair material failures, and record exact evidence",
        status: "unresolved", evidence: [], tags: [project, "artifact", "review.md", "verification"],
      });
    }
    if (this.config.testingEnabled && await empty("testing")) {
      await this.upsert({
        id: `${project}:implementer-verification-practice`, kind: "testing", scope: "shared",
        projectId: project, verificationSubject: "implementation-public-interface",
        title: "Incremental public-interface verification", targetRoles: ["implementer"], priority: 80,
        text: "Responsibility=implementer; Trigger=multi-stage implementation or explicit ordering; Command=run executable checks after each implemented slice and the primary end-to-end path; Pass evidence=exit 0 plus assertions on observable public behavior; Failure action=diagnose and revise before handoff",
        status: "required", evidence: [], tags: [project, "role:implementer", "verification", "end-to-end"],
      });
      await this.upsert({
        id: `${project}:reviewer-verification-practice`, kind: "testing", scope: "shared",
        projectId: project, verificationSubject: "independent-boundary-verification",
        title: "Independent boundary and negative verification", targetRoles: ["reviewer"], priority: 90,
        text: "Responsibility=reviewer; Trigger=review or executable verification; Command=run the documented entrypoint and independent happy-path, invalid-input, ordering, and cross-boundary checks; Pass evidence=exact command, exit status, assertion counts, and observed result; Failure action=repair material failures and rerun before approval",
        status: "required", evidence: [], tags: [project, "role:reviewer", "verification", "boundary"],
      });
    }
    // Only create a co-domain contract when TASK.md itself identifies a real
    // producer/consumer boundary. Build-order wording alone remains dependency.
    if (this.config.codomainEnabled && await empty("codomain")
      && /registration|profile/i.test(taskText) && /feedback|rating|review/i.test(taskText)) {
      await this.upsert({
        id: `${project}:experience-feedback-contract`, kind: "codomain", scope: "shared",
        projectId: project, interfaceId: "experience-to-feedback", artifactIds: ["feedback-api"],
        producerIds: ["experience modules"], consumerIds: ["feedback and rating module"],
        title: "Experience modules to feedback boundary", targetRoles: ["implementer", "reviewer"],
        participants: ["experience modules", "feedback and rating module"], priority: 85, version: 1,
        text: "Producer domain=experience modules; Consumer domain=feedback and rating module; Shared data=target_type, target_id, participant user_id, completion state; Obligations=producer exposes stable existing experience identity and consumer rejects unknown or inaccessible targets; Invariant=feedback refers to a real completed tour, exchange, or workshop and rating remains within the declared range; Boundary test=create each real experience, submit feedback, then reject unknown id/type without side effects",
        status: "agreed", evidence: [], tags: [project, "feedback", "rating", "boundary"],
      });
      await this.upsert({
        id: `${project}:identity-feature-contract`, kind: "codomain", scope: "shared",
        projectId: project, interfaceId: "identity-to-protected-features", artifactIds: ["registered-user-identity"],
        producerIds: ["registration and profile module"], consumerIds: ["tour language and workshop modules"],
        title: "Registration identity to protected features", targetRoles: ["implementer", "reviewer"],
        participants: ["registration and profile module", "tour language and workshop modules"], priority: 80, version: 1,
        text: "Producer domain=registration and profile module; Consumer domain=tour language and workshop modules; Shared data=user_id, profile identity, cultural interests and languages; Obligations=producer returns a stable registered identity and consumers validate it before mutation; Invariant=no protected feature state is created for an unknown user; Boundary test=perform each feature with a registered user, then reject an unknown user while preserving state",
        status: "agreed", evidence: [], tags: [project, "registration", "profile", "boundary"],
      });
    }
  }

  private async initializeFromCooperativeAssignments(taskText: string): Promise<boolean> {
    const matches = [...taskText.matchAll(/\[Assignment\s+([^\]]+)\]([\s\S]*?)(?=\n\[Assignment\s+|$)/gi)];
    if (matches.length < 2) return false;
    const project = taskText.match(/\[Project\s+([^\]]+)\]/i)?.[1]?.trim() ?? "cooperative-task";
    const assignments = matches.map((match) => {
      const id = match[1].trim();
      const body = match[2].trim();
      const title = body.match(/(?:Title|Feature)\s*:\s*([^\n]+)/i)?.[1]?.trim() ?? id;
      const files = [...body.matchAll(/`([^`]+\.[A-Za-z0-9]+)`|(?:Files? Modified|File)\s*:\s*[-*]?\s*([^\s,]+)/gi)]
        .map((entry) => (entry[1] ?? entry[2] ?? "").replace(/^[-*]\s*/, "").trim())
        .filter(Boolean);
      return { id, body, title, files: [...new Set(files)] };
    });
    const sharedFiles = assignments[0].files.filter((file) => assignments.slice(1).some((item) => item.files.includes(file)));
    const taskTag = `project:${project.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

    if (this.config.dependencyEnabled) {
      for (const assignment of assignments) {
        await this.upsert({
          id: `${taskTag}:assignment:${assignment.id}`, kind: "dependency", scope: "private",
          projectId: project, artifactIds: assignment.files, subject: `assignment:${assignment.id}:handoff`,
          title: `${assignment.id} deliverable state`, targetRoles: [assignment.id], priority: 90,
          text: `Required before=assignment handoff; Required state=${assignment.title} implemented in ${assignment.files.join(", ") || "assigned artifact"}; Observed=missing; Evidence=patch and assignment tests; Blocker=assigned feature not yet evidenced; Next action=implement only ${assignment.id}, preserve partner-owned semantics, and report changed API/artifact plus test evidence`,
          status: "unresolved", evidence: [], tags: [taskTag, `assignment:${assignment.id}`, ...assignment.files],
        });
      }
    }
    if (this.config.codomainEnabled && sharedFiles.length) {
      const left = assignments[0], right = assignments[1];
      await this.upsert({
        id: `${taskTag}:shared-artifact:${sharedFiles.join("+")}`, kind: "codomain", scope: "shared",
        projectId: project, artifactIds: sharedFiles,
        interfaceId: `shared-artifact:${sharedFiles.join("+")}`,
        producerIds: [left.id], consumerIds: [right.id],
        title: `Shared contract for ${sharedFiles.join(", ")}`, targetRoles: assignments.map((item) => item.id),
        participants: assignments.map((item) => item.id), priority: 100, version: 1,
        text: `Producer domain=${left.id} (${left.title}); Consumer domain=${right.id} (${right.title}); Shared data=${sharedFiles.join(", ")} public API signature, default behavior, validation order, and return shape; Obligations=each assignment changes only its feature semantics while preserving the partner option and backward-compatible defaults; Invariant=both options compose in one call without either feature overwriting the other's signature, token stream, errors, or return type; Boundary test=run each feature test independently, then call the shared API with both options enabled and verify both behaviors simultaneously`,
        status: "proposed", evidence: [], tags: [taskTag, "shared-artifact", "composition", ...sharedFiles],
      });
    }
    if (this.config.testingEnabled) {
      for (const assignment of assignments) {
        await this.upsert({
          id: `${taskTag}:testing:${assignment.id}`, kind: "testing", scope: "shared",
          projectId: project, artifactIds: sharedFiles,
          verificationSubject: `assignment:${assignment.id}:composition`,
          title: `${assignment.id} independent and composition verification`, targetRoles: [assignment.id], priority: 90,
          text: `Responsibility=${assignment.id}; Trigger=shared artifact or API modified by another assignment; Command=run baseline tests, ${assignment.id} feature tests, and a composition check combining both assignments; Pass evidence=exact commands and assertions showing own feature, partner defaults, and joint behavior; Failure action=revise only the conflicting boundary and rerun before handoff`,
          status: "required", evidence: [], tags: [taskTag, `assignment:${assignment.id}`, "composition", ...sharedFiles],
        });
      }
    }
    return true;
  }

  async observeWorkflow(workspace: string, nextRole?: string): Promise<void> {
    const dependency = await this.load("dependency");
    for (const item of dependency.items) {
      if (!isRelevantToRole(item, nextRole)) continue;
      const wanted = item.artifactIds?.length
        ? item.artifactIds
        : (item.tags ?? []).filter((tag) => /\.(md|py)$/i.test(tag));
      if (!wanted.length) continue;
      const observations = await Promise.all(wanted.map((name) => this.observeArtifact(workspace, name, "before-spawn")));
      const missing = observations.filter((entry) => !entry.exists).map((entry) => entry.artifactId);
      const changedAfterVerification = item.lifecycleState === "verified" || item.lifecycleState === "ready"
        ? observations.some((entry) => {
          const prior = item.artifactObservations?.find((old) => old.artifactId === entry.artifactId && old.exists);
          return Boolean(prior?.sha256 && entry.sha256 && prior.sha256 !== entry.sha256);
        })
        : false;
      const lifecycleState = missing.length ? "blocked" : changedAfterVerification ? "produced"
        : item.lifecycleState === "verified" || item.lifecycleState === "ready" ? item.lifecycleState : "produced";
      const observed = observations.map((entry) => `${entry.artifactId}=${entry.exists ? `produced@${entry.sha256}` : "missing"}`);
      await this.upsert({
        ...item,
        status: missing.length ? "unresolved" : changedAfterVerification ? "stale" : item.status,
        lifecycleState,
        artifactObservations: observations,
        text: item.text
          .replace(/Observed=[^;]*/i, `Observed=${missing.length ? "missing" : "present"}`)
          .replace(/Evidence=[^;]*/i, `Evidence=${observed.join(", ")}`)
          .replace(/Blocker=[^;]*/i, `Blocker=${missing.length ? `${missing.join(", ")} absent` : changedAfterVerification ? "artifact changed after verification" : "null"}`),
        evidence: observed,
      });
    }
  }

  private async observeArtifact(workspace: string, artifactId: string, source: string): Promise<ArtifactObservation> {
    const root = resolve(workspace);
    const path = resolve(root, artifactId);
    const observedAt = new Date().toISOString();
    if (path !== root && !path.startsWith(root + "/")) {
      return { artifactId, exists: false, observedAt, source: `${source}:outside-workspace` };
    }
    try {
      const metadata = await stat(path);
      if (!metadata.isFile()) return { artifactId, exists: false, observedAt, source: `${source}:not-file` };
      const content = await readFile(path);
      return {
        artifactId,
        exists: true,
        size: metadata.size,
        modifiedAt: metadata.mtime.toISOString(),
        sha256: createHash("sha256").update(content).digest("hex"),
        observedAt,
        source,
      };
    } catch {
      return { artifactId, exists: false, observedAt, source };
    }
  }

  async buildSpawnPacket(task: string, parentSessionKey?: string, assignment?: string): Promise<{
    packet: string;
    selected: Record<MemoryKind, string[]>;
    role?: string;
  }> {
    const role = assignment ?? inferRole(task);
    const selected: Record<MemoryKind, string[]> = { dependency: [], codomain: [], testing: [] };
    const sections: string[] = [];
    const enabled: Array<[MemoryKind, boolean, string]> = [
      ["dependency", this.config.dependencyEnabled, "PRIVATE DEPENDENCY MEMORY — only this child’s target, prerequisites, blockers, and acceptance evidence"],
      ["codomain", this.config.codomainEnabled, "SHARED CO-DOMAIN CONTRACT MEMORY — interfaces and semantics agreed across producer/consumer boundaries"],
      ["testing", this.config.testingEnabled, "TEAM TESTING PRACTICE MEMORY — reusable verification responsibilities and valid evidence"],
    ];
    for (const [kind, isEnabled, heading] of enabled) {
      if (!isEnabled) continue;
      const items = await this.retrieve(kind, task, parentSessionKey, role);
      selected[kind] = items.map((item) => item.id);
      if (!items.length) continue;
      sections.push([heading, ...items.map((item) => `- [${item.id}] ${item.title}: ${item.text}`)].join("\n"));
    }
    if (!sections.length) return { packet: "", selected, role };
    return {
      selected,
      role,
      packet: [
        "\n\n--- MULTI-AGENT MEMORY CONTEXT (plugin-injected) ---",
        ...sections,
        `Target role: ${role ?? "unclassified"}. Only records relevant to this role/boundary were selected.`,
        "Use these records as current working context. Dependency records describe state, not permission to invent missing evidence. Co-domain records describe producer/consumer semantics, not Agent handoffs. Testing records are inject-only practices and add no retries or rerouting. If a record is wrong or stale, report a typed update through multiagent_memory_record instead of silently ignoring it.",
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
