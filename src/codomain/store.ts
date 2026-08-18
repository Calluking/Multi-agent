import { mkdir, open, readFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { CoDomainEvent } from "./types.js";

export interface CoDomainEventStore {
  load(runId: string): Promise<CoDomainEvent[]>;
  append(event: CoDomainEvent): Promise<void>;
}

export class JsonlCoDomainEventStore implements CoDomainEventStore {
  private queue: Promise<void> = Promise.resolve();
  constructor(private readonly path: string) {}
  async load(runId: string): Promise<CoDomainEvent[]> {
    let text: string;
    try { text = await readFile(this.path, "utf8"); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return []; throw error; }
    return text.split("\n").filter(Boolean).map((line) => JSON.parse(line) as CoDomainEvent).filter((event) => event.runId === runId);
  }
  async append(event: CoDomainEvent): Promise<void> {
    const write = async () => {
      await mkdir(dirname(this.path), { recursive: true });
      const handle = await open(this.path, "a");
      try { await handle.write(`${JSON.stringify(event)}\n`); await handle.sync(); }
      finally { await handle.close(); }
    };
    this.queue = this.queue.then(write, write); await this.queue;
  }
}

export class InMemoryCoDomainEventStore implements CoDomainEventStore {
  readonly events: CoDomainEvent[] = [];
  async load(runId: string) { return this.events.filter((event) => event.runId === runId).map((event) => structuredClone(event)); }
  async append(event: CoDomainEvent) { this.events.push(structuredClone(event)); }
}
