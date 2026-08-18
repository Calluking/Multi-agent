# Testing-Practice Memory — First Implementation

The harness-neutral backend lives in `src/testing/` and implements the two-layer
model from `TESTING_PRACTICE_MEMORY.md`.

## Implemented

- universal semantic practices with lifecycle, applicability, evidence,
  invalid-substitute, confidence, cost, and provenance fields;
- hard-filtered sparse retrieval returning at most two practices;
- strict separation between advisory retrieval and run-specific obligations;
- owner-targeted projections so the coordinator can instantiate a concrete
  standard and each worker extracts only standards assigned to its work;
- append-only JSONL and in-memory verification ledgers;
- authoritative and advisory obligation sources;
- exact-command evidence with cwd, timestamps, exit status, output references,
  assertion summary, and current SHA-256 artifact versions;
- automatic stale state after any covered artifact changes;
- real-path enforcement for boundary verification;
- failed-evidence retention and bounded, changed repair strategies;
- completion gates only for authoritative instantiated obligations;
- event replay, run isolation, and deterministic projections.

The OpenCode bridge is `adapters/opencode/testing-practice-memory.mjs`. It
exposes initialization, sparse practice search, declaration, inspection,
artifact observation, objective execution, repair assignment, and completion
decision tools. Verification is capped at 120 seconds, uses WSL's existing
`python3`, and rejects environment creation, runtime installation, and
system-path mutation.

Waiver exists in the backend event model but is intentionally not exposed as an
agent tool because explicit task authority cannot be authenticated reliably
through the current OpenCode tool surface.

Run `npm test` for all memory-mechanism regression tests.
