#!/usr/bin/env python3
"""Run MultiAgentBench coding tasks with automatically generated dependency memory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from dependency_memory import DependencyMemoryStore, UNRESOLVED


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "memory_batch_01_20_v3"
DATASET = Path("coding_main.jsonl")
WORKFLOW_PATH = HERE / "multiagentbench_coding_workflow.yaml"
EXTRACTOR = HERE / "extract_contracts.py"
MODEL = "deepseek/deepseek-v4-flash"
AGENTS_TEXT = """# Memory-enabled MultiAgentBench coding run

Treat TASK.md as the sole product specification. Do not use MARBLE, MARBLE profiles,
MARBLE actions, or previous task results. Work in files, use Python's standard library,
keep behavior deterministic, and never claim tests passed without running them.
Dependency checkpoints are private operational memory. Resolve them using actual files
and execution evidence; do not merely repeat them in chat.
"""


def run(command: list[str], cwd: Path, timeout: int = 660) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def tasks() -> dict[int, dict[str, Any]]:
    return {
        int(item["task_id"]): item
        for item in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def ensure_agent(agent_id: str, workspace: Path) -> None:
    proc = run([
        "openclaw", "agents", "add", agent_id, "--non-interactive",
        "--workspace", str(workspace), "--model", MODEL, "--json",
    ], workspace, 120)
    (workspace / "agent_add.stdout").write_text(proc.stdout, encoding="utf-8")
    (workspace / "agent_add.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(proc.stderr or proc.stdout)
    for _ in range(30):
        listed = run(["openclaw", "agents", "list", "--json"], workspace, 60)
        if listed.returncode == 0:
            try:
                if any(item.get("id") == agent_id for item in json.loads(listed.stdout)):
                    time.sleep(5)
                    return
            except json.JSONDecodeError:
                pass
        time.sleep(1)
    raise RuntimeError(f"Agent {agent_id} was not discoverable")


def call_agent(workspace: Path, agent_id: str, session: str, message: str, label: str) -> dict:
    proc = None
    for attempt in range(1, 7):
        proc = run([
            "openclaw", "agent", "--agent", agent_id, "--session-id", session,
            "--model", MODEL, "--thinking", "off", "--timeout", "600",
            "--json", "--message", message,
        ], workspace)
        (workspace / f"{label}.attempt_{attempt}.stderr").write_text(proc.stderr, encoding="utf-8")
        if "unknown agent id" not in (proc.stderr or "").lower():
            break
        time.sleep(5 * attempt)
    assert proc is not None
    (workspace / f"{label}.stdout.json").write_text(proc.stdout, encoding="utf-8")
    (workspace / f"{label}.stderr").write_text(proc.stderr, encoding="utf-8")
    (workspace / f"{label}.exit").write_text(str(proc.returncode) + "\n", encoding="utf-8")
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr or f"{label} returned no output")
    envelope = json.loads(proc.stdout)
    if envelope.get("status") != "ok":
        raise RuntimeError(f"{label} returned non-ok")
    return envelope


def payload_text(envelope: dict) -> str:
    return "\n".join(
        item.get("text", "") for item in envelope.get("result", {}).get("payloads", [])
        if isinstance(item, dict)
    )


def stage_meta(envelope: dict | None) -> dict:
    if not envelope:
        return {}
    meta = envelope.get("result", {}).get("meta", {})
    return {
        "duration_ms": meta.get("durationMs"),
        "usage": meta.get("agentMeta", {}).get("usage", {}),
        "tool_summary": meta.get("toolSummary", {}),
    }


def verify_solution(workspace: Path) -> dict:
    solution = workspace / "solution.py"
    if not solution.exists():
        return {"compile_exit": None, "run_exit": None, "error": "solution.py missing"}
    compile_proc = run([sys.executable, "-m", "py_compile", "solution.py"], workspace, 30)
    try:
        execute = run([sys.executable, "solution.py"], workspace, 120)
        return {
            "compile_exit": compile_proc.returncode,
            "run_exit": execute.returncode,
            "stdout": execute.stdout[-6000:],
            "stderr": execute.stderr[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        def text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            return value.decode(errors="replace") if isinstance(value, bytes) else value
        return {
            "compile_exit": compile_proc.returncode,
            "run_exit": 124,
            "stdout": text(exc.stdout)[-6000:],
            "stderr": text(exc.stderr)[-6000:],
        }


def parse_task_score(envelope: dict) -> dict[str, int]:
    keys = ("instruction_following", "executability", "consistency", "quality")
    for candidate in reversed(re.findall(r"\{[^{}]+\}", payload_text(envelope), re.DOTALL)):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if all(key in value for key in keys):
            return {key: int(value[key]) for key in keys}
    raise ValueError("No task score object")


def checkpoint(
    store: DependencyMemoryStore,
    *, task_id: int, run_id: str, role: str, stage: str, action: str, query: str,
    path: Path, limit: int = 8,
) -> tuple[list[dict], str]:
    selected = store.select(
        task_id=str(task_id), run_id=run_id, recipient_role=role, stage=stage,
        action=action, query=query, limit=limit,
    )
    projection = store.projection(selected)
    path.write_text(projection, encoding="utf-8")
    return selected, projection


def record_known_environment(store: DependencyMemoryStore, stage: str) -> None:
    for record in list(store.data["records"]):
        dep = record["dependency"]
        verification = record["contract"].get("verification") or {}
        command = verification.get("command")
        if dep.get("scope") != "environment" or command != "python3 --version":
            continue
        proc = run(["python3", "--version"], store.workspace, 30)
        store.record_observation(
            dependency_id=record["identity"]["dependency_id"],
            event_type="capability_result", passed=proc.returncode == 0,
            observed_state="available" if proc.returncode == 0 else "unavailable",
            evidence={"command": command, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
            stage=stage, event_id=f"python-runtime-{stage}",
        )


def reconcile_solution_verification(store: DependencyMemoryStore, result: dict, stage: str, event: str) -> None:
    for record in list(store.data["records"]):
        subject = record["dependency"]["subject"]
        verification = record["contract"].get("verification") or {}
        if verification.get("command") != "python3 solution.py":
            continue
        store.record_verification(
            dependency_id=record["identity"]["dependency_id"], command="python3 solution.py",
            exit_code=result.get("run_exit") if result.get("run_exit") is not None else 127,
            stdout=result.get("stdout", ""), stderr=result.get("stderr", result.get("error", "")),
            stage=stage, event_id=f"{event}-{record['identity']['dependency_id']}",
        )


def reconcile_handoffs(store: DependencyMemoryStore, producer_role: str, stage: str) -> None:
    """Resolve abstract handoff nodes from the readiness of their prerequisites."""
    for record in list(store.data["records"]):
        if record["dependency"]["type"] != "handoff":
            continue
        if record["dependency"]["producer"].get("role") != producer_role:
            continue
        prerequisite_results = []
        for item in record["dependency"].get("prerequisites", []):
            try:
                upstream = store._by_id(item["dependency_id"])
            except KeyError:
                prerequisite_results.append(False)
                continue
            required = item.get("required_state", "verified")
            status = upstream["state"]["status"]
            prerequisite_results.append(
                status == required or
                (required in {"available", "produced"} and upstream["state"]["readiness"])
            )
        passed = bool(prerequisite_results) and all(prerequisite_results)
        store.record_observation(
            dependency_id=record["identity"]["dependency_id"],
            event_type="interface_result", passed=passed,
            observed_state="handoff_ready" if passed else "handoff_blocked",
            evidence={
                "summary": "Handoff prerequisites satisfied" if passed else "Handoff prerequisites unresolved",
                "prerequisite_results": prerequisite_results,
            },
            stage=stage, event_id=f"handoff-{record['identity']['dependency_id']}-{int(time.time())}",
        )


def reconcile_completion_decisions(store: DependencyMemoryStore, stage: str) -> None:
    for record in list(store.data["records"]):
        if record["dependency"]["type"] != "decision":
            continue
        prerequisites = record["dependency"].get("prerequisites", [])
        states = []
        for item in prerequisites:
            try:
                upstream = store._by_id(item["dependency_id"])
            except KeyError:
                states.append(False)
                continue
            required = item.get("required_state", "verified")
            status = upstream["state"]["status"]
            states.append(
                status == required or
                (required == "available" and upstream["state"]["readiness"]) or
                (required == "produced" and upstream["state"]["artifact"].get("exists"))
            )
        passed = bool(prerequisites) and all(states)
        store.record_observation(
            dependency_id=record["identity"]["dependency_id"], event_type="decision_result",
            passed=passed, observed_state="approved" if passed else "blocked",
            evidence={"summary": "All prerequisite contracts satisfied" if passed else "Prerequisite contracts remain unresolved", "prerequisite_results": states},
            stage=stage, event_id=f"completion-decision-{int(time.time())}",
        )


def extract_contracts(root: Path, workspace: Path, task_id: int, run_id: str) -> Path:
    contract_input = workspace / "CONTRACT_INPUT.md"
    contract_input.write_text(
        (workspace / "TASK.md").read_text(encoding="utf-8")
        + "\n\n# Actual planner output\n\n"
        + (workspace / "plan.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    extraction_workspace = root / "contract_extractions" / f"task_{task_id:02d}_{run_id}"
    proc = run([
        sys.executable, str(EXTRACTOR), "--task", str(contract_input),
        "--workflow", str(WORKFLOW_PATH), "--output-dir", str(extraction_workspace),
        "--task-id", str(task_id), "--run-id", run_id,
    ], HERE, 900)
    (workspace / "contract_extractor.stdout").write_text(proc.stdout, encoding="utf-8")
    (workspace / "contract_extractor.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"Contract extraction failed: {proc.stdout[-2000:]} {proc.stderr[-2000:]}")
    source = extraction_workspace / "compiled_dependency_memory.yaml"
    if not source.exists():
        raise RuntimeError("Extractor succeeded without compiled memory")
    destination = workspace / "dependency_memory.yaml"
    shutil.copy2(source, destination)
    shutil.copy2(extraction_workspace / "extracted_contracts.yaml", workspace / "extracted_contracts.yaml")
    if (extraction_workspace / "consolidation.json").exists():
        shutil.copy2(extraction_workspace / "consolidation.json", workspace / "consolidation.json")
    return destination


def run_task(root: Path, item: dict[str, Any]) -> dict:
    task_id = int(item["task_id"])
    workspace = root / f"task_{task_id:02d}"
    workspace.mkdir(parents=True, exist_ok=False)
    task_text = item["task"]["content"]
    (workspace / "TASK.md").write_text("# Official coding task\n\n" + task_text + "\n", encoding="utf-8")
    (workspace / "official_task.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
    (workspace / "AGENTS.md").write_text(AGENTS_TEXT, encoding="utf-8")
    run_id = f"depmem-{task_id:02d}-{int(time.time())}"
    agent_id = f"mab-depmem-t{task_id:02d}-{int(time.time())}"
    ensure_agent(agent_id, workspace)

    planner = call_agent(
        workspace, agent_id, run_id + "-planner",
        "Act as planner. Read TASK.md and AGENTS.md. Write plan.md covering architecture, every requirement, dependencies, deterministic tests, and edge cases. Do not implement code. Keep chat under five lines.",
        "planner",
    )
    memory_path = extract_contracts(root, workspace, task_id, run_id)
    store = DependencyMemoryStore(workspace, memory_path)
    store.load()
    store.observe_files(stage="implementation", event_id="after-planning")
    record_known_environment(store, "implementation")
    reconcile_handoffs(store, "planner", "implementation")

    impl_selected, impl_projection = checkpoint(
        store, task_id=task_id, run_id=run_id, role="implementer", stage="implementation",
        action="create", query="What prerequisites, artifacts, interfaces, and verified results must I produce before implementation handoff?",
        path=workspace / "implementer_start_checkpoint.yaml",
    )
    impl_session = run_id + "-implementer"
    implementer1 = call_agent(
        workspace, agent_id, impl_session,
        "Act as implementer. Read TASK.md, AGENTS.md, and plan.md. Create a complete self-contained solution.py with deterministic executable tests. Run python3 solution.py and fix failures. Write implementation.md with the exact command and result. Keep chat under five lines.\n\nPRIVATE DEPENDENCY MEMORY:\n" + impl_projection,
        "implementer_pass1",
    )
    store.observe_files(stage="implementation", event_id="after-implementer-pass1")
    objective_impl = verify_solution(workspace)
    reconcile_solution_verification(store, objective_impl, "implementation", "implementer-pass1-verification")
    store.observe_files(stage="implementation", event_id="after-implementer-verification")
    reconcile_handoffs(store, "implementer", "implementation")
    impl_final_selected, impl_final_projection = checkpoint(
        store, task_id=task_id, run_id=run_id, role="implementer", stage="implementation",
        action="finalize", query="Which required implementation and handoff obligations remain unresolved before I finish?",
        path=workspace / "implementer_final_checkpoint.yaml",
    )
    implementer2 = None
    if impl_final_selected:
        implementer2 = call_agent(
            workspace, agent_id, impl_session,
            "Continue the implementation. The memory service observed actual artifacts and verification results. Resolve every checkpoint below using bounded writes and rerun verification before finishing.\n\n" + impl_final_projection,
            "implementer_pass2",
        )
        store.observe_files(stage="implementation", event_id="after-implementer-pass2")
        objective_impl = verify_solution(workspace)
        reconcile_solution_verification(store, objective_impl, "implementation", "implementer-pass2-verification")
        store.observe_files(stage="review", event_id="implementation-handoff")
        reconcile_handoffs(store, "implementer", "review")

    review_selected, review_projection = checkpoint(
        store, task_id=task_id, run_id=run_id, role="reviewer", stage="review",
        action="review", query="What upstream artifacts, interfaces, and verification evidence must I consume or recover before review?",
        path=workspace / "reviewer_start_checkpoint.yaml",
    )
    review_session = run_id + "-reviewer"
    reviewer1 = call_agent(
        workspace, agent_id, review_session,
        "Act as independent reviewer. Read TASK.md, AGENTS.md, plan.md, solution.py, and implementation.md when present. Check every requirement and edge case. Run python3 solution.py. Repair solution.py if needed, add reviewer tests where useful, rerun, and write review.md with exact results. You have recovery authority for missing handoff artifacts. Keep chat under five lines.\n\nPRIVATE DEPENDENCY MEMORY:\n" + review_projection,
        "reviewer_pass1",
    )
    store.observe_files(stage="review", event_id="after-reviewer-pass1")
    objective_review = verify_solution(workspace)
    reconcile_solution_verification(store, objective_review, "review", "reviewer-pass1-verification")
    store.observe_files(stage="review", event_id="after-reviewer-verification")
    reconcile_handoffs(store, "implementer", "review")
    reconcile_completion_decisions(store, "review")
    review_final_selected, review_final_projection = checkpoint(
        store, task_id=task_id, run_id=run_id, role="reviewer", stage="review",
        action="finalize", query="Which required outputs, dependency contracts, and handoff obligations remain unresolved before workflow completion?",
        path=workspace / "reviewer_final_checkpoint.yaml",
    )
    reviewer2 = None
    if review_final_selected:
        reviewer2 = call_agent(
            workspace, agent_id, review_session,
            "Continue the same review. Resolve every dependency checkpoint below. Persist missing reports, repair current artifacts, rerun required commands, and record exact results before finishing.\n\n" + review_final_projection,
            "reviewer_pass2",
        )
        store.observe_files(stage="review", event_id="after-reviewer-pass2")
        objective_review = verify_solution(workspace)
        reconcile_solution_verification(store, objective_review, "review", "reviewer-pass2-verification")
        store.observe_files(stage="review", event_id="final-artifact-snapshot")
        reconcile_completion_decisions(store, "review")

    judge = call_agent(
        workspace, agent_id, run_id + "-judge",
        "Read TASK.md and solution.py. Score strictly: instruction_following, executability, consistency, quality, each integer 1-5. Deduct for every missing or partial requirement. Do not modify files. Output only one JSON object with those four keys.",
        "task_score",
    )
    scores = parse_task_score(judge)
    final_memory = DependencyMemoryStore(workspace, memory_path)
    final_memory.load()
    unresolved = final_memory.unresolved()
    required_files = ("plan.md", "solution.py", "implementation.md", "review.md")
    result = {
        "task_id": task_id,
        "run_id": run_id,
        "model": MODEL,
        "objective": objective_review,
        "task_scores": {**scores, "mean": sum(scores.values()) / 4, "percentage": sum(scores.values()) * 5},
        "required_artifacts": {name: (workspace / name).exists() for name in required_files},
        "workflow_complete": all((workspace / name).exists() for name in required_files),
        "dependency_records": len(final_memory.data["records"]),
        "unresolved_dependency_ids": [r["identity"]["dependency_id"] for r in unresolved],
        "memory_selection": {
            "implementer_start": [r["identity"]["dependency_id"] for r in impl_selected],
            "implementer_final": [r["identity"]["dependency_id"] for r in impl_final_selected],
            "reviewer_start": [r["identity"]["dependency_id"] for r in review_selected],
            "reviewer_final": [r["identity"]["dependency_id"] for r in review_final_selected],
        },
        "stage_meta": {
            "planner": stage_meta(planner), "implementer_pass1": stage_meta(implementer1),
            "implementer_pass2": stage_meta(implementer2), "reviewer_pass1": stage_meta(reviewer1),
            "reviewer_pass2": stage_meta(reviewer2), "judge": stage_meta(judge),
        },
        "comparability": "memory-enabled adapted workflow; not leaderboard-comparable",
    }
    (workspace / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def aggregate(root: Path) -> dict:
    rows = []
    for path in sorted(root.glob("task_*/result.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    summary = {
        "completed": len(rows),
        "task_ids": [row["task_id"] for row in rows],
        "workflow_complete": sum(row["workflow_complete"] for row in rows),
        "compile_pass": sum(row["objective"].get("compile_exit") == 0 for row in rows),
        "run_pass": sum(row["objective"].get("run_exit") == 0 for row in rows),
        "mean_task_percentage": sum(row["task_scores"]["percentage"] for row in rows) / len(rows) if rows else None,
        "tasks_with_unresolved_memory": sum(bool(row["unresolved_dependency_ids"]) for row in rows),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    global DATASET, MODEL
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=20)
    args = parser.parse_args()
    DATASET = args.dataset.expanduser().resolve()
    MODEL = args.model
    root = args.root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dataset = tasks()
    failures = []
    for task_id in range(args.start, args.end + 1):
        result_path = root / f"task_{task_id:02d}" / "result.json"
        if result_path.exists():
            print(f"TASK {task_id}: already complete", flush=True)
            continue
        print(f"TASK {task_id}: starting", flush=True)
        try:
            result = run_task(root, dataset[task_id])
            print(
                f"TASK {task_id}: done workflow={result['workflow_complete']} "
                f"run={result['objective'].get('run_exit')} score={result['task_scores']['percentage']:.0f}%",
                flush=True,
            )
        except Exception as exc:
            failure = {"task_id": task_id, "error": repr(exc), "time": time.time()}
            failures.append(failure)
            failure_path = root / f"task_{task_id:02d}" / "failure.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
            print(f"TASK {task_id}: FAILED {exc}", flush=True)
        aggregate(root)
    (root / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate(root), indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
