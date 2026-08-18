import { mkdir, open, readFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { TestingEvent } from "./types.js";

export interface TestingEventStore { load(runId: string): Promise<TestingEvent[]>; append(event: TestingEvent): Promise<void> }
export class JsonlTestingEventStore implements TestingEventStore {
  private queue: Promise<void> = Promise.resolve();
  constructor(private readonly path: string) {}
  async load(runId: string) { try { return (await readFile(this.path, "utf8")).split("\n").filter(Boolean).map((line) => JSON.parse(line) as TestingEvent).filter((e) => e.runId === runId); } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return []; throw error; } }
  async append(event: TestingEvent) { const write = async () => { await mkdir(dirname(this.path), { recursive: true }); const h = await open(this.path, "a"); try { await h.write(`${JSON.stringify(event)}\n`); await h.sync(); } finally { await h.close(); } }; this.queue = this.queue.then(write, write); await this.queue; }
}
export class InMemoryTestingEventStore implements TestingEventStore {
  readonly events: TestingEvent[] = [];
  async load(runId: string) { return this.events.filter((e) => e.runId === runId).map((e) => structuredClone(e)); }
  async append(event: TestingEvent) { this.events.push(structuredClone(event)); }
}
