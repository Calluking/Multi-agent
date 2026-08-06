import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-observer-"));
const workspace = await mkdtemp(join(tmpdir(), "multiagent-workspace-observer-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  await engine.upsert({
    id: "task:solution-readiness",
    kind: "dependency",
    scope: "private",
    projectId: "task",
    subject: "solution-readiness",
    artifactIds: ["solution.py"],
    title: "Solution readiness",
    text: "Observed=missing; Evidence=none; Blocker=solution.py absent; Next action=implement",
    status: "unresolved",
    evidence: [],
  });

  await engine.observeWorkflow(workspace);
  let item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "blocked") throw new Error(`missing artifact state=${item.lifecycleState}`);

  await writeFile(join(workspace, "solution.py"), "print('ok')\n");
  await engine.observeWorkflow(workspace);
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "produced") throw new Error(`produced artifact state=${item.lifecycleState}`);
  if (item.status === "verified") throw new Error("artifact existence incorrectly implied verification");
  const firstHash = item.artifactObservations[0].sha256;

  await engine.upsert({ ...item, lifecycleState: "verified", status: "verified" });
  await engine.observeWorkflow(workspace);
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "verified") throw new Error("unchanged verified artifact lost verification");

  await writeFile(join(workspace, "solution.py"), "print('changed')\n");
  await engine.observeWorkflow(workspace);
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "produced" || item.status !== "stale") {
    throw new Error(`changed artifact did not invalidate verification: ${item.lifecycleState}/${item.status}`);
  }
  if (item.artifactObservations[0].sha256 === firstHash) throw new Error("artifact hash did not change");
  console.log("PASS artifact observation, produced state, and stale verification invalidation");
} finally {
  await rm(root, { recursive: true, force: true });
  await rm(workspace, { recursive: true, force: true });
}
