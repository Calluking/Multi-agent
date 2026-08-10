import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-verification-"));
const workspace = await mkdtemp(join(tmpdir(), "multiagent-workspace-verification-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  await writeFile(join(workspace, "solution.py"), "print('ok')\n");
  await engine.upsert({
    id: "task:solution", kind: "dependency", scope: "private",
    projectId: "task", subject: "solution-readiness", artifactIds: ["solution.py"],
    verificationCommand: "python3 solution.py", title: "Solution",
    text: "Observed=present; Evidence=none; Blocker=null", status: "unresolved",
    evidence: [], lifecycleState: "produced",
  });

  if (await engine.recordVerification(workspace, { command: "pytest", exitCode: 0 }) !== 0) {
    throw new Error("unrelated command verified an artifact");
  }
  await engine.recordVerification(workspace, {
    command: "python3 solution.py", exitCode: 1, error: "failed",
  });
  let item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "blocked" || item.verificationAttempts.at(-1).passed) {
    throw new Error("failed command did not create a blocking attempt");
  }

  await engine.recordVerification(workspace, {
    command: `cd ${workspace} && python3 solution.py; echo "EXIT=$?"`,
    exitCode: 0, output: "failed\nEXIT=1",
  });
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "blocked" || item.verificationAttempts.at(-1).passed) {
    throw new Error("status-echo wrapper hid the inner verification failure");
  }

  await engine.recordVerification(workspace, {
    command: `cd ${workspace} && python3 solution.py; echo "EXIT=$?"`,
    exitCode: 0, output: "ok\nEXIT=0",
  });
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "verified" || !item.verificationAttempts.at(-1).passed) {
    throw new Error("successful matching command did not verify artifact version");
  }
  if (!item.verificationAttempts.at(-1).artifactVersions["solution.py"]) {
    throw new Error("verification attempt did not bind artifact hash");
  }

  await writeFile(join(workspace, "solution.py"), "print('changed')\n");
  await engine.observeWorkflow(workspace);
  item = (await engine.load("dependency")).items[0];
  if (item.lifecycleState !== "produced" || item.status !== "stale") {
    throw new Error("post-verification edit did not invalidate ledger evidence");
  }
  console.log("PASS exact-command verification ledger and artifact-version binding");
} finally {
  await rm(root, { recursive: true, force: true });
  await rm(workspace, { recursive: true, force: true });
}
