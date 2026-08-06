import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-isolation-"));
try {
  const engine = new MemoryEngine({ storeRoot: root, maxItemsPerMemory: 8 });
  const taskA = "Please write a software system called AlphaProject with registration and feedback rating.";
  const taskB = "Please write a software system called BetaProject with registration and feedback rating.";
  await engine.initializeFromTask(taskA, "run-a1");
  await engine.initializeFromTask(taskA, "run-a2");
  await engine.initializeFromTask(taskB, "run-b1");

  const bank = await engine.load("dependency");
  if (bank.items.length !== 9) throw new Error(`run-scoped initialization collapsed records: ${bank.items.length}`);
  const ids = new Set(bank.items.map((item) => item.id));
  if (ids.size !== bank.items.length) throw new Error("generated run-scoped IDs collided");

  const a1 = await engine.buildSpawnPacket("You are the IMPLEMENTER for AlphaProject", undefined,
    "implementer", "AlphaProject", "run-a1");
  if (a1.selected.dependency.length !== 2
    || a1.selected.dependency.some((id) => id.includes("BetaProject"))) {
    throw new Error("retrieval leaked another project or run");
  }
  const blockers = await engine.readinessBlockers("implementer", "AlphaProject", "run-a1");
  if (blockers.length !== 1 || blockers[0].runId !== "run-a1") {
    throw new Error("readiness gate leaked another run");
  }

  await engine.upsert({
    id: "generic-practice", kind: "testing", scope: "shared", title: "generic verify",
    text: "implementer executable verification", targetRoles: ["implementer"], evidence: [],
  });
  const generic = await engine.retrieve("testing", "implementer executable verification", undefined,
    "implementer", "AlphaProject", "run-a1");
  if (!generic.some((item) => item.id === "generic-practice")) {
    throw new Error("unscoped reusable practice was hidden");
  }
  console.log("PASS project/run isolation with reusable unscoped memory");
} finally {
  await rm(root, { recursive: true, force: true });
}
