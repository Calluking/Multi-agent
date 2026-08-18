import type {
  Blocker,
  DependencyEdge,
  DependencyEvent,
  DependencyRequirement,
  ObligationRecord,
  ObligationStatus,
  OwnerProjection,
  SpawnDecision,
} from "./types.js";
import type { DependencyEventStore } from "./store.js";

function cloneRecord(record: ObligationRecord): ObligationRecord {
  return structuredClone(record);
}

export class DependencyMemory {
  private readonly obligations = new Map<string, ObligationRecord>();
  private readonly edges = new Map<string, DependencyEdge>();
  private readonly seenEvents = new Set<string>();

  constructor(
    readonly runId: string,
    private readonly store: DependencyEventStore,
  ) {}

  static async open(runId: string, store: DependencyEventStore): Promise<DependencyMemory> {
    const memory = new DependencyMemory(runId, store);
    for (const event of await store.load(runId)) memory.reduce(event);
    return memory;
  }

  async record(event: DependencyEvent): Promise<void> {
    if (event.runId !== this.runId) throw new Error(`event ${event.eventId} belongs to another run`);
    if (this.seenEvents.has(event.eventId)) return;
    this.validate(event);
    await this.store.append(event);
    this.reduce(event);
  }

  get(obligationId: string): ObligationRecord | undefined {
    const record = this.obligations.get(obligationId);
    return record ? cloneRecord(record) : undefined;
  }

  list(): ObligationRecord[] {
    return [...this.obligations.values()].map(cloneRecord);
  }

  listEdges(): DependencyEdge[] {
    return [...this.edges.values()].map((edge) => structuredClone(edge));
  }

  blockers(obligationId: string): Blocker[] {
    this.requireObligation(obligationId);
    const result: Blocker[] = [];
    for (const edge of this.edges.values()) {
      if (edge.downstreamId !== obligationId) continue;
      const upstream = this.requireObligation(edge.upstreamId);
      if (this.requirementSatisfied(upstream, edge.requirement)) continue;
      const blocker: Blocker = {
        edgeId: edge.edgeId,
        upstreamId: edge.upstreamId,
        requiredState: edge.requirement,
        observedState: this.deriveStatus(upstream),
      };
      const recoveryOwner = upstream.recovery?.ownerId ?? upstream.ownerId;
      if (recoveryOwner) blocker.recoveryOwner = recoveryOwner;
      result.push(blocker);
    }
    return result;
  }

  spawnDecision(obligationId: string): SpawnDecision {
    const record = this.requireObligation(obligationId);
    const blockers = this.blockers(obligationId);
    if (record.active || record.completed || record.status === "cancelled") {
      return {
        decision: "wait",
        obligationId,
        blockers,
      };
    }
    return blockers.length === 0
      ? { decision: "allow", obligationId }
      : { decision: "wait", obligationId, blockers };
  }

  readySet(): string[] {
    return [...this.obligations.values()]
      .filter((record) => !record.active && !record.completed && record.status !== "cancelled")
      .filter((record) => this.blockers(record.obligationId).length === 0)
      .map((record) => record.obligationId)
      .sort();
  }

  completionSatisfied(obligationId: string): boolean {
    const record = this.requireObligation(obligationId);
    return this.outputsProduced(record) && this.verificationsCurrent(record);
  }

  projectForOwner(ownerId: string): OwnerProjection[] {
    return [...this.obligations.values()]
      .filter((record) => record.ownerId === ownerId || record.recovery?.ownerId === ownerId)
      .map((record) => {
        const projection: OwnerProjection = {
          obligationId: record.obligationId,
          ownerId,
          title: record.title,
          status: this.deriveStatus(record),
          requiredOutputs: structuredClone(record.requiredOutputs),
          requiredVerifications: structuredClone(record.requiredVerifications),
          blockers: this.blockers(record.obligationId),
        };
        if (record.recovery) projection.recovery = structuredClone(record.recovery);
        return projection;
      });
  }

  private validate(event: DependencyEvent): void {
    if (event.type === "obligation.declared") {
      if (event.obligation.runId !== this.runId) throw new Error("obligation run mismatch");
      if (this.obligations.has(event.obligation.obligationId)) throw new Error("obligation already declared");
      return;
    }
    if (event.type === "dependency.declared") {
      if (event.edge.runId !== this.runId) throw new Error("edge run mismatch");
      if (this.edges.has(event.edge.edgeId)) throw new Error("edge already declared");
      this.requireObligation(event.edge.upstreamId);
      this.requireObligation(event.edge.downstreamId);
      if (event.edge.requirement === "requires_verified") {
        const upstream = this.requireObligation(event.edge.upstreamId);
        if (upstream.requiredVerifications.length === 0) {
          throw new Error(`verified dependency ${event.edge.edgeId} has no declared verification`);
        }
      }
      if (event.edge.upstreamId === event.edge.downstreamId) throw new Error("self dependency is invalid");
      if (this.wouldCreateCycle(event.edge)) throw new Error("dependency graph contains a cycle");
      return;
    }
    const obligation = this.requireObligation(event.obligationId);
    if (event.type === "owner.started") {
      if (event.ownerId !== obligation.ownerId && event.ownerId !== obligation.recovery?.ownerId) {
        throw new Error(`owner ${event.ownerId} does not own ${event.obligationId}`);
      }
      const decision = this.spawnDecision(event.obligationId);
      if (decision.decision === "wait") throw new Error(`obligation ${event.obligationId} is not spawn-ready`);
    }
    if (event.type === "artifact.observed" && event.exists && !event.version) {
      throw new Error("existing artifact requires a version");
    }
    if (event.type === "artifact.observed" && !obligation.requiredOutputs.some((item) => item.artifactId === event.artifactId)) {
      throw new Error(`artifact ${event.artifactId} is not a declared output of ${event.obligationId}`);
    }
    if (event.type === "obligation.completed" && !this.completionSatisfied(event.obligationId)) {
      throw new Error(`obligation ${event.obligationId} lacks current completion evidence`);
    }
  }

  private reduce(event: DependencyEvent): void {
    if (this.seenEvents.has(event.eventId)) return;
    this.seenEvents.add(event.eventId);

    if (event.type === "obligation.declared") {
      this.obligations.set(event.obligation.obligationId, {
        ...structuredClone(event.obligation),
        status: "accepted",
        artifacts: {},
        verifications: {},
        active: false,
        completed: false,
        accepted: true,
      });
      this.refreshStatuses();
      return;
    }
    if (event.type === "dependency.declared") {
      this.edges.set(event.edge.edgeId, structuredClone(event.edge));
      this.assertAcyclic();
      this.refreshStatuses();
      return;
    }

    const record = this.requireObligation(event.obligationId);
    switch (event.type) {
      case "owner.started":
        record.active = true;
        delete record.failure;
        break;
      case "artifact.observed": {
        const previous = record.artifacts[event.artifactId];
        if (!event.exists) {
          delete record.artifacts[event.artifactId];
          record.completed = false;
          record.failure = `required artifact missing: ${event.artifactId}`;
          this.invalidateCoveredVerification(record, event.artifactId);
        } else {
          record.artifacts[event.artifactId] = {
            artifactId: event.artifactId,
            version: event.version as string,
            observedAt: event.observedAt,
            eventId: event.eventId,
          };
          if (previous && previous.version !== event.version) {
            record.completed = false;
            this.invalidateCoveredVerification(record, event.artifactId);
          }
        }
        break;
      }
      case "verification.observed":
        record.verifications[event.verificationId] = {
          verificationId: event.verificationId,
          command: event.command,
          success: event.success,
          artifactVersions: structuredClone(event.artifactVersions),
          observedAt: event.observedAt,
          eventId: event.eventId,
        };
        if (!event.success) {
          record.completed = false;
          record.failure = `verification failed: ${event.verificationId}`;
        }
        break;
      case "owner.ended":
        record.active = false;
        if (event.outcome !== "ok") {
          record.failure = `owner ended: ${event.outcome}`;
        } else if (!this.completionSatisfied(record.obligationId)) {
          record.failure = "owner ended without satisfying its obligation";
        }
        break;
      case "obligation.completed":
        record.completed = true;
        record.active = false;
        delete record.failure;
        break;
      case "obligation.cancelled":
        record.completed = false;
        record.active = false;
        record.status = "cancelled";
        record.failure = event.reason;
        break;
      case "recovery.assigned":
        record.recovery = {
          ownerId: event.ownerId,
          retryCount: (record.recovery?.retryCount ?? 0) + 1,
          strategy: event.strategy,
          evidenceRef: event.evidenceRef,
        };
        record.ownerId = event.ownerId;
        record.active = false;
        delete record.failure;
        break;
    }
    this.refreshStatuses();
  }

  private refreshStatuses(): void {
    for (const record of this.obligations.values()) {
      if (record.status === "cancelled") continue;
      record.status = this.deriveStatus(record);
    }
  }

  private deriveStatus(record: ObligationRecord): ObligationStatus {
    if (record.status === "cancelled") return "cancelled";
    if (record.completed) return "complete";
    if (record.active) return "in_progress";
    if (record.failure) {
      if (record.failure.startsWith("owner ended: error")) return "failed";
      if (record.failure.startsWith("owner ended") || record.failure.includes("without satisfying")) return "orphaned";
      return "blocked";
    }
    const hasStaleVerification = record.requiredVerifications.some((requirement) => {
      const evidence = record.verifications[requirement.verificationId];
      return Boolean(evidence?.success) && !this.verificationMatchesCurrent(record, requirement.verificationId);
    });
    if (hasStaleVerification) return "stale";
    if (this.verificationsCurrent(record) && record.requiredVerifications.length > 0) return "verified";
    if (this.outputsProduced(record) && record.requiredOutputs.length > 0) return "produced";
    if (this.blockersWithoutRecursion(record.obligationId).length === 0) return "ready";
    return "accepted";
  }

  private blockersWithoutRecursion(obligationId: string): DependencyEdge[] {
    const blockers: DependencyEdge[] = [];
    for (const edge of this.edges.values()) {
      if (edge.downstreamId !== obligationId) continue;
      const upstream = this.requireObligation(edge.upstreamId);
      if (!this.requirementSatisfied(upstream, edge.requirement)) blockers.push(edge);
    }
    return blockers;
  }

  private requirementSatisfied(record: ObligationRecord, requirement: DependencyRequirement): boolean {
    switch (requirement) {
      case "requires_accepted": return record.accepted;
      case "requires_produced": return this.outputsProduced(record);
      case "requires_verified": return record.requiredVerifications.length > 0 && this.verificationsCurrent(record);
      case "requires_complete": return record.completed && this.completionSatisfied(record.obligationId);
    }
  }

  private outputsProduced(record: ObligationRecord): boolean {
    return record.requiredOutputs.every((requirement) => Boolean(record.artifacts[requirement.artifactId]));
  }

  private verificationsCurrent(record: ObligationRecord): boolean {
    return record.requiredVerifications.every((requirement) => {
      const evidence = record.verifications[requirement.verificationId];
      if (!evidence || !evidence.success || evidence.command !== requirement.command) return false;
      return requirement.covers.every((artifactId) => {
        const artifact = record.artifacts[artifactId];
        return artifact !== undefined && evidence.artifactVersions[artifactId] === artifact.version;
      });
    });
  }

  private verificationMatchesCurrent(record: ObligationRecord, verificationId: string): boolean {
    const requirement = record.requiredVerifications.find((item) => item.verificationId === verificationId);
    if (!requirement) return false;
    const evidence = record.verifications[verificationId];
    if (!evidence || !evidence.success || evidence.command !== requirement.command) return false;
    return requirement.covers.every((artifactId) => evidence.artifactVersions[artifactId] === record.artifacts[artifactId]?.version);
  }

  private invalidateCoveredVerification(_record: ObligationRecord, _artifactId: string): void {
    // Evidence is immutable history. Keeping it lets deriveStatus distinguish
    // stale evidence from evidence that was never produced.
  }

  private requireObligation(obligationId: string): ObligationRecord {
    const record = this.obligations.get(obligationId);
    if (!record) throw new Error(`unknown obligation: ${obligationId}`);
    return record;
  }

  private assertAcyclic(): void {
    const adjacency = new Map<string, string[]>();
    for (const edge of this.edges.values()) {
      const next = adjacency.get(edge.upstreamId) ?? [];
      next.push(edge.downstreamId);
      adjacency.set(edge.upstreamId, next);
    }
    const visiting = new Set<string>();
    const visited = new Set<string>();
    const visit = (id: string) => {
      if (visiting.has(id)) throw new Error("dependency graph contains a cycle");
      if (visited.has(id)) return;
      visiting.add(id);
      for (const next of adjacency.get(id) ?? []) visit(next);
      visiting.delete(id);
      visited.add(id);
    };
    for (const id of this.obligations.keys()) visit(id);
  }

  private wouldCreateCycle(candidate: DependencyEdge): boolean {
    const adjacency = new Map<string, string[]>();
    for (const edge of [...this.edges.values(), candidate]) {
      const next = adjacency.get(edge.upstreamId) ?? [];
      next.push(edge.downstreamId);
      adjacency.set(edge.upstreamId, next);
    }
    const stack = [candidate.downstreamId];
    const visited = new Set<string>();
    while (stack.length > 0) {
      const current = stack.pop() as string;
      if (current === candidate.upstreamId) return true;
      if (visited.has(current)) continue;
      visited.add(current);
      stack.push(...(adjacency.get(current) ?? []));
    }
    return false;
  }
}
