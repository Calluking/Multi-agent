import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-assignment-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  const task = `[Project encode-project]
[Assignment token-owner]
Title: token limit
File: tiktoken/core.py
[Assignment position-owner]
Title: positions
File: tiktoken/core.py

taskName/label: token-owner
work only in \`peer_token/\`
write \`peer_token/PATCH_READY.md\``;
  await engine.initializeFromTask(task, "run-1");
  const updated = await engine.registerAssignment({
    projectId: "encode-project", runId: "run-1", assignmentId: "token-owner", task,
  });
  if (updated.length !== 1) throw new Error("assignment dependency was not found");
  const item = updated[0];
  if (item.workDirectory !== "peer_token") throw new Error(`work directory=${item.workDirectory}`);
  if (!item.artifactIds.includes("peer_token/tiktoken/core.py")
    || !item.artifactIds.includes("peer_token/PATCH_READY.md")) {
    throw new Error(`owned artifacts not normalized: ${item.artifactIds.join(",")}`);
  }
  if (!item.targetRoles.includes("token-owner")) {
    throw new Error(`producer role lost during assignment registration: ${item.targetRoles.join(",")}`);
  }
  const other = (await engine.load("dependency")).items.find((entry) => entry.producerIds?.includes("position-owner"));
  if (other.artifactIds.some((artifact) => artifact.startsWith("peer_token/"))) {
    throw new Error(`assignment path leaked to peer owner: ${JSON.stringify(other)}`);
  }
  const absoluteTask = `You are token-owner working ONLY in the workspace directory: ${root}/peer_token\n`
    + "Create PATCH_READY.md when complete.";
  const absolute = await engine.registerAssignment({ projectId: "encode-project", runId: "run-1",
    assignmentId: "token-owner", task: absoluteTask, workspace: root });
  if (absolute[0].workDirectory !== "peer_token") {
    throw new Error(`OpenClaw absolute workspace phrase not normalized: ${absolute[0].workDirectory}`);
  }
  const objectiveOnly = await engine.registerAssignment({ projectId: "encode-project", runId: "run-1",
    assignmentId: "token-owner", workspace: root,
    task: `You are token-owner working ONLY in the workspace directory: ${root}/peer_token\nCreate PATCH_READY.md.` });
  if (objectiveOnly[0].workDirectory !== "peer_token") {
    throw new Error(`objective-only assignment did not retain its work directory: ${objectiveOnly[0].workDirectory}`);
  }
  const contextSniper = await engine.registerAssignment({ projectId: "encode-project", runId: "run-1",
    assignmentId: "token-owner", workspace: root,
    task: "You are token-owner. Your workspace is `./peer_token/` which is a repository copy." });
  if (contextSniper[0].workDirectory !== "./peer_token") {
    throw new Error(`relative workspace form was not retained: ${contextSniper[0].workDirectory}`);
  }
  console.log("PASS universal assignment workdir and artifact ownership adapter");
} finally {
  await rm(root, { recursive: true, force: true });
}
