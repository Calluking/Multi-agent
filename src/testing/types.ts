export type PracticeState = "candidate" | "validated" | "active" | "deprecated";
export type VerificationState = "pending" | "running" | "passed" | "failed" | "repair_pending" | "stale" | "waived";
export type VerificationSourceType = "starting_request" | "assignment_promise" | "accepted_contract" | "observed_failure" | "adopted_practice";

export interface TestingPractice {
  practiceId: string;
  title: string;
  state: PracticeState;
  applicability: { artifactTypes: string[]; actions: string[]; risks: string[]; surfaces: string[] };
  rule: string;
  requiredEvidence: string[];
  invalidSubstitutes: string[];
  failureAction: string;
  confidence: number;
  cost: number;
  successfulRuns: string[];
  counterexamples: string[];
}

export interface VerificationSource { type: VerificationSourceType; ref: string; authoritative: boolean }
export interface VerificationDefinition {
  verificationId: string; runId: string; source: VerificationSource; ownerId: string;
  artifacts: string[]; practiceRefs: string[]; command: string; requiredAssertions: string[];
  boundary: boolean; maxRetries: number;
}
export interface VerificationEvidence {
  evidenceId: string; command: string; cwd: string; exitCode: number; startedAt: string; endedAt: string;
  artifactVersions: Record<string, string>; assertionsObserved: string[]; stdoutRef: string; stderrRef: string;
  realPath: boolean;
}
export interface RepairEpisode { ownerId: string; strategy: string; attempt: number; evidenceRef: string }
export interface VerificationRecord {
  definition: VerificationDefinition; state: VerificationState; artifactVersions: Record<string, string>;
  evidence: VerificationEvidence[]; repairs: RepairEpisode[]; waiver?: { authority: string; reason: string };
}
export interface PracticeQuery { artifactType?: string; action?: string; risk?: string; surface?: string; limit?: number }
export interface CompletionDecision { decision: "allow" | "block"; reasons: string[]; unresolved: string[] }

interface BaseEvent { eventId: string; runId: string; observedAt: string }
export type TestingEvent =
  | (BaseEvent & { type: "verification.declared"; definition: VerificationDefinition })
  | (BaseEvent & { type: "artifact.observed"; verificationId: string; artifactId: string; version: string })
  | (BaseEvent & { type: "verification.started"; verificationId: string; command: string })
  | (BaseEvent & { type: "verification.observed"; verificationId: string; evidence: VerificationEvidence })
  | (BaseEvent & { type: "repair.assigned"; verificationId: string; repair: RepairEpisode })
  | (BaseEvent & { type: "verification.waived"; verificationId: string; authority: string; reason: string });
