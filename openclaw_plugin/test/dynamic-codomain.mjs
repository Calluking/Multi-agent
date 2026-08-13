import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const workspace = await mkdtemp(join(tmpdir(), "multiagent-memory-codomain-"));
const store = join(workspace, ".memory");
try {
  const engine = new MemoryEngine({ storeRoot: store });
  const task = `[Project click-compose]
[Assignment timeout-owner]
Title: editor timeout
File: peer_a/PATCH_READY.md
[Assignment shell-owner]
Title: shell escaping
File: peer_b/PATCH_READY.md`;
  await engine.initializeFromTask(task, "run-1");
  await engine.registerAssignment({ projectId: "click-compose", runId: "run-1",
    assignmentId: "timeout-owner", workspace,
    task: "work only in `peer_a/`; write `peer_a/PATCH_READY.md`" });
  await engine.registerAssignment({ projectId: "click-compose", runId: "run-1",
    assignmentId: "shell-owner", workspace,
    task: "You are shell-owner. Your workspace is `./peer_b/` which is a repository copy." });
  await mkdir(join(workspace, "peer_a"), { recursive: true });
  await mkdir(join(workspace, "peer_b"), { recursive: true });
  await writeFile(join(workspace, "peer_a", "PATCH_READY.md"), `# Ready
## Changed API
Public function \`click.edit()\` in \`src/click/termui.py\` adds \`timeout: int | None = None\`.
The concrete changed file is \`peer_a/src/click/termui.py\`.
Temporary checks used \`peer_a_selftest.py\` and imported \`termui.py\`.
Another disposable probe was \`sanity_wd.py\`.
The default must keep calling \`wait()\`; timeout raises \`ClickException("Editing timed out")\`.
## Evidence
$ python -m pytest tests/test_termui.py -q
62 tests passed.\n`);
  await writeFile(join(workspace, "peer_b", "PATCH_READY.md"), `# Ready
## Changed API
Public function \`click.edit()\` in \`src/click/termui.py\` adds \`escape_shell: bool = False\`.
Forward it through \`src/click/_termui_impl.py\` without dropping existing parameters.
## Evidence
$ python -m pytest tests/test_termui.py -q
19 tests passed.\n`);

  const contract = await engine.discoverCoDomainFromHandoffs(workspace, "click-compose", "run-1");
  if (!contract) throw new Error("separate handoffs did not create a co-domain contract");
  if (contract.artifactIds.some((path) => /selftest|sanity|^termui\.py$/i.test(path))) {
    throw new Error(`test scaffolding or duplicate basename entered product contract: ${contract.artifactIds}`);
  }
  if (contract.artifactIds.some((path) => /^peer_[ab]\//.test(path))) {
    throw new Error(`producer workspace prefix leaked into integration contract: ${contract.artifactIds}`);
  }
  if (contract.status !== "agreed") throw new Error(`unexpected state ${contract.status}`);
  for (const expected of ["timeout: int | None = None", "escape_shell: bool = False",
    "wait()", "src/click/termui.py", "same integrated tree"]) {
    if (!contract.text.includes(expected)) throw new Error(`contract lost boundary fact: ${expected}`);
  }
  const context = await engine.integrationContext("click-compose", "run-1");
  if (!context.includes(contract.id) || !context.includes("simultaneous acceptance criterion")
    || !context.includes("multiagent_contract_transition")) {
    throw new Error("integration turn did not receive enforceable contract context");
  }
  const blockers = await engine.completionBlockers("click-compose", "run-1");
  if (!blockers.some((item) => item.id === contract.id)) {
    throw new Error("unverified dynamic contract did not block completion");
  }
  const integration = join(workspace, "integration");
  await mkdir(join(integration, "src/click"), { recursive: true });
  await writeFile(join(integration, "src/click/termui.py"), "def edit(): pass\n");
  await writeFile(join(integration, "src/click/_termui_impl.py"), "class Editor: pass\n");
  await engine.recordCoDomainVerification(workspace, {
    command: `cd ${join(workspace, "peer_a")} && python -m pytest tests/test_termui.py -q`,
    exitCode: 0, projectId: "click-compose", runId: "run-1", coordinator: true,
  });
  const peerOnly = (await engine.load("codomain")).items.find((item) => item.id === contract.id);
  if (peerOnly?.status === "verified") {
    throw new Error("peer-local test incorrectly verified the integration contract");
  }
  await engine.recordTestingVerification(workspace, {
    command: `cd ${join(workspace, "peer_a")} && python -m pytest tests/test_termui.py -q`,
    exitCode: 0, projectId: "click-compose", runId: "run-1", coordinator: true,
  });
  const peerTesting = (await engine.load("testing")).items
    .filter((item) => item.projectId === "click-compose" && item.runId === "run-1");
  if (peerTesting.some((item) => item.status === "verified")) {
    throw new Error("peer-local test incorrectly verified composition testing memory");
  }
  await engine.recordCoDomainVerification(workspace, {
    command: "cd " + workspace + " && echo checking && cd integration && python -m pytest tests/test_termui.py -q",
    exitCode: 0, projectId: "click-compose", runId: "run-1",
  });
  const verified = (await engine.load("codomain")).items.find((item) => item.id === contract.id);
  if (verified?.status !== "verified") {
    throw new Error(`integration command did not verify contract: ${verified?.status}`);
  }
  await engine.recordTestingVerification(workspace, {
    command: `cd ${integration} && python -m pytest tests/test_termui.py -q`, exitCode: 0,
    projectId: "click-compose", runId: "run-1",
  });
  const testing = (await engine.load("testing")).items
    .filter((item) => item.projectId === "click-compose" && item.runId === "run-1");
  if (!testing.length || testing.some((item) => item.status !== "verified")) {
    throw new Error(`composition testing evidence was not promoted: ${testing.map((item) => item.status)}`);
  }
  console.log("PASS dynamic handoff discovery, integration injection, and verification gate");
} finally {
  await rm(workspace, { recursive: true, force: true });
}
