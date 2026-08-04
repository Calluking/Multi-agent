import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryEngine } from "../dist/memory-engine.js";

const root = await mkdtemp(join(tmpdir(), "multiagent-memory-test-"));
try {
  const engine = new MemoryEngine({ storeRoot: root });
  await Promise.all(Array.from({ length: 40 }, (_, index) => engine.upsert({
    id: `contract:${index}`,
    kind: "codomain",
    scope: "shared",
    title: `contract ${index}`,
    text: `producer consumer boundary ${index}`,
    status: "required",
    evidence: [],
    tags: ["concurrency-test"],
  })));
  const parsed = JSON.parse(await readFile(join(root, "codomain.json"), "utf8"));
  if (parsed.items.length !== 40) throw new Error(`expected 40 items, got ${parsed.items.length}`);
  console.log("PASS concurrent memory writes: 40/40 records preserved");
} finally {
  await rm(root, { recursive: true, force: true });
}
