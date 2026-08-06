import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-dedup-test-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  const base = {
    kind: "codomain",
    scope: "shared",
    title: "Encoding.encode contract",
    text: "Preserve default behavior and compose both keyword arguments.",
    status: "required",
    evidence: [],
    tags: ["project:openai-tiktoken-task0", "shared-artifact:tiktoken/core.py"],
    targetRoles: ["position-owner", "token-limit-owner"],
    projectId: "openai-tiktoken-task0",
    artifactIds: ["tiktoken/core.py"],
    interfaceId: "Encoding.encode",
    producerIds: ["token-limit-owner"],
    consumerIds: ["position-owner"],
  };

  const first = await engine.upsert({ ...base, id: "contract:canonical" });
  const duplicate = await engine.upsert({
    ...base,
    id: "contract:coordinator-duplicate",
    title: "Joint options on the public encoder API",
    text: "Both independently owned features must work together in one invocation.",
    tags: [...base.tags].reverse(),
    targetRoles: [...base.targetRoles].reverse(),
  });

  const differentProject = await engine.upsert({
    ...base,
    id: "contract:other-project",
    projectId: "other",
    tags: ["project:other", "shared-artifact:tiktoken/core.py"],
  });

  const bank = JSON.parse(await readFile(join(root, "codomain.json"), "utf8"));
  if (bank.items.length !== 2) throw new Error(`expected 2 records, got ${bank.items.length}`);
  if (duplicate.id !== first.id) throw new Error(`expected canonical id ${first.id}, got ${duplicate.id}`);
  if (!bank.items.some((item) => item.id === differentProject.id)) {
    throw new Error("project-distinct contract was incorrectly collapsed");
  }

  const partialUpdate = await engine.upsert({
    ...base,
    id: first.id,
    title: "Updated canonical contract",
    text: "Updated evidence-bearing wording.",
    projectId: undefined,
    artifactIds: undefined,
    interfaceId: undefined,
  });
  if (partialUpdate.projectId !== base.projectId || partialUpdate.interfaceId !== base.interfaceId) {
    throw new Error("partial update erased structured canonical identity");
  }
  console.log("PASS semantic duplicate collapse and project-scoped separation");
} finally {
  await rm(root, { recursive: true, force: true });
}
