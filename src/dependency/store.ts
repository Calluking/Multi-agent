import { mkdir, open, readFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { DependencyEvent } from "./types.js";

export interface DependencyEventStore {
  load(runId: string): Promise<DependencyEvent[]>;
  append(event: DependencyEvent): Promise<void>;
}

export class JsonlDependencyEventStore implements DependencyEventStore {
  private writeQueue: Promise<void> = Promise.resolve();

  constructor(private readonly path: string) {}

  async load(runId: string): Promise<DependencyEvent[]> {
    let text: string;
    try {
      text = await readFile(this.path, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    return text
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line) as DependencyEvent)
      .filter((event) => event.runId === runId);
  }

  async append(event: DependencyEvent): Promise<void> {
    const write = async () => {
      await mkdir(dirname(this.path), { recursive: true });
      const handle = await open(this.path, "a");
      try {
        await handle.write(`${JSON.stringify(event)}\n`);
        await handle.sync();
      } finally {
        await handle.close();
      }
    };
    this.writeQueue = this.writeQueue.then(write, write);
    await this.writeQueue;
  }
}

export class InMemoryDependencyEventStore implements DependencyEventStore {
  readonly events: DependencyEvent[] = [];

  async load(runId: string): Promise<DependencyEvent[]> {
    return this.events.filter((event) => event.runId === runId);
  }

  async append(event: DependencyEvent): Promise<void> {
    this.events.push(structuredClone(event));
  }
}
