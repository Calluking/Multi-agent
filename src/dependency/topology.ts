import type { DependencyEvent, DependencyRequirement, ObligationDefinition } from "./types.js";

export interface RequiredStage {
  id: string;
  responsibility: string;
  depends_on: string[];
  required_outputs?: string[];
  verification?: { id: string; command: string; covers: string[] };
  release_requirement?: DependencyRequirement;
}

export interface RequiredTopology {
  id: string;
  topology_policy?: "required" | "budget";
  stages?: RequiredStage[];
}

export function compileRequiredTopology(task: RequiredTopology, runId: string, observedAt: string): DependencyEvent[] {
  if (task.topology_policy !== "required" || !task.stages) return [];
  const events: DependencyEvent[] = [];
  for (const stage of task.stages) {
    const obligation: ObligationDefinition = {
      obligationId: `${runId}:${stage.id}`,
      runId,
      ownerId: stage.id,
      title: stage.responsibility,
      source: { type: "explicit_declaration", evidenceRef: `manifest:${task.id}:${stage.id}` },
      requiredOutputs: (stage.required_outputs ?? []).map((artifactId) => ({ artifactId })),
      requiredVerifications: stage.verification ? [{
        verificationId: stage.verification.id,
        command: stage.verification.command,
        covers: [...stage.verification.covers],
      }] : [],
    };
    events.push({
      type: "obligation.declared",
      eventId: `${runId}:declare:${stage.id}`,
      runId,
      observedAt,
      obligation,
    });
  }
  for (const stage of task.stages) {
    for (const upstream of stage.depends_on) {
      events.push({
        type: "dependency.declared",
        eventId: `${runId}:edge:${upstream}:${stage.id}`,
        runId,
        observedAt,
        edge: {
          edgeId: `${runId}:${upstream}->${stage.id}`,
          runId,
          upstreamId: `${runId}:${upstream}`,
          downstreamId: `${runId}:${stage.id}`,
          requirement: stage.release_requirement ?? "requires_complete",
          evidenceRef: `manifest:${task.id}:${stage.id}:depends_on:${upstream}`,
        },
      });
    }
  }
  return events;
}
