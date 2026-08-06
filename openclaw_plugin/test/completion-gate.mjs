import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-completion-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  const base = {
    projectId: "task", runId: "run", scope: "private", kind: "dependency",
    title: "output", text: "output readiness", evidence: [],
  };
  await engine.upsert({ ...base, id: "output", subject: "output", artifactIds: ["out.md"],
    producerIds: ["worker"], consumerIds: ["completion"], lifecycleState: "blocked" });
  await engine.upsert({ id: "contract", kind: "codomain", scope: "shared", projectId: "task", runId: "run",
    interfaceId: "api", artifactIds: ["api"], title: "API", evidence: [], status: "agreed",
    text: "Producer domain=a; Consumer domain=b; Shared data=x; Boundary test=x" });
  if ((await engine.completionBlockers("task", "run")).length !== 2) {
    throw new Error("completion gate did not include artifact and contract blockers");
  }
  const output = (await engine.load("dependency")).items[0];
  const contract = (await engine.load("codomain")).items[0];
  await engine.upsert({ ...output, lifecycleState: "produced", status: "produced" });
  await engine.upsert({ ...contract, status: "verified" });
  if ((await engine.completionBlockers("task", "run")).length !== 0) {
    throw new Error("completion gate did not release resolved obligations");
  }
  console.log("PASS project-scoped artifact and contract completion gate");
} finally {
  await rm(root, { recursive: true, force: true });
}
