#!/usr/bin/env python3
"""Evidence-based four-fault audit for completed MultiAgentBench runs."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any

import run_interface_panel as base


FAULTS = ("adaptive", "cross_domain", "dependency", "testing")

AUDIT_PROMPT = r"""Act as a strict benchmark log auditor. Read the task and run evidence line by line. Do not modify any files. Inspect TASK.md, official_task.json, result.json, every *_stdout.json and *_stderr.txt, plan.md, implementation.md, review.md, solution.py, and every memory/audit JSON file that exists.

Classify four faults using these exact rules:
1. adaptive: runtime output or user/reviewer feedback was visibly delivered before a later agent opportunity, but the later action failed to adapt, repair, or re-verify it. A final failure alone is insufficient.
2. cross_domain: an exercised producer/consumer technical boundary (for example frontend/backend, UI/functionality, ML/application, NLP/mobile, data/analytics, networking/state, visualization/engine) is materially incompatible, simulated instead of real, or missing. Do not mark generic incompleteness.
3. dependency: ordering, readiness, required-artifact handoff, or interface prerequisites were violated, causing premature work, an invalid handoff, or a consumer acting without its dependency. A generic command mismatch alone is insufficient.
4. testing: an exercised implementation-test-feedback loop is defective: an observed failure remains unresolved; tests validate the wrong substitute; a central requirement is absent but approved; or a concrete defect visible to the tester is missed. If no implementation exists, testing was not exercised.

Important reporting convention: if a criterion is not exercised or cannot be evaluated because the artifact is absent, set exercised=false and fault=false. This implements the requested display convention (NE counts as zero) while preserving the distinction in the raw audit.

Return JSON only, with this exact shape:
{"task_id": 1, "adaptive":{"fault":false,"exercised":true,"evidence":["file: concise fact"],"rationale":"..."}, "cross_domain":{"fault":false,"exercised":true,"evidence":[],"rationale":"..."}, "dependency":{"fault":false,"exercised":true,"evidence":[],"rationale":"..."}, "testing":{"fault":false,"exercised":true,"evidence":[],"rationale":"..."}}
Use the actual task id. Evidence must name files and concrete observations. Never infer a fault only from a benchmark score."""


def parse_json(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", text))):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError("auditor did not return valid JSON")


def task_id_for(workspace: Path) -> int:
    official = json.loads((workspace / "official_task.json").read_text(encoding="utf-8"))
    return int(official["task_id"])


def validate(value: dict[str, Any], task_id: int) -> dict[str, Any]:
    clean: dict[str, Any] = {"task_id": task_id}
    for fault in FAULTS:
        item = value.get(fault, {})
        exercised = bool(item.get("exercised", False))
        clean[fault] = {
            "fault": bool(item.get("fault", False)) if exercised else False,
            "exercised": exercised,
            "evidence": [str(x) for x in item.get("evidence", [])][:6],
            "rationale": str(item.get("rationale", "")),
        }
    return clean


def audit_workspace(workspace: Path, condition: str) -> dict[str, Any]:
    task_id = task_id_for(workspace)
    existing = workspace / "four_fault_audit.json"
    if existing.exists():
        return validate(json.loads(existing.read_text(encoding="utf-8")), task_id)
    agent_id = f"mab-fault-audit-{condition}-t{task_id:02d}-{uuid.uuid4().hex[:6]}"
    base.ensure_agent(agent_id, workspace)
    envelope = base.call_agent(
        workspace, agent_id, f"fault-audit-{condition}-t{task_id:02d}",
        AUDIT_PROMPT, "four_fault_audit"
    )
    result = validate(parse_json(base.payload_text(envelope)), task_id)
    existing.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def discover(roots: list[Path]) -> list[Path]:
    found: dict[int, Path] = {}
    for root in roots:
        for result in sorted(root.rglob("result.json")):
            workspace = result.parent
            try:
                found[task_id_for(workspace)] = workspace
            except Exception:
                continue
    return [found[key] for key in sorted(found)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspaces = discover(args.roots)
    if not workspaces:
        raise SystemExit("no completed runs found")
    audits, errors = [], []
    for workspace in workspaces:
        try:
            audits.append(audit_workspace(workspace, args.condition))
        except Exception as exc:
            errors.append({"workspace": str(workspace), "error": repr(exc)})
    counts = {fault: sum(int(row[fault]["fault"]) for row in audits) for fault in FAULTS}
    not_exercised = {fault: sum(int(not row[fault]["exercised"]) for row in audits) for fault in FAULTS}
    output = {
        "condition": args.condition,
        "display_convention": "not_exercised_is_zero",
        "audited_tasks": len(audits),
        "fault_counts": counts,
        "not_exercised_counts": not_exercised,
        "tasks": audits,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
