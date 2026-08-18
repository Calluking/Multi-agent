export type AgreementState = "candidate" | "proposed" | "challenged" | "accepted" | "superseded";
export type BoundaryVerificationState = "unverified" | "verified" | "failed" | "stale";
export type ContractRisk = "low" | "medium" | "high";

export interface ContractParticipant {
  ownerId: string;
  artifacts: string[];
}

export interface SharedField {
  name: string;
  type: string;
  meaning: string;
}

export interface ContractSemantics {
  fields: SharedField[];
  producerObligations: string[];
  consumerObligations: string[];
  invariants: string[];
  errorSemantics: string[];
}

export interface BoundaryVerificationRequirement {
  command: string;
  expectedExitCode: number;
  requiredAssertions?: string[];
  interactionCases?: InteractionCase[];
  interfaceEvidence?: InterfaceEvidence[];
}

export interface BaselineBinding {
  evidenceId: string;
  path: string;
  symbol: string;
  commandFragment: string;
}

export interface InteractionCase {
  id: string;
  category: "normal" | "error" | "precedence" | "compatibility";
  marker: string;
  binding?: BaselineBinding;
}

export interface InterfaceEvidence {
  id: string;
  path: string;
  contains: string;
}

export interface ContractDefinition {
  contractId: string;
  runId: string;
  interfaceId: string;
  sourceEvidence: string[];
  producer: ContractParticipant;
  consumer: ContractParticipant;
  semantics: ContractSemantics;
  boundaryVerification: BoundaryVerificationRequirement;
  risk: ContractRisk;
  version: number;
}

export interface ContractChallenge {
  challengeId: string;
  authorId: string;
  target: "field" | "producer_obligation" | "consumer_obligation" | "invariant" | "error_semantics" | "verification";
  detail: string;
  evidenceRefs: string[];
  version: number;
  open: boolean;
}

export interface BoundaryVerificationEvidence {
  version: number;
  command: string;
  exitCode: number;
  realPath: boolean;
  artifactVersions: Record<string, string>;
  evidenceRefs: string[];
  observedAt: string;
  eventId: string;
}

export interface ContractRecord {
  definition: ContractDefinition;
  agreementState: AgreementState;
  verificationState: BoundaryVerificationState;
  acceptedBy: string[];
  challenges: ContractChallenge[];
  artifactVersions: Record<string, string>;
  verification?: BoundaryVerificationEvidence;
}

interface EventBase { eventId: string; runId: string; observedAt: string }

export type CoDomainEvent =
  | (EventBase & { type: "contract.candidate"; contract: ContractDefinition })
  | (EventBase & { type: "contract.proposed"; contract: ContractDefinition; authorId: string })
  | (EventBase & { type: "contract.challenged"; contractId: string; baseVersion: number; challenge: Omit<ContractChallenge, "version" | "open"> })
  | (EventBase & { type: "contract.revised"; contractId: string; baseVersion: number; authorId: string; semantics: ContractSemantics; boundaryVerification: BoundaryVerificationRequirement; sourceEvidence: string[]; resolvesChallengeIds: string[] })
  | (EventBase & { type: "contract.accepted"; contractId: string; version: number; authorId: string; evidenceRefs: string[] })
  | (EventBase & { type: "artifact.observed"; contractId: string; ownerId: string; artifactId: string; version: string })
  | (EventBase & { type: "boundary.verified"; contractId: string; version: number; command: string; exitCode: number; realPath: boolean; artifactVersions: Record<string, string>; evidenceRefs: string[] });

export interface ProducerProjection {
  role: "producer";
  contractId: string;
  interfaceId: string;
  version: number;
  agreementState: AgreementState;
  verificationState: BoundaryVerificationState;
  fields: SharedField[];
  producerObligations: string[];
  consumerAssumptions: string[];
  invariants: string[];
  openChallenges: ContractChallenge[];
  boundaryVerification: BoundaryVerificationRequirement;
}

export interface ConsumerProjection {
  role: "consumer";
  contractId: string;
  interfaceId: string;
  version: number;
  agreementState: AgreementState;
  verificationState: BoundaryVerificationState;
  fields: SharedField[];
  producerGuarantees: string[];
  consumerObligations: string[];
  invariants: string[];
  errorSemantics: string[];
  openChallenges: ContractChallenge[];
  boundaryVerification: BoundaryVerificationRequirement;
}

export interface BoundaryDecision {
  decision: "allow" | "block" | "report_risk";
  contractId: string;
  reasons: string[];
}
