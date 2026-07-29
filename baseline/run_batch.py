#!/usr/bin/env python3
"""Run official MultiAgentBench coding tasks through clean native OpenClaw workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("runs/baseline")
DATASET = Path("coding_main.jsonl")
MODEL = "deepseek/deepseek-v4-flash"
AGENTS_TEXT = """# Clean MultiAgentBench coding run

Treat TASK.md as the sole product specification. Do not use MARBLE, MARBLE profiles,
MARBLE actions, or previous task results. Work in files, use Python's standard library,
keep behavior deterministic, and never claim tests passed without running them.
"""


def load_tasks() -> dict[int, dict]:
    return {
        int(item["task_id"]): item
        for item in (
            json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    }


def run(command: list[str], cwd: Path, timeout: int = 660) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def agent_exists(agent_id: str) -> bool:
    proc = run(["openclaw", "agents", "list", "--json"], ROOT, 60)
    if proc.returncode:
        return False
    return any(item.get("id") == agent_id for item in json.loads(proc.stdout))


def ensure_agent(agent_id: str, workspace: Path) -> None:
    if agent_exists(agent_id):
        return
    proc = run(
        [
            "openclaw", "agents", "add", agent_id, "--non-interactive",
            "--workspace", str(workspace), "--model", MODEL, "--json",
        ],
        ROOT, 120,
    )
    (workspace / "agent_add.stdout").write_text(proc.stdout, encoding="utf-8")
    (workspace / "agent_add.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"Agent registration failed: {proc.stderr or proc.stdout}")


def call_agent(workspace: Path, agent_id: str, session: str, message: str, label: str) -> dict:
    proc = run(
        [
            "openclaw", "agent", "--agent", agent_id, "--session-id", session,
            "--model", MODEL, "--thinking", "off", "--timeout", "600",
            "--json", "--message", message,
        ],
        workspace,
    )
    (workspace / f"{label}.stdout.json").write_text(proc.stdout, encoding="utf-8")
    (workspace / f"{label}.stderr").write_text(proc.stderr, encoding="utf-8")
    (workspace / f"{label}.exit").write_text(str(proc.returncode) + "\n", encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{label} failed: {proc.stderr or proc.stdout}")
    data = json.loads(proc.stdout)
    if data.get("status") != "ok":
        raise RuntimeError(f"{label} returned non-ok envelope")
    return data


def meta(envelope: dict) -> dict:
    data = envelope.get("result", {}).get("meta", {})
    return {
        "duration_ms": data.get("durationMs"),
        "usage": data.get("agentMeta", {}).get("usage", {}),
        "tool_summary": data.get("toolSummary", {}),
        "fallback_used": data.get("executionTrace", {}).get("fallbackUsed"),
    }


def payload_text(envelope: dict) -> str:
    return "\n".join(
        item.get("text", "")
        for item in envelope.get("result", {}).get("payloads", [])
        if isinstance(item, dict)
    )


def parse_rating(envelope: dict) -> int:
    matches = re.findall(r'\{\s*"rating"\s*:\s*([1-5])\s*\}', payload_text(envelope))
    if not matches:
        raise ValueError("No rating object")
    return int(matches[-1])


def parse_task_score(envelope: dict) -> dict[str, int]:
    text = payload_text(envelope)
    objects = re.findall(r"\{[^{}]+\}", text, re.DOTALL)
    keys = ("instruction_following", "executability", "consistency", "quality")
    for candidate in reversed(objects):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if all(key in data for key in keys):
            scores = {key: int(data[key]) for key in keys}
            if all(1 <= value <= 5 for value in scores.values()):
                return scores
    raise ValueError("No valid task score object")


def verify(workspace: Path) -> dict:
    solution = workspace / "solution.py"
    if not solution.exists():
        return {"compile_exit": None, "run_exit": None, "error": "solution.py missing"}
    compile_run = run([sys.executable, "-m", "py_compile", "solution.py"], workspace, 30)
    try:
        execution = run([sys.executable, "solution.py"], workspace, 120)
        return {
            "compile_exit": compile_run.returncode,
            "run_exit": execution.returncode,
            "stdout": execution.stdout[-12000:],
            "stderr": execution.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "compile_exit": compile_run.returncode, "run_exit": 124,
            "stdout": (exc.stdout or "")[-12000:], "stderr": (exc.stderr or "")[-12000:],
        }


def task_score_message() -> str:
    return """Read TASK.md and solution.py. Score the solution strictly using exactly these MultiAgentBench coding criteria: (1) Instruction-Following: fulfillment of every task requirement; deduct for every unmet or partial requirement. (2) Executability: syntax, imports, and runtime correctness. (3) Consistency: naming, formatting, and logical consistency. (4) Quality: documentation, clarity, and modularity. Scores: 1 Below Average/significant issues; 2 Average/noticeable improvements; 3 Good/minor improvements; 4 Excellent/almost or fully satisfies; 5 Legendary/flawless and exceeds expectations. Do not assign the same score to all four criteria. Output only one JSON object with integer keys instruction_following, executability, consistency, quality. Do not modify files."""


def coordination_prompts(workspace: Path, task: str) -> tuple[str, str]:
    plan = (workspace / "plan.md").read_text(encoding="utf-8", errors="replace")
    implementation = (workspace / "implementation.md").read_text(encoding="utf-8", errors="replace")
    review = (workspace / "review.md").read_text(encoding="utf-8", errors="replace")
    communications = (
        f"From planner to implementer via plan.md:\n{plan}\n\n"
        f"From implementer to reviewer via implementation.md and solution.py:\n{implementation}\n\n"
        f"From reviewer to team via review.md and reviewer tests:\n{review}"
    )
    communication = f"""[Context]
**Task:** {task}

**Communications:** {communications}

[System]
Evaluate communication quality between agents in the Graph structure. Focus on Information Exchange, Clarity, Task Assistance, and Efficiency. Rate 1-5: 1 poor with major failures; 2 significant clarity/relevance issues; 3 adequate but required clarification; 4 effective with minor improvements; 5 clear and effective, maximizing efficiency. Output ONLY {{"rating": X}}."""
    planning = f"""[Context]
**Summary:** Fresh three-stage run; no previous coordination round.

**Agent Profiles:** planner: architecture, requirements, dependencies, tests; implementer: implementation and initial executable tests; reviewer: independent audit, edge tests, repair authority.

**Agent Tasks:** planner creates the plan; implementer builds and tests; reviewer independently audits, adds edge tests, repairs if needed, and reruns.

**Results:** Planner:\n{plan}\n\nImplementer:\n{implementation}\n\nReviewer:\n{review}

[System]
Evaluate self-coordination in the Graph structure. Focus on Role Clarity, Task Alignment, and Autonomy. Rate 1-5: 1 very poor with major inefficiencies; 2 frequent role confusion; 3 moderate overlap/confusion; 4 effective with minor clarification needed; 5 clear roles and effective self-coordination. Output ONLY {{"rating": X}}."""
    (workspace / "communication_evaluator_prompt.md").write_text(communication, encoding="utf-8")
    (workspace / "planning_evaluator_prompt.md").write_text(planning, encoding="utf-8")
    return communication, planning


def run_task(item: dict, timeout: int) -> dict:
    task_id = int(item["task_id"])
    workspace = ROOT / f"task_{task_id:02d}"
    workspace.mkdir(parents=True, exist_ok=True)
    result_path = workspace / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    task = item["task"]["content"]
    (workspace / "TASK.md").write_text("# Official coding task\n\n" + task + "\n", encoding="utf-8")
    (workspace / "official_task.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
    (workspace / "AGENTS.md").write_text(AGENTS_TEXT, encoding="utf-8")
    agent_id = f"mab-clean-batch-t{task_id:02d}"
    ensure_agent(agent_id, workspace)
    prefix = f"mab-clean-batch-{task_id:02d}-{int(time.time())}"
    print(f"TASK {task_id}: planner", flush=True)
    planner = call_agent(
        workspace, agent_id, prefix + "-planner",
        "Act as planner. Read TASK.md and AGENTS.md. Write plan.md covering architecture, every requirement, dependencies, deterministic tests, and edge cases. Do not implement code. Keep chat under five lines.",
        "planner",
    )
    print(f"TASK {task_id}: implementer", flush=True)
    implementer = call_agent(
        workspace, agent_id, prefix + "-implementer",
        "Act as implementer. Read TASK.md, AGENTS.md, and plan.md. Create a complete self-contained solution.py with deterministic executable tests. Run python3 solution.py and fix failures. Write implementation.md with the exact command and result. Keep chat under five lines.",
        "implementer",
    )
    print(f"TASK {task_id}: reviewer", flush=True)
    reviewer = call_agent(
        workspace, agent_id, prefix + "-reviewer",
        "Act as independent reviewer. Read TASK.md, AGENTS.md, plan.md, solution.py, and implementation.md. Check every requirement and edge case. Run python3 solution.py. Repair solution.py if needed, add reviewer tests where useful, rerun, and write review.md with exact results. Keep chat under five lines.",
        "reviewer",
    )
    objective = verify(workspace)
    print(f"TASK {task_id}: task judge", flush=True)
    task_judge = call_agent(
        workspace, agent_id, prefix + "-task-judge", task_score_message(), "task_score"
    )
    task_scores = parse_task_score(task_judge)
    communication_prompt, planning_prompt = coordination_prompts(workspace, task)
    print(f"TASK {task_id}: communication judge", flush=True)
    communication_judge = call_agent(
        workspace, agent_id, prefix + "-communication-judge",
        "Read communication_evaluator_prompt.md, perform exactly that evaluation, do not modify files, and output only the requested JSON.",
        "communication_score",
    )
    print(f"TASK {task_id}: planning judge", flush=True)
    planning_judge = call_agent(
        workspace, agent_id, prefix + "-planning-judge",
        "Read planning_evaluator_prompt.md, perform exactly that evaluation, do not modify files, and output only the requested JSON.",
        "planning_score",
    )
    communication = parse_rating(communication_judge)
    planning = parse_rating(planning_judge)
    task_mean = sum(task_scores.values()) / 4
    result = {
        "task_id": task_id,
        "model": MODEL,
        "objective": objective,
        "task_scores": {**task_scores, "mean": task_mean, "percentage": task_mean * 20},
        "communication_score": communication,
        "planning_score": planning,
        "coordination_score": (communication + planning) / 2,
        "coordination_percentage": (communication + planning) * 10,
        "stage_meta": {
            "planner": meta(planner), "implementer": meta(implementer),
            "reviewer": meta(reviewer), "task_judge": meta(task_judge),
            "communication_judge": meta(communication_judge),
            "planning_judge": meta(planning_judge),
        },
        "comparability": "adapted; not leaderboard-comparable",
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def aggregate() -> None:
    rows = []
    for task_id in range(1, 11):
        path = ROOT / f"task_{task_id:02d}" / "result.json"
        if path.exists():
            rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        return
    summary = {
        "completed": len(rows),
        "task_ids": [row["task_id"] for row in rows],
        "objective_compile_pass": sum(row["objective"].get("compile_exit") == 0 for row in rows),
        "objective_run_pass": sum(row["objective"].get("run_exit") == 0 for row in rows),
        "mean_task_percentage": sum(row["task_scores"]["percentage"] for row in rows) / len(rows),
        "mean_coordination_percentage": sum(row["coordination_percentage"] for row in rows) / len(rows),
        "comparability": "adapted; not leaderboard-comparable",
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    global ROOT, DATASET, MODEL
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--start", type=int, default=2)
    parser.add_argument("--end", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=660)
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    DATASET = args.dataset.expanduser().resolve()
    MODEL = args.model
    ROOT.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    failures = []
    for task_id in range(args.start, args.end + 1):
        try:
            result = run_task(tasks[task_id], args.timeout)
            print(
                f"TASK {task_id}: done TS={result['task_scores']['percentage']:.0f}% "
                f"CS={result['coordination_percentage']:.0f}%", flush=True,
            )
        except Exception as exc:
            failures.append({"task_id": task_id, "error": repr(exc)})
            (ROOT / f"task_{task_id:02d}" / "failure.json").write_text(
                json.dumps(failures[-1], indent=2) + "\n", encoding="utf-8"
            )
            print(f"TASK {task_id}: FAILED {exc!r}", flush=True)
        aggregate()
    (ROOT / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
