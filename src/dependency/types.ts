export type ObligationStatus =
  | "accepted"
  | "ready"
  | "in_progress"
  | "produced"
  | "verified"
  | "complete"
  | "blocked"
  | "failed"
  | "stale"
  | "cancelled"
  | "orphaned";

export type DependencyRequirement =
  | "requires_produced"
  | "requires_accepted"
  | "requires_verified"
  | "requires_complete";

export interface ArtifactRequirement {
  artifactId: string;
}

export interface VerificationRequirement {
  verificationId: string;
  command: string;
  covers: string[];
  requiredAssertions?: string[];
  interactionCases?: Array<{
    id: string;
    category: "normal" | "error" | "precedence" | "compatibility";
    marker: string;
    binding?: { evidenceId: string; path: string; symbol: string; commandFragment: string };
  }>;
  interfaceEvidence?: Array<{ id: string; path: string; contains: string }>;
}

export interface ObligationDefinition {
  obligationId: string;
  runId: string;
  ownerId: string;
  title: string;
  source: {
    type: "starting_request" | "spawn_assignment" | "explicit_declaration";
    evidenceRef: string;
  };
  requiredOutputs: ArtifactRequirement[];
  requiredVerifications: VerificationRequirement[];
  consumerIds?: string[];
}

export interface DependencyEdge {
  edgeId: string;
  runId: string;
  upstreamId: string;
  downstreamId: string;
  requirement: DependencyRequirement;
  evidenceRef: string;
}

export interface ArtifactEvidence {
  artifactId: string;
  version: string;
  observedAt: string;
  eventId: string;
}

export interface VerificationEvidence {
  verificationId: string;
  command: string;
  success: boolean;
  artifactVersions: Record<string, string>;
  observedAt: string;
  eventId: string;
}

export interface RecoveryState {
  ownerId: string;
  retryCount: number;
  strategy: string;
  evidenceRef: string;
}

export interface ObligationRecord extends ObligationDefinition {
  status: ObligationStatus;
  artifacts: Record<string, ArtifactEvidence>;
  verifications: Record<string, VerificationEvidence>;
  active: boolean;
  completed: boolean;
  accepted: boolean;
  failure?: string;
  recovery?: RecoveryState;
}

interface EventBase {
  eventId: string;
  runId: string;
  observedAt: string;
}

export type DependencyEvent =
  | (EventBase & { type: "obligation.declared"; obligation: ObligationDefinition })
  | (EventBase & { type: "dependency.declared"; edge: DependencyEdge })
  | (EventBase & { type: "owner.started"; obligationId: string; ownerId: string })
  | (EventBase & {
      type: "artifact.observed";
      obligationId: string;
      artifactId: string;
      exists: boolean;
      version?: string;
    })
  | (EventBase & {
      type: "verification.observed";
      obligationId: string;
      verificationId: string;
      command: string;
      success: boolean;
      artifactVersions: Record<string, string>;
    })
  | (EventBase & { type: "owner.ended"; obligationId: string; ownerId: string; outcome: "ok" | "error" | "timeout" | "killed" })
  | (EventBase & { type: "obligation.completed"; obligationId: string })
  | (EventBase & { type: "obligation.cancelled"; obligationId: string; reason: string })
  | (EventBase & {
      type: "recovery.assigned";
      obligationId: string;
      ownerId: string;
      strategy: string;
      evidenceRef: string;
    });

export interface Blocker {
  edgeId: string;
  upstreamId: string;
  requiredState: DependencyRequirement;
  observedState: ObligationStatus;
  recoveryOwner?: string;
}

export type SpawnDecision =
  | { decision: "allow"; obligationId: string }
  | { decision: "wait"; obligationId: string; blockers: Blocker[] };

export interface OwnerProjection {
  obligationId: string;
  ownerId: string;
  title: string;
  status: ObligationStatus;
  requiredOutputs: ArtifactRequirement[];
  requiredVerifications: VerificationRequirement[];
  blockers: Blocker[];
  recovery?: RecoveryState;
}
