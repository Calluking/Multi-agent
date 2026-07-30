#!/usr/bin/env python3
"""Run shared-interface-memory MultiAgentBench development experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from interface_memory import (compact_view, coverage_summary, load_or_empty, render_patterns,
                              retrieve_patterns, save_bank, summarize_audit)
from sparse_memory import append_event, fail_open_observe, observe_blocker, recovery_prompt


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "runs_interface_x1"
DATASET = Path("/home/luzh/multi-agent_2/MARBLE/multiagentbench/coding/coding_main.jsonl")
MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_PANEL = list(range(1, 21))
AGENTS_TEXT = """# Sparse-recovery MultiAgentBench coding run

Treat TASK.md as the sole product specification. Do not use MARBLE, MARBLE profiles,
MARBLE actions, or previous task results. Work in files, use Python's standard library,
keep behavior deterministic, and never claim tests passed without running them.
"""
BOUNDARY_EXTRACTOR_PROMPT = """Act as a task-level interface-memory generator. Read only TASK.md and AGENTS.md. Create interface_memory.json as valid JSON with this shape: {\"interfaces\": [{\"interface_id\": \"short_id\", \"producer\": \"required domain/technology\", \"consumer\": \"required domain/technology\", \"task_evidence\": \"short exact requirement from TASK.md\", \"risk\": 1, \"purpose\": \"why behavior must cross\", \"fields\": [{\"name\": \"field\", \"type\": \"type\", \"meaning\": \"semantic meaning\"}], \"producer_obligations\": [\"concrete obligation\"], \"consumer_obligations\": [\"concrete obligation\"], \"invariants\": [\"property spanning both sides\"], \"boundary_test\": {\"setup\": \"state in producer\", \"action\": \"real crossing\", \"expected\": \"observable consumer result\"}}]}. Select at most three boundaries explicitly required by the official task. Rank risk 5 highest. Prefer required frontend/backend, external data/service, real-time/event, ML/application, NLP/application, cross-user authorization, and multi-party state boundaries. Do not select generic CLI dispatch, database CRUD, constructors, or internal registration merely because they are easy to test. Do not design implementation details or write plan.md. Keep chat under three lines."""
PLANNER_PROMPT = """Act as planner. Read TASK.md, AGENTS.md, and interface_memory.json. Write plan.md covering architecture, every requirement, dependencies, deterministic tests, and edge cases. Treat the task-derived interface records as fixed acceptance requirements and bind each producer, consumer, invariant, and boundary test to concrete components. Do not replace required product boundaries with generic CLI/database substitutes. Do not modify interface_memory.json and do not implement code. Keep chat under five lines."""
BASELINE_PLANNER_PROMPT = "Act as planner. Read TASK.md and AGENTS.md. Write plan.md covering architecture, every requirement, dependencies, deterministic tests, and edge cases. Do not implement code. Keep chat under five lines."
X3_PLANNER_PROMPT = """Act as planner and task-level interface-memory generator. Read TASK.md and AGENTS.md. First create interface_memory.json using the exact JSON schema described below, then create plan.md that binds each record to concrete components and executable boundary tests. Cover architecture, every task requirement, dependencies, deterministic tests, and edge cases.

Schema: {\"interfaces\": [{\"interface_id\": \"short_id\", \"producer\": \"required domain/technology\", \"consumer\": \"required domain/technology\", \"task_evidence\": \"short exact requirement from TASK.md\", \"risk\": 1, \"purpose\": \"why behavior must cross\", \"fields\": [{\"name\": \"field\", \"type\": \"type\", \"meaning\": \"semantic meaning\"}], \"producer_obligations\": [\"concrete obligation\"], \"consumer_obligations\": [\"concrete obligation\"], \"invariants\": [\"property spanning both sides\"], \"boundary_test\": {\"setup\": \"state in producer\", \"action\": \"real crossing\", \"expected\": \"observable consumer result\"}}]}.

Select at most three boundaries explicitly required by the official task and rank risk 5 highest. Prefer required frontend/backend, external data/service, real-time/event, ML/application, NLP/application, cross-user authorization, and multi-party state boundaries. Do not select generic CLI dispatch, database CRUD, constructors, or internal registration merely because they are easy to test. Do not replace required product boundaries with generic substitutes. Do not implement code. Keep chat under five lines."""
X4_PLANNER_PROMPT = X3_PLANNER_PROMPT.replace(
    "Select at most three boundaries", "Select at most five boundaries"
).replace(
    "and multi-party state boundaries.",
    "and multi-party state boundaries. Also select cross-requirement state propagation: data introduced in one "
    "requirement that must constrain another capability, including availability, membership, occupancy, permissions, "
    "feedback, and notifications. For requirements described as web, external, real-time, interactive media, email, "
    "ML, or NLP, require an executable technical seam and reject data-only or hard-coded simulation as evidence.",
)
IMPLEMENTER_PROMPT = "Act as implementer. Read TASK.md, AGENTS.md, and plan.md. Create a complete self-contained solution.py with deterministic executable tests. Run python3 solution.py and fix failures. Write implementation.md with the exact command and result. Keep chat under five lines."
REVIEWER_PROMPT = "Act as independent reviewer. Read TASK.md, AGENTS.md, plan.md, solution.py, and implementation.md. Check every requirement and edge case. Run python3 solution.py. Repair solution.py if needed, add reviewer tests where useful, rerun, and write review.md with exact results. Keep chat under five lines."
INTEGRATION_PROMPT = """Act as a cross-domain integration specialist. Read TASK.md, plan.md, solution.py, implementation.md, and the shared interface memory appended below. Focus only on the detailed highest-risk contract. Exercise its real producer-to-consumer path with an executable boundary test. Reject placeholders and simulation-only seams when the task requires web, external data, real-time events, media, ML/NLP, authorization, or multi-party state propagation. Repair the smallest implementation gap, rerun python3 solution.py plus your boundary test, and write integration.md with exact evidence. Do not redesign unrelated features. Keep chat under five lines."""
POSTHOC_INTEGRATION_PROMPT = """Act as an evidence-grounded cross-domain integration specialist. Read TASK.md, plan.md, solution.py, and implementation.md. Inspect the actual implementation and select exactly one highest-impact required producer-to-consumer boundary that is missing, incompatible, simulation-only, or semantically incomplete. Prefer frontend/backend, external data, real-time event, ML/NLP application, authorization, interactive media, or multi-party state propagation defects.

Create interface_memory.json as valid JSON with exactly one interface record using this schema: {\"interfaces\": [{\"interface_id\": \"short_id\", \"producer\": \"actual component\", \"consumer\": \"actual component\", \"task_evidence\": \"requirement\", \"risk\": 5, \"purpose\": \"crossing\", \"fields\": [{\"name\": \"field\", \"type\": \"type\", \"meaning\": \"meaning\"}], \"producer_obligations\": [\"obligation\"], \"consumer_obligations\": [\"obligation\"], \"invariants\": [\"invariant\"], \"boundary_test\": {\"setup\": \"setup\", \"action\": \"real crossing\", \"expected\": \"observable result\"}}]}.

Then repair that one boundary, execute its real end-to-end test plus python3 solution.py, and write integration.md with exact before/after evidence. Do not broaden scope or rewrite working unrelated code. Keep chat under five lines."""
JUDGE_PROMPT = "Read TASK.md and solution.py when present. Score strictly: instruction_following, executability, consistency, quality, each integer 1-5. Deduct for every missing or partial requirement. Do not modify files. Output only one JSON object with those four keys."


def run(command: list[str], cwd: Path, timeout: int = 660) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def load_tasks() -> dict[int, dict[str, Any]]:
    return {int(x["task_id"]): x for x in
            (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip())}


def parse_task_ids(value: str) -> list[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    return sorted(result)


def ensure_agent(agent_id: str, workspace: Path) -> None:
    proc = run(["openclaw", "agents", "add", agent_id, "--non-interactive", "--workspace",
                str(workspace), "--model", MODEL, "--json"], workspace, 120)
    (workspace / "agent_add.stdout").write_text(proc.stdout, encoding="utf-8")
    (workspace / "agent_add.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(proc.stderr or proc.stdout)
    for _ in range(30):
        listed = run(["openclaw", "agents", "list", "--json"], workspace, 60)
        try:
            if listed.returncode == 0 and any(x.get("id") == agent_id for x in json.loads(listed.stdout)):
                time.sleep(5)
                return
        except json.JSONDecodeError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Agent {agent_id} was not discoverable")


def call_agent(workspace: Path, agent_id: str, session: str, prompt: str, label: str) -> dict[str, Any]:
    proc: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, 7):
        proc = run(["openclaw", "agent", "--agent", agent_id, "--session-id", session,
                    "--model", MODEL, "--thinking", "off", "--timeout", "600", "--json",
                    "--message", prompt], workspace)
        (workspace / f"{label}.attempt_{attempt}.stderr").write_text(proc.stderr, encoding="utf-8")
        if "unknown agent id" not in (proc.stderr or "").lower():
            break
        time.sleep(5 * attempt)
    assert proc is not None
    (workspace / f"{label}.stdout.json").write_text(proc.stdout, encoding="utf-8")
    (workspace / f"{label}.stderr").write_text(proc.stderr, encoding="utf-8")
    (workspace / f"{label}.exit").write_text(f"{proc.returncode}\n", encoding="utf-8")
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr or f"{label} returned no output")
    envelope = json.loads(proc.stdout)
    if envelope.get("status") != "ok":
        raise RuntimeError(f"{label} returned non-ok")
    return envelope


def stage_meta(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not envelope:
        return {}
    meta = envelope.get("result", {}).get("meta", {})
    return {"duration_ms": meta.get("durationMs"), "liveness_state": meta.get("livenessState"), "error": meta.get("error"),
            "tool_summary": meta.get("toolSummary", {}),
            "usage": meta.get("agentMeta", {}).get("usage", {})}


def verify_solution(workspace: Path) -> dict[str, Any]:
    solution = workspace / "solution.py"
    if not solution.is_file():
        return {"compile_exit": None, "run_exit": None, "error": "solution.py missing"}
    compile_proc = run([sys.executable, "-m", "py_compile", "solution.py"], workspace, 30)
    result: dict[str, Any] = {"compile_exit": compile_proc.returncode,
                              "compile_stderr": compile_proc.stderr[-3000:]}
    try:
        executed = run([sys.executable, "solution.py"], workspace, 120)
        result.update({"run_exit": executed.returncode, "stdout": executed.stdout[-6000:],
                       "stderr": executed.stderr[-6000:]})
    except subprocess.TimeoutExpired as exc:
        def text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            return value.decode(errors="replace") if isinstance(value, bytes) else value
        result.update({"run_exit": 124, "stdout": text(exc.stdout)[-6000:],
                       "stderr": text(exc.stderr)[-6000:]})
    return result


def payload_text(envelope: dict[str, Any]) -> str:
    return "\n".join(x.get("text", "") for x in envelope.get("result", {}).get("payloads", [])
                       if isinstance(x, dict))


def parse_score(envelope: dict[str, Any]) -> dict[str, int]:
    keys = ("instruction_following", "executability", "consistency", "quality")
    for candidate in reversed(re.findall(r"\{[^{}]+\}", payload_text(envelope), re.DOTALL)):
        try:
            score = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if all(k in score for k in keys):
            return {k: int(score[k]) for k in keys}
    raise ValueError("No task score object")


def immutable_input(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o444)
    return hashlib.sha256(text.encode()).hexdigest()


def safe_call(workspace: Path, *args: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return call_agent(workspace, *args), None
    except Exception as exc:
        with (workspace / "stage_failures.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": time.time(), "error": repr(exc), "args": list(args)[2:4]}) + "\n")
        return None, repr(exc)


def run_one(root: Path, item: dict[str, Any], condition: str, repetition: int) -> dict[str, Any]:
    run_started = time.time()
    task_id = int(item["task_id"])
    run_id = f"sparse-{condition.lower()}-t{task_id:02d}-r{repetition}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    workspace = root / condition / f"task_{task_id:02d}" / f"rep_{repetition:02d}" / run_id
    workspace.mkdir(parents=True, exist_ok=False)
    hashes = {
        "TASK.md": immutable_input(workspace / "TASK.md", "# Official coding task\n\n" + item["task"]["content"] + "\n"),
        "official_task.json": immutable_input(workspace / "official_task.json", json.dumps(item, indent=2) + "\n"),
        "AGENTS.md": immutable_input(workspace / "AGENTS.md", AGENTS_TEXT),
    }
    (workspace / "input_manifest.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    agent_id = f"mab-sparse-{condition.lower()}-t{task_id:02d}-r{repetition}-{uuid.uuid4().hex[:6]}"
    ensure_agent(agent_id, workspace)

    bank_path = workspace / "interface_memory.json"
    extractor = None
    extractor_error = None
    if condition == "X2":
        extractor, extractor_error = safe_call(workspace, agent_id, run_id + "-interface-generator",
                                                BOUNDARY_EXTRACTOR_PROMPT, "interface_generator")
        bank = load_or_empty(bank_path, task_id, run_id)
        save_bank(bank_path, bank)
        planner_prompt = PLANNER_PROMPT
    else:
        planner_prompt = (BASELINE_PLANNER_PROMPT if condition == "X8" else
                          X4_PLANNER_PROMPT if condition in {"X4", "X6"} else X3_PLANNER_PROMPT)
        if condition == "X7":
            planner_prompt += "\n\n" + render_patterns(retrieve_patterns(item["task"]["content"]))
    planner, planner_error = safe_call(workspace, agent_id, run_id + "-planner", planner_prompt, "planner")
    bank = load_or_empty(bank_path, task_id, run_id)
    save_bank(bank_path, bank)
    inventory = coverage_summary(bank)
    implementation_memory = (
        "\n\n".join(x for x in (inventory, compact_view(bank, "implementer", limit=2)) if x)
        if condition == "X4" else compact_view(bank, "implementer", limit=1)
    )
    if condition == "X8":
        implementation_memory = ""
    selected_patterns = retrieve_patterns(item["task"]["content"])
    if condition == "X7":
        implementation_memory = "\n\n".join(x for x in (render_patterns(selected_patterns), implementation_memory) if x)
    implementer_prompt = IMPLEMENTER_PROMPT + (("\n\n" + implementation_memory) if implementation_memory else "")
    (workspace / "implementer_interface_memory.txt").write_text(implementation_memory, encoding="utf-8")
    implementer1, impl_error = safe_call(workspace, agent_id, run_id + "-implementer", implementer_prompt, "implementer_pass1")
    impl_verification = verify_solution(workspace)
    impl_blocker = fail_open_observe(
        observe_blocker, error_log=workspace / "memory_errors.jsonl", workspace=workspace,
        task_id=task_id, run_id=run_id, role="implementer", stage="implementation",
        hook="after_first_pass", verification=impl_verification, stage_meta=stage_meta(implementer1),
    )
    append_event(workspace / "memory_events.jsonl", impl_blocker, condition=condition, hook="after_implementer_pass1")
    implementer2 = None
    impl_recovery_text = ""
    if impl_blocker:
        try:
            impl_recovery_text = recovery_prompt(impl_blocker, "M3" if condition in {"X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8"} else condition)
        except Exception as exc:
            impl_recovery_text = recovery_prompt(impl_blocker, "C0")
            try:
                with (workspace / "memory_errors.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"error": repr(exc), "fallback": "C0_prompt"}) + "\n")
            except Exception:
                pass
        (workspace / "implementer_recovery_prompt.txt").write_text(impl_recovery_text, encoding="utf-8")
        implementer2, _ = safe_call(workspace, agent_id, run_id + "-implementer",
                                    impl_recovery_text, "implementer_recovery")
        impl_verification = verify_solution(workspace)

    scaffold_origin = bool(impl_blocker and impl_blocker.blocker_type == "artifact_missing" and implementer2)

    integration = None
    integration_error = None
    if condition == "X6" and (workspace / "solution.py").is_file():
        integration_memory = compact_view(bank, "reviewer", limit=1)
        integration_prompt = INTEGRATION_PROMPT + (("\n\n" + integration_memory) if integration_memory else "")
        (workspace / "integration_interface_memory.txt").write_text(integration_memory, encoding="utf-8")
        integration, integration_error = safe_call(workspace, agent_id, run_id + "-integration",
                                                     integration_prompt, "integration")
    elif condition == "X8" and (workspace / "solution.py").is_file():
        integration, integration_error = safe_call(workspace, agent_id, run_id + "-integration",
                                                     POSTHOC_INTEGRATION_PROMPT, "integration")
        bank = load_or_empty(bank_path, task_id, run_id)
        save_bank(bank_path, bank)

    # Reviewer first pass is deliberately identical in C0 and M1 and always runs.
    review_memory = (
        "\n\n".join(x for x in (inventory, compact_view(bank, "reviewer", limit=3)) if x)
        if condition == "X4" else compact_view(bank, "reviewer", limit=3)
    )
    if condition == "X7":
        review_memory = "\n\n".join(x for x in (render_patterns(selected_patterns), review_memory) if x)
    strict_audit_instruction = """\n\nCROSS-DOMAIN COVERAGE AND FIDELITY GATE
Reread every TASK.md requirement before approving. Identify required domain/technology crossings omitted from interface memory, and repair material omissions. A class name, hard-coded table, data-only placeholder, function that always returns None, manual call labeled real-time, or isolated unit test is not sufficient integration evidence. For multi-user behavior, verify state propagation for every affected participant, not only the owner.

Create interface_audit.json as valid JSON: {\"interfaces\": [{\"interface_id\": \"exact ID from memory\", \"passed\": true, \"evidence\": [\"exact test/observation\"], \"blocker\": null}], \"uncovered_task_boundaries\": [{\"task_evidence\": \"requirement\", \"status\": \"repaired or failed\", \"evidence\": \"exact observation\"}]}. Do not mark a boundary passed from class names or isolated unit tests; exercise its real producer-to-consumer path."""
    basic_audit_instruction = """\n\nCreate interface_audit.json as valid JSON: {\"interfaces\": [{\"interface_id\": \"exact ID from memory\", \"passed\": true, \"evidence\": [\"exact test/observation\"], \"blocker\": null}]}. Do not mark a boundary passed from class names or isolated unit tests; exercise its real producer-to-consumer path."""
    audit_instruction = strict_audit_instruction if condition in {"X4", "X5"} else basic_audit_instruction
    reviewer_prompt = REVIEWER_PROMPT + (("\n\n" + review_memory + audit_instruction) if review_memory else "")
    (workspace / "reviewer_interface_memory.txt").write_text(review_memory, encoding="utf-8")
    reviewer1, review_error = safe_call(workspace, agent_id, run_id + "-reviewer", reviewer_prompt, "reviewer_pass1")
    review_verification = verify_solution(workspace)
    review_blocker = fail_open_observe(
        observe_blocker, error_log=workspace / "memory_errors.jsonl", workspace=workspace,
        task_id=task_id, run_id=run_id, role="reviewer", stage="review",
        hook="after_first_pass", verification=review_verification, stage_meta=stage_meta(reviewer1),
        scaffold_origin=scaffold_origin,
    )
    append_event(workspace / "memory_events.jsonl", review_blocker, condition=condition, hook="after_reviewer_pass1")
    reviewer2 = None
    review_recovery_text = ""
    if review_blocker:
        try:
            review_recovery_text = recovery_prompt(review_blocker, "M3" if condition in {"X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8"} else condition)
        except Exception as exc:
            review_recovery_text = recovery_prompt(review_blocker, "C0")
            try:
                with (workspace / "memory_errors.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"error": repr(exc), "fallback": "C0_prompt"}) + "\n")
            except Exception:
                pass
        (workspace / "reviewer_recovery_prompt.txt").write_text(review_recovery_text, encoding="utf-8")
        reviewer2, _ = safe_call(workspace, agent_id, run_id + "-reviewer",
                                 review_recovery_text, "reviewer_recovery")
        review_verification = verify_solution(workspace)

    interface_summary = summarize_audit(workspace / "interface_audit.json", bank)
    save_bank(bank_path, bank)

    judge, judge_error = safe_call(workspace, agent_id, run_id + "-judge", JUDGE_PROMPT, "task_score")
    try:
        scores = parse_score(judge) if judge else {k: 1 for k in ("instruction_following", "executability", "consistency", "quality")}
        score_valid = judge is not None
    except Exception:
        scores = {k: 1 for k in ("instruction_following", "executability", "consistency", "quality")}
        score_valid = False
    required = {name: (workspace / name).is_file()
                for name in ("plan.md", "solution.py", "implementation.md", "review.md")}
    result = {
        "task_id": task_id, "condition": condition, "repetition": repetition,
        "run_id": run_id, "workspace": str(workspace), "model": MODEL,
        "objective": review_verification, "task_scores": {**scores, "percentage": sum(scores.values()) * 5},
        "score_valid": score_valid,
        "required_artifacts": required, "workflow_complete": all(required.values()),
        "triggers": {"implementer": impl_blocker.to_dict() if impl_blocker else None,
                     "reviewer": review_blocker.to_dict() if review_blocker else None},
        "recovery_calls": {"implementer": implementer2 is not None, "reviewer": reviewer2 is not None},
        "interface_memory": interface_summary,
        "interface_patterns": [item["id"] for item in selected_patterns] if condition == "X7" else [],
        "injection": {"implementer_chars": len(impl_recovery_text),
                      "reviewer_chars": len(review_recovery_text),
                      "total_chars": len(impl_recovery_text) + len(review_recovery_text)},
        "stage_meta": {"interface_generator": stage_meta(extractor), "planner": stage_meta(planner), "implementer_pass1": stage_meta(implementer1),
                       "implementer_recovery": stage_meta(implementer2), "integration": stage_meta(integration),
                       "reviewer_pass1": stage_meta(reviewer1), "reviewer_recovery": stage_meta(reviewer2), "judge": stage_meta(judge)},
        "wall_time_seconds": time.time() - run_started,
        "stage_errors": {"interface_generator": extractor_error, "planner": planner_error, "implementer": impl_error,
                         "integration": integration_error, "reviewer": review_error, "judge": judge_error},
        "input_hashes": hashes,
    }
    (workspace / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default=",".join(map(str, DEFAULT_PANEL)), help="e.g. 1,2,5,15,17 or 1-5")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--condition", choices=("C0", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8"), default="X8")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dataset = load_tasks()
    conditions = [args.condition]
    results = []
    failures = []
    for repetition in range(1, args.repetitions + 1):
        for task_id in parse_task_ids(args.tasks):
            ordered_conditions = conditions
            for condition in ordered_conditions:
                try:
                    result = run_one(root, dataset[task_id], condition, repetition)
                    results.append(result)
                    print(f"{condition} task={task_id} rep={repetition} score={result['task_scores']['percentage']} workflow={result['workflow_complete']}", flush=True)
                except Exception as exc:
                    failures.append({"condition": condition, "task_id": task_id,
                                     "repetition": repetition, "error": repr(exc)})
                    print(f"{condition} task={task_id} rep={repetition} FAILED {exc}", flush=True)
    summary = {"runs": len(results), "failures": failures,
               "mean_score": sum(x["task_scores"]["percentage"] for x in results) / len(results) if results else None,
               "workflow_complete": sum(x["workflow_complete"] for x in results)}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
