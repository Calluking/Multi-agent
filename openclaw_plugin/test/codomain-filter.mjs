import { MemoryEngine } from "../dist/memory-engine.js";

const root = process.argv[2];
const engine = new MemoryEngine({ storeRoot: root, maxItemsPerMemory: 8 });
const ids = (await engine.retrieve("codomain", "FoodChain customer restaurant delivery order")).map((item) => item.id);
console.log(JSON.stringify(ids));
if (ids.some((id) => /planner|impl|review/.test(id))) process.exit(1);
