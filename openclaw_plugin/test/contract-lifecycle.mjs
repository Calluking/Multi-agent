import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-contract-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  const contract = {
    id: "contract:encode", kind: "codomain", scope: "shared", projectId: "tiktoken",
    artifactIds: ["tiktoken/core.py"], interfaceId: "Encoding.encode",
    producerIds: ["token-owner"], consumerIds: ["position-owner"],
    title: "Encoding contract",
    text: "Producer domain=token feature; Consumer domain=position feature; Shared data=signature; Boundary test=both options",
    evidence: [],
  };
  let stored = await engine.applyContractAction(contract, "propose");
  if (stored.version !== 1 || stored.status !== "proposed") throw new Error("proposal state invalid");
  stored = await engine.applyContractAction({ ...contract, text: "missing return shape" }, "challenge", 1);
  if (stored.status !== "challenged" || stored.version !== 1) throw new Error("challenge state invalid");
  stored = await engine.applyContractAction({ ...contract, text: "complete joint return shape" }, "revise", 1);
  if (stored.status !== "proposed" || stored.version !== 2) throw new Error("revision did not increment version");
  await engine.applyContractAction(contract, "accept", 2);
  stored = await engine.applyContractAction({ ...contract, evidence: ["joint call passed"] }, "verify", 2);
  if (stored.status !== "verified" || stored.evidence.at(-1) !== "joint call passed") {
    throw new Error("verification state invalid");
  }
  let rejected = false;
  try { await engine.applyContractAction(contract, "accept", 1); } catch { rejected = true; }
  if (!rejected) throw new Error("stale contract acceptance was not rejected");
  if ((await engine.load("codomain")).items.length !== 1) throw new Error("lifecycle created duplicate contracts");
  console.log("PASS typed contract lifecycle and stale-version rejection");
} finally {
  await rm(root, { recursive: true, force: true });
}
