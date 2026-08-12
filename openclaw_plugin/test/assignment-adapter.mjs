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
  if (objectiveOnly[0].artifactIds.includes("PATCH_READY.md")) {
    throw new Error(`bare ready artifact bypassed assignment workspace: ${objectiveOnly[0].artifactIds}`);
  }
  const contextSniper = await engine.registerAssignment({ projectId: "encode-project", runId: "run-1",
    assignmentId: "token-owner", workspace: root,
    task: "You are token-owner. Your workspace is `./peer_token/` which is a repository copy." });
  if (contextSniper[0].workDirectory !== "peer_token") {
    throw new Error(`relative workspace form was not retained: ${contextSniper[0].workDirectory}`);
  }
  const apiHeavyTask = `[Project api-project]
[Assignment api-owner]
Artifact: peer_a/PATCH_READY.md
Workspace: peer_a
Goal:
Modify \`src/click/termui.py\` and expose \`Editor.wait_timeout\`.
[Assignment peer-owner]
Artifact: peer_b/PATCH_READY.md
Workspace: peer_b
Goal:
Modify \`src/click/termui.py\` and expose \`Editor.working_dir\`.`;
  await engine.initializeFromTask(apiHeavyTask, "run-api");
  const apiOwner = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: "You are api-owner. Workspace: peer_a\nWrite peer_a/PATCH_READY.md." });
  if (!apiOwner[0].artifactIds.includes("peer_a/src/click/termui.py")
    || apiOwner[0].artifactIds.some((artifact) => artifact.includes("Editor.wait_timeout"))) {
    throw new Error(`API symbols were treated as files: ${apiOwner[0].artifactIds.join(",")}`);
  }
  const cooperWording = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: `Work ONLY in the workspace directory \`peer_a\` (absolute path: ${root}/peer_a).` });
  if (cooperWording[0].workDirectory !== "peer_a") {
    throw new Error(`CooperBench workspace wording was not normalized: ${cooperWording[0].workDirectory}`);
  }
  const cooperAbsolute = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: `Work ONLY inside the workspace directory: ${root}/peer_a\nDo not edit elsewhere.` });
  if (cooperAbsolute[0].workDirectory !== "peer_a") {
    throw new Error(`CooperBench absolute workspace wording was not normalized: ${cooperAbsolute[0].workDirectory}`);
  }
  const freeWording = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: `You own code over there. Implement only the assigned feature.` });
  if (freeWording[0].workDirectory !== "peer_a") {
    throw new Error(`declared PATCH_READY parent was not used as workspace fallback: ${freeWording[0].workDirectory}`);
  }
  const headingContamination = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: `Workspace:\nYou work ONLY inside ${root}/peer_a (this is your peer directory). Do not edit elsewhere.` });
  if (headingContamination[0].workDirectory !== "peer_a") {
    throw new Error(`workspace heading consumed an instruction sentence: ${headingContamination[0].workDirectory}`);
  }
  const misleadingProse = await engine.registerAssignment({ projectId: "api-project", runId: "run-api",
    assignmentId: "api-owner", workspace: root,
    task: "Your workspace is the peer directory described above." });
  if (misleadingProse[0].workDirectory !== "peer_a") {
    throw new Error(`inferred prose overrode declared assignment ownership: ${misleadingProse[0].workDirectory}`);
  }
console.log("PASS universal assignment workdir and artifact ownership adapter");
} finally {
  await rm(root, { recursive: true, force: true });
}
