import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-readiness-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  await engine.upsert({
    id: "task:plan", kind: "dependency", scope: "private", projectId: "task",
    subject: "plan", artifactIds: ["plan.md"], producerIds: ["planner"], consumerIds: ["implementer"],
    title: "Plan", text: "plan missing", status: "unresolved", lifecycleState: "blocked", evidence: [],
  });
  await engine.upsert({
    id: "task:solution", kind: "dependency", scope: "private", projectId: "task",
    subject: "solution", artifactIds: ["solution.py"], producerIds: ["implementer"], consumerIds: ["reviewer"],
    verificationCommand: "python3 solution.py", title: "Solution", text: "solution missing",
    status: "unresolved", lifecycleState: "blocked", evidence: [], targetRoles: ["implementer"],
  });

  if ((await engine.readinessBlockers("planner")).length !== 0) throw new Error("producer was blocked by its own output");
  if ((await engine.readinessBlockers("implementer")).map((item) => item.id).join() !== "task:plan") {
    throw new Error("implementer prerequisite gate failed");
  }
  const plan = (await engine.load("dependency")).items.find((item) => item.id === "task:plan");
  await engine.upsert({ ...plan, lifecycleState: "produced", status: "produced" });
  if ((await engine.readinessBlockers("implementer")).length !== 0) {
    throw new Error("non-command artifact did not become consumable when produced");
  }
  if ((await engine.readinessBlockers("reviewer")).length !== 1) throw new Error("reviewer was not gated");

  await engine.recordLifecycleOutcome({
    selectedIds: ["task:solution"], assignment: "implementer", outcome: "timeout", error: "turn timed out",
  });
  const solution = (await engine.load("dependency")).items.find((item) => item.id === "task:solution");
  if (solution.lifecycleState !== "blocked" || solution.recoveryOwnerId !== "implementer") {
    throw new Error("failed lifecycle did not create owned recovery obligation");
  }
  if (solution.lifecycleOutcomes.at(-1).outcome !== "timeout") throw new Error("lifecycle outcome was not retained");
  let admission = await engine.recoveryAdmission("implementer", "task", undefined);
  if (!admission.allowed || admission.obligations.length !== 1) throw new Error("first bounded recovery was not admitted");
  const packet = await engine.buildSpawnPacket("Implement solution.py after timeout", undefined,
    "implementer", "task", undefined);
  if (!packet.packet.includes("BOUNDED RECOVERY OBLIGATION")
    || !packet.packet.includes("materially changed strategy")) {
    throw new Error("recovery directive was not injected");
  }
  await engine.recordLifecycleOutcome({
    selectedIds: ["task:solution"], assignment: "implementer", outcome: "error", error: "retry failed",
  });
  admission = await engine.recoveryAdmission("implementer", "task", undefined);
  if (admission.allowed || !admission.reason?.includes("exhausted")) {
    throw new Error("bounded recovery budget was not enforced");
  }
  console.log("PASS readiness gating and lifecycle recovery ownership");
} finally {
  await rm(root, { recursive: true, force: true });
}
