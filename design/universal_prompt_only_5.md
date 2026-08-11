# Universal Prompt-Only Five-Scenario Set

The harness may create empty workspaces and submit a root prompt. It must not call
memory tools, seed memory records, or tell agents how to transition plugin state.

## 1. Sequential custom handoff

- Agents: `schema-author` then `service-builder`
- Directories: `blueprint/`, `service/`
- Handoffs: `blueprint/SCHEMA_DONE.json`, `service/BUILD_DONE.txt`
- Verification: `python3 service/app.py`
- Expected: builder admission waits for the schema handoff; both dependencies end
  produced; testing evidence binds the final executable.

## 2. Parallel producers, custom integration tree

- Agents: `left-producer`, `right-producer`
- Directories: `left_lab/`, `right_lab/`; final tree: `assembled/`
- Handoffs: `left_lab/LEFT_READY.yaml`, `right_lab/RIGHT_READY.yaml`
- Shared interface: JSON message `{name, value}`
- Verification: `node assembled/check.mjs`
- Expected: both producers complete, a co-domain contract is discovered from the
  declared handoffs without relying on PATCH_READY.md, and composition is verified.

## 3. Three-agent diamond

- Agents: `source-owner`, `rule-owner`, `report-owner`
- Directories: `source_box/`, `rule_box/`, `report_box/`; final tree: `result/`
- Handoffs: `SOURCE.OK`, `RULE.OK`, `REPORT.OK`
- Dependency: report consumes both source and rule outputs.
- Verification: `python3 result/verify.py`
- Expected: the consumer cannot complete before both prerequisites; all three
  assignments are tracked independently.

## 4. Shared root with file ownership

- Agents: `parser-owner`, `formatter-owner`
- No peer directories; owned artifacts are `lib/parser.ts` and `lib/formatter.ts`.
- Handoffs: `handoffs/parser.json`, `handoffs/formatter.json`
- Verification: `node verify.mjs`
- Expected: ownership is derived from declared artifacts rather than directory-name
  conventions; shared API evidence is verified.

## 5. Contract repair and negative testing

- Agents: `producer`, `consumer`, `auditor`
- Directories: `producer_zone/`, `consumer_zone/`, `audit_zone/`; final tree: `final/`
- First producer/consumer drafts intentionally use different field names; the auditor
  must identify the mismatch and the coordinator must repair it before completion.
- Handoffs: `PRODUCER.done`, `CONSUMER.done`, `AUDIT.done`
- Verification: `python3 final/contract_test.py`, including a negative-input assertion.
- Expected: co-domain/testing state cannot verify the incompatible draft; finalization
  occurs only after repaired joint and negative evidence passes.

## Common audit

For every scenario:

1. Root exits normally without a session lock or timeout.
2. Every declared handoff and final artifact exists.
3. No dependency record ends blocked/unresolved.
4. Every product co-domain contract ends verified.
5. Every required composition-testing record ends verified.
6. A premature `sessions_yield` attempt, if made, is blocked and followed by work.
