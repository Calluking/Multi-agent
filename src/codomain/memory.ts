import type { CoDomainEventStore } from "./store.js";
import type {
  BoundaryDecision,
  BoundaryVerificationEvidence,
  CoDomainEvent,
  ConsumerProjection,
  ContractDefinition,
  ContractRecord,
  ProducerProjection,
} from "./types.js";

const clone = <T>(value: T): T => structuredClone(value);

export class CoDomainMemory {
  private readonly contracts = new Map<string, ContractRecord>();
  private readonly seenEvents = new Set<string>();

  constructor(readonly runId: string, private readonly store: CoDomainEventStore) {}

  static async open(runId: string, store: CoDomainEventStore): Promise<CoDomainMemory> {
    const memory = new CoDomainMemory(runId, store);
    for (const event of await store.load(runId)) memory.reduce(event);
    return memory;
  }

  async record(event: CoDomainEvent): Promise<void> {
    if (event.runId !== this.runId) throw new Error(`event ${event.eventId} belongs to another run`);
    if (this.seenEvents.has(event.eventId)) return;
    this.validate(event);
    await this.store.append(event);
    this.reduce(event);
  }

  get(contractId: string): ContractRecord | undefined {
    const record = this.contracts.get(contractId); return record ? clone(record) : undefined;
  }

  list(): ContractRecord[] { return [...this.contracts.values()].map(clone); }

  projectForOwner(ownerId: string): Array<ProducerProjection | ConsumerProjection> {
    const result: Array<ProducerProjection | ConsumerProjection> = [];
    for (const record of this.contracts.values()) {
      const d = record.definition;
      const common = {
        contractId: d.contractId,
        interfaceId: d.interfaceId,
        version: d.version,
        agreementState: record.agreementState,
        verificationState: record.verificationState,
        fields: clone(d.semantics.fields),
        invariants: clone(d.semantics.invariants),
        openChallenges: clone(record.challenges.filter((item) => item.open)),
        boundaryVerification: clone(d.boundaryVerification),
      };
      if (ownerId === d.producer.ownerId) result.push({
        ...common,
        role: "producer",
        producerObligations: clone(d.semantics.producerObligations),
        consumerAssumptions: clone(d.semantics.consumerObligations),
      });
      if (ownerId === d.consumer.ownerId) result.push({
        ...common,
        role: "consumer",
        producerGuarantees: clone(d.semantics.producerObligations),
        consumerObligations: clone(d.semantics.consumerObligations),
        errorSemantics: clone(d.semantics.errorSemantics),
      });
    }
    return result;
  }

  integrationDecision(contractId: string): BoundaryDecision {
    const record = this.requireContract(contractId);
    const open = record.challenges.filter((item) => item.open);
    if (open.length > 0) return { decision: "block", contractId, reasons: open.map((item) => `open challenge: ${item.target}: ${item.detail}`) };
    if (record.agreementState !== "accepted") return {
      decision: "report_risk", contractId, reasons: ["contract has not been accepted by both participants"],
    };
    if (record.definition.risk === "high" && record.verificationState !== "verified") return {
      decision: "block", contractId, reasons: [`high-risk accepted boundary is ${record.verificationState}`],
    };
    if (record.verificationState !== "verified") return {
      decision: "report_risk", contractId, reasons: [`accepted boundary is ${record.verificationState}`],
    };
    return { decision: "allow", contractId, reasons: [] };
  }

  private validate(event: CoDomainEvent): void {
    if (event.type === "contract.candidate" || event.type === "contract.proposed") {
      this.validateDefinition(event.contract);
      const existing = this.contracts.get(event.contract.contractId);
      if (event.type === "contract.candidate" && existing) throw new Error("contract already exists");
      if (event.type === "contract.proposed") {
        if (event.authorId !== event.contract.producer.ownerId) throw new Error("only the producer may propose a contract");
        if (existing) {
          if (existing.agreementState !== "candidate") throw new Error("contract already proposed");
          const before = existing.definition;
          if (before.interfaceId !== event.contract.interfaceId || before.producer.ownerId !== event.contract.producer.ownerId || before.consumer.ownerId !== event.contract.consumer.ownerId) {
            throw new Error("proposal cannot change candidate structural identity");
          }
        }
      }
      return;
    }
    const record = this.requireContract(event.contractId);
    const current = record.definition;
    if (event.type === "contract.challenged") {
      this.requireCurrentVersion(current, event.baseVersion);
      if (!this.isParticipant(current, event.challenge.authorId)) throw new Error("challenge author is not a participant");
      if (event.challenge.authorId !== current.consumer.ownerId) throw new Error("only the consumer may challenge a contract");
      if (!event.challenge.detail.trim() || event.challenge.evidenceRefs.length === 0) throw new Error("challenge requires precise detail and evidence");
      if (record.challenges.some((item) => item.challengeId === event.challenge.challengeId)) throw new Error("challenge already exists");
    } else if (event.type === "contract.revised") {
      this.requireCurrentVersion(current, event.baseVersion);
      if (!this.isParticipant(current, event.authorId)) throw new Error("revision author is not a participant");
      if (event.authorId !== current.producer.ownerId) throw new Error("only the producer may revise a contract");
      if (event.sourceEvidence.length === 0) throw new Error("revision requires source evidence");
      for (const id of event.resolvesChallengeIds) {
        if (!record.challenges.some((item) => item.challengeId === id && item.open)) throw new Error(`unknown open challenge: ${id}`);
      }
    } else if (event.type === "contract.accepted") {
      this.requireCurrentVersion(current, event.version);
      if (!this.isParticipant(current, event.authorId)) throw new Error("acceptance author is not a participant");
      if (event.evidenceRefs.length === 0) throw new Error("acceptance requires evidence");
      if (record.challenges.some((item) => item.open)) throw new Error("cannot accept with open challenges");
    } else if (event.type === "artifact.observed") {
      if (!this.isParticipant(current, event.ownerId)) throw new Error("artifact owner is not a participant");
      const owned = event.ownerId === current.producer.ownerId ? current.producer.artifacts : current.consumer.artifacts;
      if (!owned.includes(event.artifactId)) throw new Error("artifact is not declared for this participant");
      if (!event.version) throw new Error("artifact observation requires a version");
      if (record.agreementState !== "accepted") throw new Error("implementation evidence requires current-version acceptance by both participants");
    } else if (event.type === "boundary.verified") {
      this.requireCurrentVersion(current, event.version);
      if (event.command !== current.boundaryVerification.command) throw new Error("verification command differs from contract");
      if (!event.realPath) throw new Error("disconnected verification cannot verify a boundary");
      if (event.evidenceRefs.length === 0) throw new Error("verification requires evidence references");
      if (record.agreementState !== "accepted") throw new Error("boundary verification requires current-version agreement by both participants");
      for (const artifact of this.allArtifacts(current)) {
        const observed = record.artifactVersions[artifact];
        if (!observed || event.artifactVersions[artifact] !== observed) throw new Error(`verification lacks current artifact: ${artifact}`);
      }
    }
  }

  private reduce(event: CoDomainEvent): void {
    if (this.seenEvents.has(event.eventId)) return;
    this.seenEvents.add(event.eventId);
    if (event.type === "contract.candidate" || event.type === "contract.proposed") {
      const existing = this.contracts.get(event.contract.contractId);
      if (event.type === "contract.proposed" && existing) {
        existing.definition = clone(event.contract);
        existing.agreementState = "proposed";
        existing.verificationState = "unverified";
        existing.acceptedBy = [];
        existing.challenges = [];
        existing.artifactVersions = {};
        delete existing.verification;
        return;
      }
      this.contracts.set(event.contract.contractId, {
        definition: clone(event.contract),
        agreementState: event.type === "contract.candidate" ? "candidate" : "proposed",
        verificationState: "unverified",
        acceptedBy: [], challenges: [], artifactVersions: {},
      });
      return;
    }
    const record = this.requireContract(event.contractId);
    switch (event.type) {
      case "contract.challenged":
        record.challenges.push({ ...clone(event.challenge), version: event.baseVersion, open: true });
        record.agreementState = "challenged";
        break;
      case "contract.revised":
        record.definition = {
          ...record.definition,
          semantics: clone(event.semantics),
          boundaryVerification: clone(event.boundaryVerification),
          sourceEvidence: [...record.definition.sourceEvidence, ...event.sourceEvidence],
          version: event.baseVersion + 1,
        };
        for (const item of record.challenges) if (event.resolvesChallengeIds.includes(item.challengeId)) item.open = false;
        record.acceptedBy = [];
        record.agreementState = record.challenges.some((item) => item.open) ? "challenged" : "proposed";
        if (record.verification) record.verificationState = "stale";
        break;
      case "contract.accepted":
        if (!record.acceptedBy.includes(event.authorId)) record.acceptedBy.push(event.authorId);
        record.agreementState = this.bothAccepted(record) ? "accepted" : "proposed";
        break;
      case "artifact.observed": {
        const previous = record.artifactVersions[event.artifactId];
        record.artifactVersions[event.artifactId] = event.version;
        if (record.verification && previous !== event.version) record.verificationState = "stale";
        break;
      }
      case "boundary.verified": {
        const evidence: BoundaryVerificationEvidence = {
          version: event.version, command: event.command, exitCode: event.exitCode,
          realPath: event.realPath, artifactVersions: clone(event.artifactVersions),
          evidenceRefs: clone(event.evidenceRefs), observedAt: event.observedAt, eventId: event.eventId,
        };
        record.verification = evidence;
        record.verificationState = event.exitCode === record.definition.boundaryVerification.expectedExitCode ? "verified" : "failed";
        break;
      }
    }
  }

  private validateDefinition(definition: ContractDefinition): void {
    if (definition.runId !== this.runId) throw new Error("contract run mismatch");
    if (definition.version !== 1) throw new Error("initial contract version must be 1");
    if (!definition.interfaceId.trim() || definition.sourceEvidence.length === 0) throw new Error("contract requires interface identity and source evidence");
    if (definition.producer.ownerId === definition.consumer.ownerId) throw new Error("producer and consumer must be distinct owners");
    if (definition.producer.artifacts.length === 0 || definition.consumer.artifacts.length === 0) throw new Error("both participants require grounded artifacts");
    if (!definition.boundaryVerification.command.trim()) throw new Error("boundary verification command is required");
  }

  private requireContract(contractId: string): ContractRecord {
    const record = this.contracts.get(contractId); if (!record) throw new Error(`unknown contract: ${contractId}`); return record;
  }
  private requireCurrentVersion(definition: ContractDefinition, version: number) {
    if (definition.version !== version) throw new Error(`stale contract version ${version}; current is ${definition.version}`);
  }
  private isParticipant(definition: ContractDefinition, ownerId: string) {
    return ownerId === definition.producer.ownerId || ownerId === definition.consumer.ownerId;
  }
  private allArtifacts(definition: ContractDefinition) { return [...new Set([...definition.producer.artifacts, ...definition.consumer.artifacts])]; }
  private bothAccepted(record: ContractRecord) {
    return record.acceptedBy.includes(record.definition.producer.ownerId) && record.acceptedBy.includes(record.definition.consumer.ownerId);
  }
}
