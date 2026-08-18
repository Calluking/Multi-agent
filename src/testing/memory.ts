import type { TestingEventStore } from "./store.js";
import type { CompletionDecision, PracticeQuery, TestingEvent, TestingPractice, VerificationRecord } from "./types.js";

const clone = <T>(value: T): T => structuredClone(value);
export class TestingPracticeMemory {
  private readonly records = new Map<string, VerificationRecord>();
  private readonly seen = new Set<string>();
  constructor(readonly runId: string, private readonly store: TestingEventStore, readonly practices: TestingPractice[]) {}
  static async open(runId: string, store: TestingEventStore, practices: TestingPractice[] = []) { const m = new TestingPracticeMemory(runId, store, practices); for (const e of await store.load(runId)) m.reduce(e); return m; }
  search(query: PracticeQuery): TestingPractice[] {
    const match = (wanted: string | undefined, values: string[]) => !wanted || values.includes(wanted);
    return this.practices.filter((p) => p.state === "active" && match(query.artifactType, p.applicability.artifactTypes) && match(query.action, p.applicability.actions) && match(query.risk, p.applicability.risks) && match(query.surface, p.applicability.surfaces))
      .sort((a, b) => (b.confidence - b.cost * .05) - (a.confidence - a.cost * .05) || a.practiceId.localeCompare(b.practiceId)).slice(0, Math.min(query.limit ?? 2, 2)).map(clone);
  }
  async record(event: TestingEvent) { if (event.runId !== this.runId) throw new Error("event belongs to another run"); if (this.seen.has(event.eventId)) return; this.validate(event); await this.store.append(event); this.reduce(event); }
  get(id: string) { const r = this.records.get(id); return r ? clone(r) : undefined; }
  list() { return [...this.records.values()].map(clone); }
  projectForOwner(ownerId: string) {
    return this.list().filter((r) => r.definition.ownerId === ownerId).map((r) => ({
      verificationId: r.definition.verificationId,
      state: r.state,
      source: r.definition.source,
      artifacts: r.definition.artifacts,
      command: r.definition.command,
      requiredAssertions: r.definition.requiredAssertions,
      practices: r.definition.practiceRefs.map((id) => this.practices.find((p) => p.practiceId === id)).filter(Boolean).map(clone),
      latestFailure: r.evidence.filter((e) => e.exitCode !== 0).at(-1),
      repair: r.repairs.at(-1),
    }));
  }
  completionDecision(): CompletionDecision { const unresolved = this.list().filter((r) => r.definition.source.authoritative && !["passed", "waived"].includes(r.state)).map((r) => r.definition.verificationId); return { decision: unresolved.length ? "block" : "allow", reasons: unresolved.map((id) => `${id} is not currently passed or waived`), unresolved }; }
  private validate(event: TestingEvent) {
    if (event.type === "verification.declared") { const d = event.definition; if (d.runId !== this.runId || !d.verificationId || !d.ownerId || !d.command.trim() || d.artifacts.length === 0) throw new Error("invalid verification declaration"); if (this.records.has(d.verificationId)) throw new Error("verification already declared"); for (const p of d.practiceRefs) if (!this.practices.some((x) => x.practiceId === p && x.state === "active")) throw new Error(`unknown active practice: ${p}`); if (d.source.authoritative) { for (const earlier of this.records.values()) { if (!earlier.definition.source.authoritative || earlier.definition.ownerId !== d.ownerId || !earlier.definition.artifacts.some((a) => d.artifacts.includes(a))) continue; const assertionsPreserved = earlier.definition.requiredAssertions.every((a) => d.requiredAssertions.includes(a)); if (d.command !== earlier.definition.command || !assertionsPreserved) throw new Error("duplicate authoritative declaration may not weaken an earlier criterion"); } } return; }
    const r = this.records.get(event.verificationId); if (!r) throw new Error("unknown verification");
    if (event.type === "artifact.observed" && !r.definition.artifacts.includes(event.artifactId)) throw new Error("artifact is not covered");
    if (event.type === "verification.started" && event.command !== r.definition.command) throw new Error("original acceptance command must be rerun exactly");
    if (event.type === "verification.observed") { const e = event.evidence; if (e.command !== r.definition.command) throw new Error("evidence command differs from obligation"); if (!e.startedAt || !e.endedAt || !e.stdoutRef || !e.stderrRef) throw new Error("execution evidence is incomplete"); for (const a of r.definition.artifacts) if (!r.artifactVersions[a] || e.artifactVersions[a] !== r.artifactVersions[a]) throw new Error(`evidence lacks current artifact: ${a}`); if (e.exitCode === 0) for (const assertion of r.definition.requiredAssertions) if (!e.assertionsObserved.includes(assertion)) throw new Error(`required assertion was not observed: ${assertion}`); if (r.definition.boundary && !e.realPath) throw new Error("disconnected mock cannot verify a boundary"); }
    if (event.type === "repair.assigned") { if (!r.evidence.length || r.evidence.at(-1)?.exitCode === 0) throw new Error("repair requires failed evidence"); if (event.repair.attempt !== r.repairs.length + 1 || event.repair.attempt > r.definition.maxRetries) throw new Error("repair retry is invalid or exhausted"); if (!event.repair.strategy.trim() || r.repairs.some((x) => x.strategy === event.repair.strategy)) throw new Error("repair requires a materially changed strategy"); }
    if (event.type === "verification.waived" && (!event.authority.trim() || !event.reason.trim())) throw new Error("waiver requires explicit authority and reason");
  }
  private reduce(event: TestingEvent) { if (this.seen.has(event.eventId)) return; this.seen.add(event.eventId); if (event.type === "verification.declared") { this.records.set(event.definition.verificationId, { definition: clone(event.definition), state: "pending", artifactVersions: {}, evidence: [], repairs: [] }); return; } const r = this.records.get(event.verificationId)!; switch (event.type) {
    case "artifact.observed": { const before = r.artifactVersions[event.artifactId]; r.artifactVersions[event.artifactId] = event.version; if (r.state === "passed" && before !== event.version) r.state = "stale"; break; }
    case "verification.started": r.state = "running"; break;
    case "verification.observed": r.evidence.push(clone(event.evidence)); r.state = event.evidence.exitCode === 0 ? "passed" : "failed"; break;
    case "repair.assigned": r.repairs.push(clone(event.repair)); r.state = "repair_pending"; break;
    case "verification.waived": r.waiver = { authority: event.authority, reason: event.reason }; r.state = "waived"; break;
  }}
}
