import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine, inferRole } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-targeting-"));
try {
  const engine = new MemoryEngine({ storeRoot: root, maxItemsPerMemory: 5 });
  const now = new Date().toISOString();
  const add = (item) => engine.upsert({ evidence: [], ...item });
  await add({ id: "dep-impl", kind: "dependency", scope: "private", title: "solution artifact", text: "solution.py missing; implement it", targetRoles: ["implementer"], status: "unresolved" });
  await add({ id: "dep-review", kind: "dependency", scope: "private", title: "verification artifact", text: "review solution.py", targetRoles: ["reviewer"], status: "required" });
  await add({ id: "test-review", kind: "testing", scope: "shared", title: "independent verification", text: "solution.py command assertions", targetRoles: ["reviewer"], status: "required", tags: ["role:reviewer"] });
  await add({ id: "test-unrelated", kind: "testing", scope: "shared", title: "mobile ui snapshot", text: "swift ios screenshot", targetRoles: ["reviewer"], status: "required" });
  await add({ id: "contract-current", kind: "codomain", scope: "shared", title: "profile to workshop", text: "Producer domain=profile module; Consumer domain=workshop module; Shared data=user_id; Invariant=known user; Boundary test=reject unknown", targetRoles: ["implementer", "reviewer"], participants: ["profile module", "workshop module"], status: "agreed", version: 2 });
  await add({ id: "contract-old", kind: "codomain", scope: "shared", title: "old profile contract", text: "Producer domain=profile module; Consumer domain=workshop module; Shared data=legacy_id; Invariant=legacy; Boundary test=legacy", targetRoles: ["implementer"], status: "superseded", version: 1 });

  if (inferRole("Spawn a reviewer responsible only for executable verification and review.md") !== "reviewer") throw new Error("role inference failed");
  if (inferRole("You are the IMPLEMENTER. Read TASK.md and plan.md, then write solution.py and implementation.md") !== "implementer") throw new Error("implementer was shadowed by plan.md");
  if (inferRole("You are the REVIEWER. Read plan.md, solution.py and implementation.md, then write review.md") !== "reviewer") throw new Error("reviewer was shadowed by predecessor artifacts");
  const reviewer = await engine.buildSpawnPacket("Reviewer verifies solution.py profile module workshop module with executable assertions");
  if (!reviewer.selected.dependency.includes("dep-review") || reviewer.selected.dependency.includes("dep-impl")) throw new Error("dependency role targeting failed");
  if (!reviewer.selected.testing.includes("test-review") || reviewer.selected.testing.includes("test-unrelated")) throw new Error("sparse testing retrieval failed");
  if (!reviewer.selected.codomain.includes("contract-current") || reviewer.selected.codomain.includes("contract-old")) throw new Error("contract state/version targeting failed");
  const planner = await engine.buildSpawnPacket("Planner responsible only for plan.md");
  if (Object.values(planner.selected).flat().length !== 0) throw new Error("irrelevant memory leaked to planner");

  const autoRoot = await mkdtemp(join(tmpdir(), "multiagent-memory-auto-"));
  try {
    const workspace = join(autoRoot, "workspace");
    await mkdir(workspace);
    const auto = new MemoryEngine({ storeRoot: join(autoRoot, "bank"), maxItemsPerMemory: 5 });
    await auto.initializeFromTask("Please write a software system called CulturalExchangeHub. Registration and profile are required. Tours, language and workshops produce experiences. Feedback and rating consume them.");
    const initial = await auto.buildSpawnPacket("You are the IMPLEMENTER for CulturalExchangeHub. Write solution.py and implementation.md.");
    if (!initial.selected.dependency.includes("CulturalExchangeHub:implementation-artifacts")) throw new Error("automatic dependency initialization failed");
    if (!initial.selected.codomain.includes("CulturalExchangeHub:experience-feedback-contract")) throw new Error("automatic co-domain initialization failed");
    if (!initial.selected.testing.includes("CulturalExchangeHub:implementer-verification-practice")) throw new Error("automatic testing initialization failed");
    await writeFile(join(workspace, "plan.md"), "plan");
    await auto.observeWorkflow(workspace, "planner");
    const planBank = await auto.load("dependency");
    const planState = planBank.items.find((item) => item.id.endsWith("plan-artifact"));
    if (planState?.lifecycleState !== "produced" || planState.status === "verified") {
      throw new Error("workspace observation incorrectly treated existence as verification");
    }
  } finally {
    await rm(autoRoot, { recursive: true, force: true });
  }

  const coopRoot = await mkdtemp(join(tmpdir(), "multiagent-memory-cooper-"));
  try {
    const coop = new MemoryEngine({ storeRoot: coopRoot, maxItemsPerMemory: 5 });
    const cooperativeTask = `[Project openai-tiktoken-task0]\n[Assignment token-limit-owner]\nTitle: Add max_tokens to Encoding.encode\nFile: tiktoken/core.py\n[Assignment position-owner]\nTitle: Add return_positions to Encoding.encode\nFile: tiktoken/core.py`;
    await coop.initializeFromTask(cooperativeTask);
    const a = await coop.buildSpawnPacket(`${cooperativeTask}\nCurrent assignment: token-limit-owner`, undefined, "token-limit-owner");
    const b = await coop.buildSpawnPacket(`${cooperativeTask}\nCurrent assignment: position-owner`, undefined, "position-owner");
    if (!a.selected.dependency.some((id) => id.endsWith("token-limit-owner")) || a.selected.dependency.some((id) => id.endsWith("position-owner"))) throw new Error("peer assignment targeting failed");
    if (!b.selected.dependency.some((id) => id.endsWith("position-owner")) || b.selected.dependency.some((id) => id.endsWith("token-limit-owner"))) throw new Error("second peer targeting failed");
    if (a.selected.codomain.length !== 1 || b.selected.codomain.length !== 1) throw new Error("shared artifact contract was not delivered to both peers");
    if (!a.selected.testing.some((id) => id.includes("token-limit-owner")) || !b.selected.testing.some((id) => id.includes("position-owner"))) throw new Error("peer testing practice targeting failed");
    if (inferRole("Current assignment: token-limit-owner") !== undefined) throw new Error("arbitrary assignment was forced into benchmark roles");
  } finally {
    await rm(coopRoot, { recursive: true, force: true });
  }
  console.log("PASS role-scoped sparse retrieval and current-contract selection");
} finally {
  await rm(root, { recursive: true, force: true });
}
