import { access, mkdir, readFile, rename, stat, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { basename, dirname, isAbsolute, relative, resolve } from "node:path";
import { homedir } from "node:os";

export type MemoryKind = "dependency" | "codomain" | "testing";
export type ContractAction = "propose" | "challenge" | "revise" | "accept" | "verify";

export type PluginConfig = {
  storeRoot?: string;
  autoInitialize?: boolean;
  dependencyEnabled?: boolean;
  codomainEnabled?: boolean;
  testingEnabled?: boolean;
  maxItemsPerMemory?: number;
  maxRecoveryAttempts?: number;
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
  runId?: string;
  artifactIds?: string[];
  /** Explicit producer completion packets declared with `Artifact:`. */
  handoffArtifactIds?: string[];
  interfaceId?: string;
  subject?: string;
  producerIds?: string[];
  consumerIds?: string[];
  verificationSubject?: string;
  verificationCommand?: string;
  verificationCommands?: string[];
  lifecycleState?: "planned" | "in_progress" | "blocked" | "produced" | "verified" | "ready";
  artifactObservations?: ArtifactObservation[];
  verificationAttempts?: VerificationAttempt[];
  recoveryOwnerId?: string;
  lifecycleOutcomes?: LifecycleOutcome[];
  assignmentId?: string;
  workDirectory?: string;
  priority?: number;
  version?: number;
  status?: string;
  evidence?: string[];
  updatedAt: string;
};

export type LifecycleOutcome = {
  assignment?: string;
  outcome: string;
  observedAt: string;
  error?: string;
};

export type VerificationAttempt = {
  command: string;
  exitCode: number;
  passed: boolean;
  artifactVersions: Record<string, string>;
  observedAt: string;
  source: string;
  output?: string;
  error?: string;
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

function escapePattern(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const ARTIFACT_EXTENSIONS = new Set([
  "c", "cc", "cpp", "css", "go", "h", "hpp", "html", "java", "js", "jsx", "json",
  "md", "mjs", "py", "rb", "rs", "sh", "sql", "toml", "ts", "tsx", "xml", "yaml", "yml",
]);

function artifactPath(value: string): string | undefined {
  const cleaned = value.trim().replace(/^[-*]\s*/, "").replace(/[),.;:]+$/, "");
  const extension = cleaned.match(/\.([A-Za-z0-9]+)$/)?.[1]?.toLowerCase();
  if (!extension || !ARTIFACT_EXTENSIONS.has(extension)) return undefined;
  if (/\s|^https?:/i.test(cleaned)) return undefined;
  return cleaned.replace(/^\.\//, "");
}

function declaredArtifactPath(value: string): string | undefined {
  const cleaned = value.trim().replace(/^[-*]\s*/, "").replace(/[),.;:]+$/, "");
  if (!cleaned || /\s|^https?:|(^|[\\/])\.\.([\\/]|$)/i.test(cleaned)) return undefined;
  return /\.[A-Za-z0-9]+$/.test(cleaned) ? cleaned.replace(/^\.\//, "") : undefined;
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
  return Boolean(role && roles.some((candidate) => sameAssignmentRole(candidate, role)));
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

function roleIdentity(value: string): string {
  const normalized = normalizeIdentity(value);
  for (const role of ["planner", "implementer", "reviewer", "coordinator"]) {
    if (new RegExp(`(^|[^a-z])${role}(?:[^a-z]|$)`, "i").test(normalized)) return role;
  }
  return normalized;
}

function sameAssignmentRole(left: string, right: string): boolean {
  const a = roleIdentity(left);
  const b = roleIdentity(right);
  return Boolean(a && b && a === b);
}

export function canonicalVerificationCommand(command: string, workspace: string): string {
  const withoutExitEcho = command.trim().replace(
    /\s*;\s*echo\s+["']?EXIT\s*=\s*\$\?["']?\s*$/i,
    "",
  );
  const segments = withoutExitEcho.split(/\s*&&\s*/);
  if (segments.length > 1) {
    const cd = segments[0].match(/^cd\s+(["']?)(.+?)\1$/i);
    if (cd && resolve(cd[2]) === resolve(workspace)) {
      return normalizeIdentity(segments.slice(1).join(" && "))
        .replace(/(^|\s)python3(?=\s)/g, "$1python");
    }
  }
  return normalizeIdentity(withoutExitEcho)
    .replace(/(^|\s)python3(?=\s)/g, "$1python");
}

function commandWorkspace(command: string, workspace: string): string {
  const matches = [...command.matchAll(/(?:^|&&|;)\s*cd\s+(?:"([^"]+)"|'([^']+)'|([^\s;&]+))/gi)];
  const cd = matches.at(-1);
  const target = cd?.[1] ?? cd?.[2] ?? cd?.[3];
  return target ? resolve(workspace, target) : resolve(workspace);
}

function verificationCommandsMatch(expected: string, actual: string, workspace: string): boolean {
  const wanted = canonicalVerificationCommand(expected, workspace);
  const observed = canonicalVerificationCommand(actual, workspace);
  if (!wanted || !observed) return false;
  if (wanted === observed || observed.startsWith(`${wanted} `)
    || wanted.startsWith(`${observed} `)) return true;
  const escaped = wanted.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  if (new RegExp(`(?:^|&&|\\|\\||;)\\s*${escaped}(?=$|\\s|;|&&|\\|\\||[<>])`).test(observed)) {
    return true;
  }
  // A reviewer may use a Python heredoc that imports the deliverable and
  // exercises its public API instead of invoking its interactive entrypoint.
  // Count that as executable evidence, but never accept syntax-only checks.
  const pythonArtifact = wanted.match(/^python\s+([^\s;]+)/)?.[1];
  if (pythonArtifact && /(?:^|[;&|])\s*python\s+-\s+<</.test(observed)
    && !/py_compile|compileall/.test(observed)) {
    const stem = basename(pythonArtifact).replace(/\.py$/i, "");
    return new RegExp(`\\b(?:from\\s+${escapePattern(stem)}\\s+import|import\\s+${escapePattern(stem)}\\b)`).test(observed);
  }
  return false;
}

function normalizedSet(values: string[] | undefined): string[] {
  return [...new Set((values ?? []).map(normalizeIdentity).filter(Boolean))].sort();
}

function definedFields<T extends object>(value: T): Partial<T> {
  return Object.fromEntries(Object.entries(value).filter(([, field]) => field !== undefined)) as Partial<T>;
}

export function canonicalKey(item: MemoryItem): string {
  const project = normalizeIdentity(item.projectId ?? "");
  const run = normalizeIdentity(item.runId ?? "");
  const owner = item.scope === "private" ? normalizeIdentity(item.ownerSessionKey ?? "") : "shared";
  const artifacts = normalizedSet(item.artifactIds).join("|");
  if (project) {
    if (item.kind === "dependency" && (item.subject || artifacts)) {
      return ["v1", item.kind, project, run, normalizeIdentity(item.subject ?? ""), artifacts, owner].join("::");
    }
    if (item.kind === "codomain" && (item.interfaceId || artifacts)) {
      return ["v1", item.kind, project, run, normalizeIdentity(item.interfaceId ?? ""), artifacts, owner].join("::");
    }
    if (item.kind === "testing" && item.verificationSubject) {
      return ["v1", item.kind, project, run, normalizeIdentity(item.verificationSubject),
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

export function inferProjectId(taskText: string): string {
  const explicit = taskText.match(/\[Project\s+([^\]]+)\]/i)?.[1]?.trim()
    ?? taskText.match(/called\s+([A-Za-z][A-Za-z0-9_-]+)/i)?.[1]?.trim();
  if (explicit) return explicit;
  return `task-${createHash("sha256").update(taskText.trim()).digest("hex").slice(0, 12)}`;
}

function inContext(item: MemoryItem, projectId?: string, runId?: string): boolean {
  if (projectId && item.projectId && normalizeIdentity(item.projectId) !== normalizeIdentity(projectId)) return false;
  if (runId && item.runId && normalizeIdentity(item.runId) !== normalizeIdentity(runId)) return false;
  return true;
}

function sameRecordContext(left: MemoryItem, right: Pick<MemoryItem, "projectId" | "runId">): boolean {
  return normalizeIdentity(left.projectId ?? "") === normalizeIdentity(right.projectId ?? "")
    && normalizeIdentity(left.runId ?? "") === normalizeIdentity(right.runId ?? "");
}

export class MemoryEngine {
  readonly root: string;
  readonly config: Required<Omit<PluginConfig, "storeRoot">>;
  private readonly writeTails = new Map<MemoryKind, Promise<void>>();

  constructor(config: PluginConfig = {}) {
    this.root = resolve(config.storeRoot ?? resolve(homedir(), ".openclaw/multiagent-memory"));
    this.config = {
      autoInitialize: config.autoInitialize ?? true,
      dependencyEnabled: config.dependencyEnabled ?? true,
      codomainEnabled: config.codomainEnabled ?? true,
      testingEnabled: config.testingEnabled ?? true,
      maxItemsPerMemory: config.maxItemsPerMemory ?? 3,
      maxRecoveryAttempts: config.maxRecoveryAttempts ?? 2,
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

  async retrieve(kind: MemoryKind, query: string, sessionKey?: string, role = inferRole(query),
                 projectId?: string, runId?: string): Promise<MemoryItem[]> {
    const bank = await this.load(kind);
    return bank.items
      .filter((item) => item.kind === kind)
      .filter((item) => inContext(item, projectId, runId))
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
      const matchingIds = bank.items
        .map((candidate, index) => ({ candidate, index }))
        .filter(({ candidate }) => candidate.id === item.id);
      const exactIndex = item.projectId === undefined && item.runId === undefined && matchingIds.length === 1
        ? matchingIds[0].index
        : matchingIds.find(({ candidate }) => sameRecordContext(candidate, item))?.index ?? -1;
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

  async applyContractAction(item: Omit<MemoryItem, "updatedAt">, action: ContractAction,
                            baseVersion?: number): Promise<MemoryItem> {
    if (item.kind !== "codomain") throw new Error("contract actions require kind=codomain");
    const bank = await this.load("codomain");
    const existing = bank.items.find((candidate) => candidate.id === item.id && sameRecordContext(candidate, item)
      || canonicalKey(candidate) === canonicalKey({ ...item, updatedAt: "" }));
    if (action === "propose") {
      if (existing) throw new Error(`contract already exists as ${existing.id} version ${existing.version ?? 1}`);
      return this.upsert({ ...item, version: 1, status: "proposed" });
    }
    if (!existing) throw new Error(`cannot ${action} a missing contract`);
    const currentVersion = existing.version ?? 1;
    if (baseVersion !== currentVersion) {
      throw new Error(`stale contract update: baseVersion=${baseVersion ?? "missing"}, current=${currentVersion}`);
    }
    const status = action === "challenge" ? "challenged"
      : action === "revise" ? "proposed"
        : action === "accept" ? "agreed" : "verified";
    const version = action === "revise" ? currentVersion + 1 : currentVersion;
    return this.upsert({ ...existing, ...definedFields(item), id: existing.id, version, status });
  }

  async initializeFromTask(taskText: string, runId?: string): Promise<string> {
    const project = inferProjectId(taskText);
    const prefix = runId
      ? `${project}:run:${createHash("sha256").update(runId).digest("hex").slice(0, 10)}`
      : project;
    if (await this.initializeFromCooperativeAssignments(taskText, project, runId)) return project;
    const empty = async (kind: MemoryKind) => !(await this.load(kind)).items
      .some((item) => item.kind === kind && inContext(item, project, runId) && item.projectId);
    if (this.config.dependencyEnabled && await empty("dependency")) {
      await this.upsert({
        id: `${prefix}:plan-artifact`, kind: "dependency", scope: "private",
        projectId: project, runId, artifactIds: ["plan.md"], subject: "plan-artifact-readiness",
        producerIds: ["planner"], consumerIds: ["implementer"],
        title: `${project} planning target`, targetRoles: ["planner", "implementer"], priority: 100,
        text: "Required before=implementation; Required state=plan.md exists and reflects TASK.md; Observed=missing; Evidence=workspace file check; Blocker=plan.md absent; Next action=write and inspect plan.md",
        status: "unresolved", evidence: [], tags: [project, "artifact", "plan.md"],
      });
      await this.upsert({
        id: `${prefix}:implementation-artifacts`, kind: "dependency", scope: "private",
        projectId: project, runId, artifactIds: ["solution.py", "implementation.md"], subject: "implementation-artifact-readiness",
        verificationCommand: "python3 solution.py",
        producerIds: ["implementer"], consumerIds: ["reviewer"],
        title: `${project} implementation target`, targetRoles: ["implementer", "reviewer"], priority: 100,
        text: "Required before=review; Required state=solution.py and implementation.md exist; Observed=missing; Evidence=workspace file check and executable command; Blocker=implementation artifacts absent; Next action=implement the complete TASK.md scope and run its primary verification",
        status: "unresolved", evidence: [], tags: [project, "artifact", "solution.py", "implementation.md"],
      });
      await this.upsert({
        id: `${prefix}:review-artifact`, kind: "dependency", scope: "private",
        projectId: project, runId, artifactIds: ["review.md"], subject: "review-artifact-readiness",
        producerIds: ["reviewer"], consumerIds: ["completion"],
        title: `${project} verification target`, targetRoles: ["reviewer"], priority: 100,
        text: "Required before=completion; Required state=review.md records an independently executed command, exit status, and result; Observed=missing; Evidence=workspace file check; Blocker=review evidence absent; Next action=run independent verification, repair material failures, and record exact evidence",
        status: "unresolved", evidence: [], tags: [project, "artifact", "review.md", "verification"],
      });
    }
    if (this.config.testingEnabled && await empty("testing")) {
      await this.upsert({
        id: `${prefix}:implementer-verification-practice`, kind: "testing", scope: "shared",
        projectId: project, runId, verificationSubject: "implementation-public-interface",
        title: "Incremental public-interface verification", targetRoles: ["implementer"], priority: 80,
        text: "Responsibility=implementer; Trigger=multi-stage implementation or explicit ordering; Command=run executable checks after each implemented slice and the primary end-to-end path; Pass evidence=exit 0 plus assertions on observable public behavior; Failure action=diagnose and revise before handoff",
        status: "required", evidence: [], tags: [project, "role:implementer", "verification", "end-to-end"],
      });
      await this.upsert({
        id: `${prefix}:reviewer-verification-practice`, kind: "testing", scope: "shared",
        projectId: project, runId, verificationSubject: "independent-boundary-verification",
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
        id: `${prefix}:experience-feedback-contract`, kind: "codomain", scope: "shared",
        projectId: project, runId, interfaceId: "experience-to-feedback", artifactIds: ["feedback-api"],
        producerIds: ["experience modules"], consumerIds: ["feedback and rating module"],
        title: "Experience modules to feedback boundary", targetRoles: ["implementer", "reviewer"],
        participants: ["experience modules", "feedback and rating module"], priority: 85, version: 1,
        text: "Producer domain=experience modules; Consumer domain=feedback and rating module; Shared data=target_type, target_id, participant user_id, completion state; Obligations=producer exposes stable existing experience identity and consumer rejects unknown or inaccessible targets; Invariant=feedback refers to a real completed tour, exchange, or workshop and rating remains within the declared range; Boundary test=create each real experience, submit feedback, then reject unknown id/type without side effects",
        status: "agreed", evidence: [], tags: [project, "feedback", "rating", "boundary"],
      });
      await this.upsert({
        id: `${prefix}:identity-feature-contract`, kind: "codomain", scope: "shared",
        projectId: project, runId, interfaceId: "identity-to-protected-features", artifactIds: ["registered-user-identity"],
        producerIds: ["registration and profile module"], consumerIds: ["tour language and workshop modules"],
        title: "Registration identity to protected features", targetRoles: ["implementer", "reviewer"],
        participants: ["registration and profile module", "tour language and workshop modules"], priority: 80, version: 1,
        text: "Producer domain=registration and profile module; Consumer domain=tour language and workshop modules; Shared data=user_id, profile identity, cultural interests and languages; Obligations=producer returns a stable registered identity and consumers validate it before mutation; Invariant=no protected feature state is created for an unknown user; Boundary test=perform each feature with a registered user, then reject an unknown user while preserving state",
        status: "agreed", evidence: [], tags: [project, "registration", "profile", "boundary"],
      });
    }
    return project;
  }

  private async initializeFromCooperativeAssignments(taskText: string, project: string,
                                                      runId?: string): Promise<boolean> {
    const matches = [...taskText.matchAll(/\[Assignment\s+([^\]]+)\]([\s\S]*?)(?=\n\[Assignment\s+|$)/gi)];
    if (matches.length < 2) return false;
    const assignments = matches.map((match) => {
      const id = match[1].trim();
      const body = match[2].trim().split(/\n(?:Peer\s+\d+|taskName\/label|taskName|label)\s*:/i)[0].trim();
      const title = body.match(/(?:Title|Feature)\s*:\s*([^\n]+)/i)?.[1]?.trim() ?? id;
      const declaredWorkspace = body.match(/^\s*(?:Workspace|Work directory)\s*:\s*`?([^`\s]+)`?/im)?.[1]?.replace(/[\\/]+$/, "");
      const handoffs = [...body.matchAll(/^\s*Artifact\s*:\s*[-*]?\s*([^\s,]+)/gim)]
        .map((entry) => declaredArtifactPath(entry[1] ?? ""))
        .filter((entry): entry is string => Boolean(entry));
      const productFiles = [...body.matchAll(/^\s*(?:Files? Modified|File)\s*:\s*[-*]?\s*([^\s,]+)/gim)]
        .map((entry) => artifactPath(entry[1] ?? ""))
        .filter((entry): entry is string => Boolean(entry))
        ;
      const quoted = [...body.matchAll(/`([^`]+\.[A-Za-z0-9]+)`/g)]
        .map((entry) => artifactPath(entry[1] ?? ""))
        .filter((entry): entry is string => Boolean(entry && entry.includes("/")))
        ;
      return { id, body, title, workspace: declaredWorkspace, handoffs: [...new Set(handoffs)],
        files: [...new Set([...handoffs, ...productFiles, ...quoted])] };
    });
    const sharedFiles = assignments[0].files.filter((file) => assignments.slice(1).some((item) => item.files.includes(file)));
    const taskTag = `project:${project.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`
      + (runId ? `:run:${createHash("sha256").update(runId).digest("hex").slice(0, 10)}` : "");

    if (this.config.dependencyEnabled) {
      for (const assignment of assignments) {
        await this.upsert({
          id: `${taskTag}:assignment:${assignment.id}`, kind: "dependency", scope: "private",
          projectId: project, runId, artifactIds: assignment.files.map((artifact) =>
            assignment.workspace && !artifact.startsWith(`${assignment.workspace}/`)
              ? `${assignment.workspace}/${artifact}` : artifact),
          handoffArtifactIds: assignment.handoffs, subject: `assignment:${assignment.id}:handoff`,
          assignmentId: assignment.id, workDirectory: assignment.workspace,
          producerIds: [assignment.id], consumerIds: ["coordinator"],
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
        projectId: project, runId, artifactIds: sharedFiles,
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
          projectId: project, runId, artifactIds: sharedFiles,
          verificationSubject: `assignment:${assignment.id}:composition`,
          title: `${assignment.id} independent and composition verification`, targetRoles: [assignment.id], priority: 90,
          text: `Responsibility=${assignment.id}; Trigger=shared artifact or API modified by another assignment; Command=run baseline tests, ${assignment.id} feature tests, and a composition check combining both assignments; Pass evidence=exact commands and assertions showing own feature, partner defaults, and joint behavior; Failure action=revise only the conflicting boundary and rerun before handoff`,
          status: "required", evidence: [], tags: [taskTag, `assignment:${assignment.id}`, "composition", ...sharedFiles],
        });
      }
    }
    return true;
  }

  /** Promote completed peer handoffs into a producer/consumer contract. */
  async discoverCoDomainFromHandoffs(workspace: string, projectId: string,
                                     runId: string): Promise<MemoryItem | undefined> {
    if (!this.config.codomainEnabled) return undefined;
    const dependency = await this.load("dependency");
    const assignments = dependency.items
      .filter((item) => inContext(item, projectId, runId) && item.assignmentId
        && (item.handoffArtifactIds?.length || item.workDirectory))
      .filter((item, index, all) => all.findIndex((other) =>
        normalizeIdentity(other.assignmentId ?? "") === normalizeIdentity(item.assignmentId ?? "")) === index);
    if (assignments.length < 2) return undefined;

    const handoffs: Array<{ assignment: string; directory: string; content: string; files: string[] }> = [];
    for (const item of assignments) {
      const directory = item.workDirectory ?? ".";
      const candidates = [
        resolve(workspace, directory, "PATCH_READY.md"),
        ...(item.handoffArtifactIds ?? []).map((artifact) => resolve(workspace, artifact)),
        ...(item.artifactIds ?? []).filter((artifact) => /PATCH_READY\.md$/i.test(artifact))
          .map((artifact) => resolve(workspace, artifact)),
      ];
      let content = "";
      for (const path of [...new Set(candidates)]) {
        try { content = await readFile(path, "utf8"); } catch { /* keep looking */ }
        if (content.trim()) break;
      }
      if (!content.trim()) continue;
      const files = [...content.matchAll(/`([^`\n]+\.[A-Za-z0-9]+)`|(?:^|\n)\s*[-*]?\s*([\w./-]+\.[A-Za-z0-9]+)\s*\|/g)]
        .map((match) => artifactPath(match[1] ?? match[2] ?? ""))
        .filter((path): path is string => path !== undefined)
        .filter((path) => !/PATCH_READY\.md$/i.test(path)
          && !/(?:^|\/)(?:tests?\/|test_[^/]+\.py$|[^/]+_test\.[^/]+$|[^/]*selftest[^/]*$)/i.test(path));
      const normalizedFiles = files.map((path) => path.startsWith(`${directory}/`)
        ? path.slice(directory.length + 1) : path);
      const concreteFiles = normalizedFiles.filter((path) => path.includes("/")
        || !normalizedFiles.some((other) => other !== path && other.endsWith(`/${path}`)));
      handoffs.push({ assignment: item.assignmentId as string, directory,
        content: content.slice(0, 7000), files: [...new Set(concreteFiles)].slice(0, 30) });
    }
    if (handoffs.length < 2) return undefined;

    const rawArtifactIds = [...new Set(handoffs.flatMap((handoff) => handoff.files))];
    const structuredPythonLayout = rawArtifactIds.some((path) => path.startsWith("src/") && path.endsWith(".py"));
    const artifactIds = structuredPythonLayout
      ? rawArtifactIds.filter((path) => !(path.endsWith(".py") && !path.includes("/")))
      : rawArtifactIds;
    const participants = handoffs.map((handoff) => handoff.assignment);
    const interfaceId = `handoff-composition:${participants.map(normalizeIdentity).sort().join("+")}`;
    const id = `${projectId}:run:${createHash("sha256").update(runId).digest("hex").slice(0, 10)}:${interfaceId}`;
    const render = (handoff: typeof handoffs[number]) => {
      const boundary = handoff.content.replace(/^#.*$/m, "")
        .split(/\n##\s+(?:Evidence|Tests?|How to Apply|Verification)/i)[0].trim().slice(0, 4500);
      return `${handoff.assignment} producer contract (${handoff.directory}):\n${boundary}`;
    };
    const verificationCommands = [...new Set(handoffs.flatMap((handoff) =>
      [...handoff.content.matchAll(/\b(go\s+test|python\s+-m\s+pytest|pytest|npm\s+test|cargo\s+test)\b([^\n`]*)/gi)]
        .map((match) => `${match[1]}${match[2]}`.trim().replace(/[)\],;:]+$/, ""))
        .filter((command) => command.length > 3 && command.length < 500)))]
      .slice(0, 6);
    if (this.config.testingEnabled) {
      const testing = await this.load("testing");
      for (const handoff of handoffs) {
        const commands = [...new Set(
          [...handoff.content.matchAll(/\b(go\s+test|python\s+-m\s+pytest|pytest|npm\s+test|cargo\s+test)\b([^\n`]*)/gi)]
            .map((match) => `${match[1]}${match[2]}`.trim().replace(/[)\],;:]+$/, ""))
            .filter((command) => command.length > 3 && command.length < 500),
        )];
        for (const item of testing.items.filter((candidate) =>
          inContext(candidate, projectId, runId)
          && normalizedSet(candidate.targetRoles).some((role) => sameAssignmentRole(role, handoff.assignment)))) {
          await this.upsert({ ...item, verificationCommands: commands,
            text: `${item.text}; Required integration commands=${commands.join(" | ") || "derive producer boundary command"}` });
        }
      }
    }
    const text = [
      `Producer domain=${participants.join(", ")}; Consumer domain=coordinator/integrator`,
      `Shared data=${artifactIds.join(", ") || "public API signatures and runtime behavior declared in peer handoffs"}`,
      "Obligations=integrate every peer's exact public signature, defaults, validation, errors, and return behavior; preserve parameters and semantics introduced by every producer; do not choose one peer implementation wholesale when both touch the same boundary",
      "Invariant=each feature passes independently against the same integrated tree and their public API changes coexist without parameter loss, altered defaults, mock-call incompatibility, error-message drift, or overwritten behavior",
      `Boundary test=apply both peer changes to one clean integration tree; run each peer's stated feature/boundary tests independently; add a joint call when both affect one API; required integration commands=${verificationCommands.join(" | ") || "derive and run each peer's stated feature test"}; record exact commands and results before verification`,
      ...handoffs.map(render),
    ].join(";\n");
    const existing = (await this.load("codomain")).items.find((item) =>
      inContext(item, projectId, runId) && normalizeIdentity(item.interfaceId ?? "") === normalizeIdentity(interfaceId));
    return this.upsert({
      ...(existing ?? {}), id: existing?.id ?? id, kind: "codomain", scope: "shared",
      projectId, runId, interfaceId,
      artifactIds: artifactIds.length ? artifactIds
        : [...new Set(assignments.flatMap((item) => item.handoffArtifactIds ?? []))],
      producerIds: participants, consumerIds: ["coordinator", "integrator"],
      title: `Integration contract from ${participants.join(" + ")} handoffs`,
      targetRoles: [...participants, "coordinator", "integrator"], participants,
      priority: 110, version: existing?.version ?? 1, text,
      status: existing?.status === "verified" ? "verified" : "agreed",
      verificationCommands,
      evidence: assignments.flatMap((item) => (item.handoffArtifactIds ?? [])
        .map((artifact) => `${item.assignmentId}: ${artifact}`)),
      tags: [projectId, "dynamic-handoff", "composition", ...artifactIds.map((artifact) => basename(artifact))],
    });
  }

  async recordCoDomainVerification(workspace: string, input: {
    command: string; exitCode: number; source?: string; output?: string; error?: string;
    projectId?: string; runId?: string; coordinator?: boolean; coordinationRoot?: string;
  }): Promise<number> {
    if (!input.projectId || !input.runId || !input.command.trim()) return 0;
    const command = canonicalVerificationCommand(input.command, workspace);
    const reportedTestFailure = /(?:^|\n)(?:FAILED\s|=+\s*FAILURES\s*=+|\d+\s+failed\b)/im
      .test(input.output ?? "");
    const verificationRoot = commandWorkspace(input.command, workspace);
    const broadGoSuite = /\bgo test\b[^;&|\n]*\.\/\.\.\./i.test(command);
    const broadPytestSuite = /\bpytest\b[^;&|\n]*(?:tests(?:\/|\s|$)|\.\/tests)/i.test(command);
    const codomain = await this.load("codomain");
    let updated = 0;
    for (const item of codomain.items.filter((candidate) => inContext(candidate, input.projectId, input.runId))) {
      const required = item.verificationCommands ?? [];
      if (item.status === "verified") continue;
      const genericTest = /(?:^|&&|;)\s*(?:go\s+test|pytest(?!\s+--version)|python(?:3)?\s+(?:-m\s+pytest(?!\s+--version)|[^;&|\s]+\.py)|node\s+[^;&|\s]+|npm\s+test|cargo\s+test)\b/i.test(command);
      // Coordinator identity is not evidence of composition. Only commands
      // whose effective cwd is the dedicated merged tree may verify a
      // co-domain contract.
      const integrationTest = basename(verificationRoot) === "integration" && genericTest;
      const matches = required.filter((expected) => {
        const key = canonicalVerificationCommand(expected, workspace);
        return key && (command.includes(key) || key.includes(command)
          || (broadGoSuite && key.includes("go test"))
          || (broadPytestSuite && key.includes("pytest"))
          || (key.includes("pytest") && command.includes("pytest")
            && key.match(/pytest\s+([^\s]+)/)?.[1] === command.match(/pytest\s+([^\s]+)/)?.[1]));
      });
      if (!matches.length && !integrationTest) continue;
      const observations = await Promise.all((item.artifactIds ?? []).map((artifact) =>
        this.observeArtifact(verificationRoot, artifact, input.source ?? "after-tool-call")));
      const artifactVersions = Object.fromEntries(observations
        .filter((entry) => entry.exists && entry.sha256)
        .map((entry) => [entry.artifactId, entry.sha256 as string]));
      const artifactsPresent = observations.every((entry) => entry.exists && Boolean(entry.sha256));
      const coordinatorBoundaryPassed = Boolean(integrationTest
        && input.exitCode === 0 && !reportedTestFailure);
      const attempt: VerificationAttempt = {
        command: input.command, exitCode: input.exitCode,
        passed: input.exitCode === 0 && !reportedTestFailure
          && (artifactsPresent || coordinatorBoundaryPassed),
        artifactVersions, observedAt: new Date().toISOString(), source: input.source ?? "after-tool-call",
        output: input.output?.slice(0, 2000), error: input.error?.slice(0, 2000),
      };
      const attempts = [...(item.verificationAttempts ?? []), attempt].slice(-30);
      const passedKeys = new Set(attempts.filter((entry) => entry.passed).map((entry) =>
        canonicalVerificationCommand(entry.command, workspace)));
      const allPassed = (required.length === 0 && attempt.passed)
        || (coordinatorBoundaryPassed && attempt.passed)
        || (artifactsPresent && required.every((expected) => {
        const key = canonicalVerificationCommand(expected, workspace);
        return [...passedKeys].some((actual) => actual.includes(key) || key.includes(actual)
          || (/\bgo test\b[^;&|\n]*\.\/\.\.\./i.test(actual) && key.includes("go test"))
          || (/\bpytest\b[^;&|\n]*(?:tests(?:\/|\s|$)|\.\/tests)/i.test(actual) && key.includes("pytest"))
          || (key.includes("pytest") && actual.includes("pytest")
            && key.match(/pytest\s+([^\s]+)/)?.[1] === actual.match(/pytest\s+([^\s]+)/)?.[1]));
      }));
      await this.upsert({ ...item, verificationAttempts: attempts,
        status: allPassed ? "verified" : "agreed",
        evidence: [...(item.evidence ?? []),
          `integration verification command=${input.command}; exit=${input.exitCode}; matched=${matches.join(",")}`].slice(-30),
      });
      updated += 1;
    }
    return updated;
  }

  async integrationContext(projectId: string, runId: string): Promise<string> {
    const codomain = await this.load("codomain");
    const items = codomain.items.filter((item) => inContext(item, projectId, runId)
      && isCurrent(item) && isProductCodomain(item))
      .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
    if (!items.length) return "";
    return ["[Multi-Agent Memory — integration acceptance contracts]",
      ...items.map((item) => `- [${item.id}] state=${item.status}; version=${item.version ?? 1}\n${item.text}`),
      "Treat every producer handoff above as a simultaneous acceptance criterion. Integrate, run each producer's boundary tests against the same final tree, then call multiagent_contract_transition(action=verify, baseVersion=current version) with exact passing evidence. Do not finalize while a contract is merely agreed.",
    ].join("\n\n");
  }

  async observeWorkflow(workspace: string, nextRole?: string, projectId?: string,
                        runId?: string): Promise<void> {
    const dependency = await this.load("dependency");
    for (const item of dependency.items) {
      if (!inContext(item, projectId, runId)) continue;
      if (nextRole && !isRelevantToRole(item, nextRole)) continue;
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
        status: missing.length ? "unresolved" : changedAfterVerification ? "stale"
          : item.verificationCommand ? item.status : "produced",
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

  async recordVerification(workspace: string, input: {
    command: string; exitCode: number; source?: string; output?: string; error?: string;
    projectId?: string; runId?: string;
  }): Promise<number> {
    const command = input.command.trim();
    if (!command) return 0;
    const dependency = await this.load("dependency");
    let updated = 0;
    for (const item of dependency.items) {
      if (!inContext(item, input.projectId, input.runId)) continue;
      if (!item.verificationCommand
        || !verificationCommandsMatch(item.verificationCommand, command, workspace)) continue;
      const artifacts = item.artifactIds ?? [];
      if (!artifacts.length) continue;
      const observations = await Promise.all(artifacts.map((artifact) =>
        this.observeArtifact(workspace, artifact, input.source ?? "after-tool-call")));
      const artifactVersions = Object.fromEntries(observations
        .filter((entry) => entry.exists && entry.sha256)
        .map((entry) => [entry.artifactId, entry.sha256 as string]));
      const exitMarkers = [...(input.output ?? "").matchAll(
        /\b(?:EXIT|EXIT_STATUS|SELFTEST_EXIT|PRIMARY_EXIT_STATUS|CLI_EXIT|test\s+exit|demo\s+exit)\s*[:=]\s*(\d+)\b/gi,
      )].map((match) => Number(match[1]));
      const passed = input.exitCode === 0 && exitMarkers.every((code) => code === 0)
        && observations.every((entry) => entry.exists && Boolean(entry.sha256));
      const attempt: VerificationAttempt = {
        command,
        exitCode: input.exitCode,
        passed,
        artifactVersions,
        observedAt: new Date().toISOString(),
        source: input.source ?? "after-tool-call",
        output: input.output?.slice(0, 2000),
        error: input.error?.slice(0, 2000),
      };
      await this.upsert({
        ...item,
        lifecycleState: passed ? "verified" : "blocked",
        status: passed ? "verified" : "unresolved",
        artifactObservations: observations,
        verificationAttempts: [...(item.verificationAttempts ?? []), attempt].slice(-20),
        evidence: [...(item.evidence ?? []),
          `command=${command}; exit=${input.exitCode}; artifacts=${JSON.stringify(artifactVersions)}; passed=${passed}`].slice(-20),
      });
      updated += 1;
    }
    return updated;
  }

  async recordTestingVerification(workspace: string, input: {
    command: string; exitCode: number; source?: string; output?: string; error?: string;
    projectId?: string; runId?: string; coordinator?: boolean; coordinationRoot?: string;
  }): Promise<number> {
    const verificationRoot = commandWorkspace(input.command, workspace);
    if (!this.config.testingEnabled || !input.projectId || !input.runId
      || basename(verificationRoot) !== "integration"
      || !/(?:^|&&|;)\s*(?:go\s+test|pytest(?!\s+--version)|python(?:3)?\s+(?:-m\s+pytest(?!\s+--version)|[^;&|\s]+\.py)|node\s+[^;&|\s]+|npm\s+test|cargo\s+test)\b/i.test(input.command)) return 0;
    const testing = await this.load("testing");
    let updated = 0;
    for (const item of testing.items.filter((candidate) => inContext(candidate, input.projectId, input.runId)
      && candidate.tags?.includes("composition") && candidate.status !== "verified")) {
      const observations = await Promise.all((item.artifactIds ?? []).map((artifact) =>
        this.observeArtifact(verificationRoot, artifact, input.source ?? "after-tool-call")));
      const artifactVersions = Object.fromEntries(observations
        .filter((entry) => entry.exists && entry.sha256)
        .map((entry) => [entry.artifactId, entry.sha256 as string]));
      const reportedTestFailure = /(?:^|\n)(?:FAILED\s|=+\s*FAILURES\s*=+|\d+\s+failed\b)/im
        .test(input.output ?? "");
      const required = item.verificationCommands ?? [];
      const canonical = canonicalVerificationCommand(input.command, workspace);
      const matched = required.length === 0 || required.some((expected) => {
        const key = canonicalVerificationCommand(expected, workspace);
        return key && (canonical.includes(key) || key.includes(canonical));
      });
      const passed = matched && input.exitCode === 0 && !reportedTestFailure;
      const attempt: VerificationAttempt = {
        command: input.command, exitCode: input.exitCode, passed, artifactVersions,
        observedAt: new Date().toISOString(), source: input.source ?? "after-tool-call",
        output: input.output?.slice(0, 2000), error: input.error?.slice(0, 2000),
      };
      await this.upsert({ ...item, status: passed ? "verified" : "required",
        verificationAttempts: [...(item.verificationAttempts ?? []), attempt].slice(-20),
        evidence: [...(item.evidence ?? []),
          `integration verification command=${input.command}; exit=${input.exitCode}; passed=${passed}`].slice(-20),
      });
      updated += 1;
    }
    return updated;
  }

  async readinessBlockers(consumerId?: string, projectId?: string, runId?: string): Promise<MemoryItem[]> {
    if (!consumerId) return [];
    const consumer = normalizeIdentity(consumerId);
    const dependency = await this.load("dependency");
    return dependency.items.filter((item) => inContext(item, projectId, runId))
      .filter((item) => !projectId || !runId || Boolean(item.projectId && item.runId))
      .filter((item) => normalizedSet(item.consumerIds).some((id) => sameAssignmentRole(id, consumer)))
      // The consumer/reviewer supplies verification. Requiring verification
      // before admitting that consumer makes the handoff circular.
      .filter((item) => !["produced", "verified", "ready"].includes(item.lifecycleState ?? ""));
  }

  async producerBlockers(producerId?: string, projectId?: string, runId?: string): Promise<MemoryItem[]> {
    if (!producerId) return [];
    const producer = normalizeIdentity(producerId);
    const dependency = await this.load("dependency");
    return dependency.items.filter((item) => inContext(item, projectId, runId))
      .filter((item) => !projectId || !runId || Boolean(item.projectId && item.runId))
      .filter((item) => normalizedSet(item.producerIds).some((id) => sameAssignmentRole(id, producer)))
      .filter((item) => !["produced", "verified", "ready"].includes(item.lifecycleState ?? ""));
  }

  async recoveryAdmission(assignmentId: string, projectId: string, runId: string): Promise<{
    obligations: MemoryItem[]; allowed: boolean; reason?: string;
  }> {
    const assignment = normalizeIdentity(assignmentId);
    const dependency = await this.load("dependency");
    const obligations = dependency.items.filter((item) => inContext(item, projectId, runId))
      .filter((item) => sameAssignmentRole(item.recoveryOwnerId ?? "", assignment))
      .filter((item) => item.lifecycleState === "blocked");
    const exhausted = obligations.filter((item) =>
      (item.lifecycleOutcomes ?? []).filter((outcome) => outcome.outcome !== "ok").length
        >= this.config.maxRecoveryAttempts);
    return {
      obligations,
      allowed: exhausted.length === 0,
      reason: exhausted.length
        ? `recovery budget exhausted for ${exhausted.map((item) => item.id).join(", ")}`
        : undefined,
    };
  }

  async recordLifecycleOutcome(input: {
    selectedIds: string[]; assignment?: string; outcome: string; error?: string;
  }): Promise<void> {
    if (["ok", "completed", "complete", "success", "succeeded"].includes(input.outcome.trim().toLowerCase())) return;
    const dependency = await this.load("dependency");
    for (const item of dependency.items.filter((candidate) => input.selectedIds.includes(candidate.id))) {
      const outcome: LifecycleOutcome = {
        assignment: input.assignment,
        outcome: input.outcome,
        observedAt: new Date().toISOString(),
        error: input.error?.slice(0, 2000),
      };
      await this.upsert({
        ...item,
        lifecycleState: "blocked",
        status: "unresolved",
        recoveryOwnerId: input.assignment ?? item.producerIds?.[0],
        lifecycleOutcomes: [...(item.lifecycleOutcomes ?? []), outcome].slice(-20),
        evidence: [...(item.evidence ?? []),
          `agent outcome=${input.outcome}; assignment=${input.assignment ?? "unknown"}; error=${input.error ?? "none"}`].slice(-20),
      });
    }
  }

  async registerAssignment(input: {
    projectId: string; runId: string; assignmentId: string; task: string; workspace?: string;
  }): Promise<MemoryItem[]> {
    const assignment = input.assignmentId.trim();
    if (!assignment) return [];
    const escaped = escapePattern(assignment);
    const focused = input.task.match(new RegExp(
      `(?:taskName/label|taskName|label|assignment|you\\s+are)\\s*[:=]?\\s*['"]?${escaped}['"]?[\\s\\S]{0,1800}`,
      "i"))?.[0] ?? input.task;
    const workDirFrom = (value: string) => value.match(/work(?:ing)?\s+only\s+(?:in|inside)\s+(?:the\s+)?workspace\s+directory\s*:?\s*`?([^`\s(\n]+)/i)?.[1]
      ?? value.match(/work only in\s+`([^`]+)`/i)?.[1]
      ?? value.match(/work(?:ing)?\s+only\s+in\s+the\s+workspace\s+directory\s+`([^`]+)`/i)?.[1]
      ?? value.match(/working\s+only\s+in(?:\s+the)?(?:\s+workspace)?\s+directory\s*[:=]\s*`?([^`\n]+)`?/i)?.[1]
      ?? value.match(/working directory\s*[:=]\s*`?([^`\n]+)`?/i)?.[1]
      ?? value.match(/(?:your\s+)?workspace\s+is\s+`?([^`\s]+)`?/i)?.[1]
      ?? value.match(/\bWorkspace\s*:\s*`?([^`\n]+)`?/i)?.[1];
    const rawWorkDir = workDirFrom(focused) ?? workDirFrom(input.task);
    let workDirectory = rawWorkDir?.trim().replace(/[\\/]+$/, "").replace(/^\.\//, "");
    if (workDirectory && /^(?:a|an|the|this|that)$/i.test(workDirectory)) workDirectory = undefined;
    if (workDirectory && /\s/.test(workDirectory)) workDirectory = undefined;
    if (workDirectory && isAbsolute(workDirectory) && input.workspace) {
      const rel = relative(resolve(input.workspace), resolve(workDirectory));
      workDirectory = rel.startsWith("..") || isAbsolute(rel) ? undefined : rel;
    }
    if (workDirectory?.split(/[\\/]/).includes("..")) workDirectory = undefined;

    const dependency = await this.load("dependency");
    const records = dependency.items.filter((item) => inContext(item, input.projectId, input.runId))
      .filter((item) => normalizedSet(item.producerIds).some((id) => sameAssignmentRole(id, assignment)));
    const updated: MemoryItem[] = [];
    for (const item of records) {
      const declaredReady = item.handoffArtifactIds?.[0]
        ?? (item.artifactIds ?? []).find((artifact) => /PATCH_READY\.md$/i.test(artifact));
      const declaredDirectory = declaredReady ? dirname(declaredReady) : undefined;
      const effectiveWorkDirectory = workDirectory ?? (declaredDirectory && declaredDirectory !== "."
        ? declaredDirectory : undefined);
      const artifacts = (item.artifactIds ?? []).map((artifact) =>
        effectiveWorkDirectory && !artifact.startsWith(effectiveWorkDirectory + "/")
          && (Boolean(workDirectory) || !artifact.includes("/"))
          ? `${effectiveWorkDirectory}/${artifact}` : artifact);
      const readyArtifact = focused.match(/write\s+`?([^`\s]*PATCH_READY\.md)`?/i)?.[1];
      let relativeReadyArtifact = readyArtifact;
      if (relativeReadyArtifact && isAbsolute(relativeReadyArtifact) && input.workspace) {
        const rel = relative(resolve(input.workspace), resolve(relativeReadyArtifact));
        relativeReadyArtifact = rel.startsWith("..") || isAbsolute(rel) ? undefined : rel;
      }
      const normalizedReadyArtifact = relativeReadyArtifact && effectiveWorkDirectory
        && !relativeReadyArtifact.startsWith(`${effectiveWorkDirectory}/`)
        ? `${effectiveWorkDirectory}/${relativeReadyArtifact}` : relativeReadyArtifact;
      if (normalizedReadyArtifact && !artifacts.includes(normalizedReadyArtifact)) {
        artifacts.push(normalizedReadyArtifact);
      }
      updated.push(await this.upsert({
        ...item,
        assignmentId: assignment,
        workDirectory: effectiveWorkDirectory,
        handoffArtifactIds: item.handoffArtifactIds,
        artifactIds: artifacts,
        // Preserve downstream consumers already attached to a prerequisite.
        // Replacing targetRoles with only the producer prevents the observer
        // from refreshing that record when the consumer is about to spawn.
        targetRoles: [...new Set([...(item.targetRoles ?? []), assignment])],
      }));
    }
    return updated;
  }

  async completionBlockers(projectId: string, runId: string): Promise<MemoryItem[]> {
    const dependency = await this.load("dependency");
    const artifactBlockers = dependency.items.filter((item) => inContext(item, projectId, runId))
      .filter((item) => Boolean(item.projectId && item.runId))
      // Terminal artifacts must exist, and every configured verification must
      // be current even when its immediate consumer was the reviewer.
      .filter((item) => Boolean(item.verificationCommand)
        || (item.consumerIds ?? []).some((consumer) =>
          ["completion", "coordinator"].includes(roleIdentity(consumer))))
      .filter((item) => item.verificationCommand
        ? item.lifecycleState !== "verified" && item.lifecycleState !== "ready"
        : !["produced", "verified", "ready"].includes(item.lifecycleState ?? ""));
    const codomain = await this.load("codomain");
    const contractBlockers = codomain.items.filter((item) => inContext(item, projectId, runId))
      .filter((item) => item.status !== "verified");
    const testing = await this.load("testing");
    const testingBlockers = testing.items.filter((item) => inContext(item, projectId, runId)
      && item.tags?.includes("composition") && item.status !== "verified");
    return [...artifactBlockers, ...contractBlockers, ...testingBlockers];
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

  async buildSpawnPacket(task: string, parentSessionKey?: string, assignment?: string,
                         projectId?: string, runId?: string): Promise<{
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
      const items = await this.retrieve(kind, task, parentSessionKey, role, projectId, runId);
      selected[kind] = items.map((item) => item.id);
      if (!items.length) continue;
      sections.push([heading, ...items.map((item) => {
        const control = item.kind === "dependency"
          ? ` [state=${item.lifecycleState ?? item.status ?? "unknown"}; recovery_owner=${item.recoveryOwnerId ?? "none"}; latest_evidence=${item.evidence?.at(-1) ?? "none"}]`
          : "";
        return `- [${item.id}] ${item.title}${control}: ${item.text}`;
      })].join("\n"));
    }
    if (!sections.length) return { packet: "", selected, role };
    const recoveryItems = (await this.load("dependency")).items
      .filter((item) => selected.dependency.includes(item.id) && item.recoveryOwnerId
        && sameAssignmentRole(item.recoveryOwnerId, role ?? "")
        && item.lifecycleState === "blocked");
    const recoveryDirective = recoveryItems.length ? [
      "BOUNDED RECOVERY OBLIGATION",
      ...recoveryItems.map((item) => {
        const attempts = (item.lifecycleOutcomes ?? []).filter((outcome) => outcome.outcome !== "ok").length;
        return `- ${item.id}: attempt ${attempts + 1}/${this.config.maxRecoveryAttempts}; latest failure=${item.evidence?.at(-1) ?? "unknown"}`;
      }),
      "Do not repeat the failed approach. First persist a checkpoint, state one materially changed strategy grounded in the failure evidence, apply the smallest repair, and rerun the exact configured verification command.",
    ].join("\n") : "";
    return {
      selected,
      role,
      packet: [
        "\n\n--- MULTI-AGENT MEMORY CONTEXT (plugin-injected) ---",
        ...sections,
        recoveryDirective,
        selected.dependency.length ? [
          "DURABLE OUTPUT PROTOCOL",
          "- A prose plan or acknowledgment is not progress on an artifact obligation.",
          "- After necessary reads, the first production action must be a write/edit/apply-patch tool call.",
          "- For a large artifact, write a small valid checkpoint first and extend it through bounded edits. Never generate the whole artifact in one response; an output-limit stop would discard it before a file exists.",
          "- Inspect the durable files and run the configured evidence command before reporting completion.",
        ].join("\n") : "",
        `Target role: ${role ?? "unclassified"}. Only records relevant to this role/boundary were selected.`,
        "Use these records as current working context. Dependency readiness is observer-owned: never update it through a memory or contract tool. Co-domain records describe product/API semantics, not Agent handoffs; use multiagent_contract_transition only for a lifecycle change to an explicitly selected co-domain record. Testing records define evidence standards.",
        "--- END MULTI-AGENT MEMORY CONTEXT ---",
      ].join("\n\n"),
    };
  }

  async inspect(query: string, sessionKey?: string, projectId?: string,
                runId?: string): Promise<Record<MemoryKind, MemoryItem[]>> {
    return {
      dependency: await this.retrieve("dependency", query, sessionKey, undefined, projectId, runId),
      codomain: await this.retrieve("codomain", query, sessionKey, undefined, projectId, runId),
      testing: await this.retrieve("testing", query, sessionKey, undefined, projectId, runId),
    };
  }
}
