import {
  appendCoordinatorContinuation,
  appendProducerContinuation,
  workspaceFromSpawn,
} from "../dist/index.js";

const root = "/tmp/multi-agent/task_02";
const cases = [
  ["", undefined, root, root],
  ["Write the deliverable in workspace root (/tmp/multi-agent/task_02/plan.md).", undefined, undefined, root],
  ["Work only in `/tmp/multi-agent/task_02`.", undefined, undefined, root],
  ["Write `/tmp/multi-agent/task_02/PATCH_READY.md` when done.", undefined, undefined, root],
  ["ignored", `${root}/solution.py`, undefined, root],
];

for (const [task, explicit, remembered, expected] of cases) {
  const actual = workspaceFromSpawn(task, explicit, remembered);
  if (actual !== expected) {
    throw new Error(`workspace mismatch: expected=${expected} actual=${actual}`);
  }
}

const producerResult = appendProducerContinuation(
  { role: "toolResult", content: [{ type: "text", text: "file written" }] },
  "implementer",
  ["task:implementation-artifacts"],
);
if (!producerResult.content[1].text.includes("command run before the last write is stale evidence")) {
  throw new Error("producer result did not enforce post-write verification");
}

const toolResult = appendCoordinatorContinuation({
  role: "toolResult",
  content: [{ type: "text", text: "spawn accepted" }],
}, "Call one bounded exec wait now.");
if (toolResult.content.length !== 2
  || !toolResult.content[1].text.includes("Call one bounded exec wait now")) {
  throw new Error("spawn result did not carry the coordinator continuation obligation");
}

console.log("workspace resolution test passed");
