# OpenClaw Multi-Agent Memory Plugin

This native OpenClaw plugin participates directly in subagent creation. It is not a benchmark wrapper and does not require planner/implementer/reviewer role names.

## Architecture

1. `before_tool_call` intercepts `sessions_spawn`.
2. It retrieves and injects up to N items from three independent banks:
   - private dependency state;
   - shared producer/consumer co-domain contracts;
   - shared testing-practice knowledge.
3. `subagent_spawned` binds the injection to the real child session key.
4. `subagent_ended` records a compact execution episode.
5. Two tools support typed writes and inspection; a bundled skill documents correct use.

The hook is the enforcement mechanism. The skill is guidance only.

## Build and validate

```bash
cd openclaw_plugin
npm install
npm run plugin:validate   # Type-check the mixed Hook + Tool entry
npm run plugin:build
```

Seed a development store before the first run:

```bash
mkdir -p /home/luzh/.openclaw/multiagent-memory
cp seed/*.json /home/luzh/.openclaw/multiagent-memory/
```

Install for local development:

```bash
openclaw plugins install --link "$PWD"
openclaw plugins enable multiagent-memory
openclaw gateway restart
openclaw plugins inspect multiagent-memory --runtime --json
```

`openclaw plugins build/validate --entry` is intentionally not used here: in
OpenClaw 2026.6 that command validates `defineToolPlugin`-only packages. This is
a mixed Hook + Tool plugin using `definePluginEntry`; runtime inspection after
installation is its authoritative registration check.

Example config:

```json5
{
  plugins: {
    entries: {
      "multiagent-memory": {
        enabled: true,
        config: {
          storeRoot: "/home/luzh/.openclaw/multiagent-memory",
          dependencyEnabled: true,
          codomainEnabled: true,
          testingEnabled: true,
          maxItemsPerMemory: 3
        }
      }
    }
  },
  tools: {
    allow: ["multiagent_memory_record", "multiagent_memory_inspect"]
  }
}
```

## Current boundary

This first plugin version validates the integration seam and typed persistence. Retrieval is deterministic lexical ranking. The next iteration should reuse the already-tested extractors and state transitions under `dependency_memory/v4_sparse` and add artifact-backed completion validation.
