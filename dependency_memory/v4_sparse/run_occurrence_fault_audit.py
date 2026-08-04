#!/usr/bin/env python3
"""Re-audit all four collaboration faults by trajectory occurrence, not final residue."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any

import run_interface_panel as base


FAULTS = ("adaptive", "cross_domain", "dependency", "testing")

PROMPT = r"""You are re-auditing one MultiAgentBench trajectory. Read every relevant log line by line; do not infer from score alone and do not modify files. Inspect TASK.md, official_task.json, result.json, every *_stdout.json and *_stderr.txt, plan.md, implementation.md, review.md, solution.py, test_solution.py, and all memory/audit JSON files that exist.

Question: did each collaboration fault OCCUR at any point in the trajectory? This is not a final-residue audit. A later repair does not erase an earlier handoff/readiness/interface fault. Multiple labels are allowed.

Rules:
1. adaptive: runtime output, tool failure, reviewer/user feedback, or changed evidence reached an Agent before a later opportunity, but that Agent ignored it, repeated the failed approach, or handed off without an appropriate adjustment. A normal failure that is immediately diagnosed, corrected, and re-verified is NOT a fault.
2. cross_domain: an actually exercised producer/consumer technical boundary (frontend/backend, UI/functionality, ML/application, NLP/mobile, data/analytics, networking/state, visualization/engine, or another concrete boundary) was missing, incompatible, simulated in place of the required real boundary, or handed off with conflicting semantics. Later repair does not erase the occurrence. Generic incompleteness without an exercised boundary is not enough.
3. dependency: a consumer Agent started before a required producer artifact, state, decision, interface, or verification evidence was ready; a required handoff was missing/invalid; or ordering/readiness constraints were violated. If the Reviewer later writes the missing implementation itself, the earlier missing producer→consumer dependency STILL counts as a dependency fault. Recovery does not erase occurrence.
4. testing: the implementation/testing collaboration loop was defective at some point: code was handed off or approved without executed evidence; a tester validated a semantic substitute instead of the defining capability; a concrete observed defect was ignored; an acceptance oracle was weakened; or the Implementer failed and the Reviewer authored both the substitute implementation and its tests and self-approved it, collapsing independent collaboration. Merely finding a defect and then correctly repairing and re-verifying it is NOT a testing fault.

Set exercised=false only when the trajectory truly offered no opportunity to evaluate that category. Missing implementation normally makes testing unexercised, but can still produce dependency=true if a downstream consumer started without it. Under no circumstances return an empty rationale. Every fault=true needs at least two concrete evidence entries naming files/stages. Every exercised=false needs evidence explaining why.

Return JSON only:
{"task_id":1,"adaptive":{"fault":false,"exercised":true,"evidence":["file: fact"],"rationale":"..."},"cross_domain":{"fault":false,"exercised":false,"evidence":["file: why not exercised"],"rationale":"..."},"dependency":{"fault":false,"exercised":true,"evidence":["file: fact"],"rationale":"..."},"testing":{"fault":false,"exercised":true,"evidence":["file: fact"],"rationale":"..."}}
"""


def parse_json(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S))
    decoder = json.JSONDecoder()
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    for match in reversed(list(re.finditer(r"\{", text))):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError("auditor did not return valid JSON")


def task_id_for(workspace: Path) -> int:
    return int(json.loads((workspace / "official_task.json").read_text(encoding="utf-8"))["task_id"])


def validate(value: dict[str, Any], task_id: int) -> dict[str, Any]:
    clean: dict[str, Any] = {"task_id": task_id}
    if int(value.get("task_id", -1)) != task_id:
        raise ValueError("wrong task id")
    for name in FAULTS:
        item = value.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"missing {name}")
        rationale = str(item.get("rationale", "")).strip()
        evidence = [str(x).strip() for x in item.get("evidence", []) if str(x).strip()]
        exercised = bool(item.get("exercised", False))
        fault = bool(item.get("fault", False))
        if not rationale or not evidence:
            raise ValueError(f"{name} has empty evidence/rationale")
        if fault and len(evidence) < 2:
            raise ValueError(f"{name} fault needs at least two evidence entries")
        clean[name] = {"fault": fault, "exercised": exercised, "evidence": evidence[:8], "rationale": rationale}
    return clean


def audit(workspace: Path, condition: str) -> dict[str, Any]:
    task_id = task_id_for(workspace)
    target = workspace / "occurrence_fault_audit.json"
    if target.exists():
        try:
            return validate(json.loads(target.read_text(encoding="utf-8")), task_id)
        except Exception:
            pass
    errors = []
    for attempt in range(1, 4):
        agent_id = f"mab-occurrence-audit-{condition}-t{task_id:02d}-{uuid.uuid4().hex[:6]}"
        base.ensure_agent(agent_id, workspace)
        try:
            envelope = base.call_agent(
                workspace, agent_id, f"occurrence-audit-{condition}-t{task_id:02d}-a{attempt}",
                PROMPT, f"occurrence_fault_audit_attempt_{attempt}"
            )
            result = validate(parse_json(base.payload_text(envelope)), task_id)
            target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return result
        except Exception as exc:
            errors.append(repr(exc))
    raise ValueError("; ".join(errors))


def discover(roots: list[Path]) -> list[Path]:
    found: dict[int, Path] = {}
    for root in roots:
        for result in root.rglob("result.json"):
            try:
                found[task_id_for(result.parent)] = result.parent
            except Exception:
                pass
    return [found[k] for k in sorted(found)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True)
    ap.add_argument("--roots", nargs="+", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    rows, errors = [], []
    for workspace in discover(args.roots):
        try:
            rows.append(audit(workspace, args.condition))
        except Exception as exc:
            errors.append({"task_id": task_id_for(workspace), "workspace": str(workspace), "error": repr(exc)})
    result = {
        "condition": args.condition,
        "criterion": "fault_occurred_anywhere_in_trajectory",
        "audited_tasks": len(rows),
        "fault_counts": {name: sum(int(row[name]["fault"]) for row in rows) for name in FAULTS},
        "not_exercised_counts": {name: sum(int(not row[name]["exercised"]) for row in rows) for name in FAULTS},
        "tasks": rows,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
