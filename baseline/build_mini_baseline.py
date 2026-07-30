import json
from pathlib import Path

ROOT = Path("/home/luzh/mab_openclaw_clean_20260727")
RESULTS = []
for task_id in range(1, 21):
    batch = "batch_01_10" if task_id <= 10 else "batch_11_20"
    task_dir = f"task_{task_id:02d}" if task_id <= 10 else f"task_{task_id}"
    path = ROOT / batch / task_dir / "result.json"
    data = json.loads(path.read_text())
    obj = data["objective"]
    RESULTS.append({
        "task_id": task_id,
        "workflow_complete": data.get("workflow_complete", not data.get("missing_required_artifacts")),
        "missing_required_artifacts": data.get("missing_required_artifacts", []),
        "solution_produced": obj.get("compile_exit") is not None,
        "compile_pass": obj.get("compile_exit") == 0,
        "run_pass": obj.get("run_exit") == 0,
        "run_timeout": bool(obj.get("timed_out", False) or obj.get("run_timed_out", False) or obj.get("run_exit") == 124),
        "task_score": data["task_scores"]["percentage"],
        "adapted_coordination": data["coordination_percentage"],
    })

aggregate = {
    "tasks": len(RESULTS),
    "workflow_complete": sum(x["workflow_complete"] for x in RESULTS),
    "solutions_produced": sum(x["solution_produced"] for x in RESULTS),
    "compile_pass": sum(x["compile_pass"] for x in RESULTS),
    "run_pass": sum(x["run_pass"] for x in RESULTS),
    "run_timeout": sum(x["run_timeout"] for x in RESULTS),
    "mean_task_score": round(sum(x["task_score"] for x in RESULTS) / len(RESULTS), 1),
    "mean_adapted_coordination": round(sum(x["adapted_coordination"] for x in RESULTS) / len(RESULTS), 1),
}

payload = {
    "name": "MultiAgentBench coding mini-baseline (tasks 1-20)",
    "model": "deepseek/deepseek-v4-flash",
    "workflow": "OpenClaw planner -> implementer -> reviewer; independent execution and adapted MultiAgentBench judging",
    "comparability": "adapted; not leaderboard-comparable",
    "aggregate": aggregate,
    "results": RESULTS,
}
(ROOT / "mini_baseline_01_20.json").write_text(json.dumps(payload, indent=2) + "\n")

lines = [
    "# MultiAgentBench Coding Mini-Baseline (Tasks 1-20)",
    "",
    "- Model: `deepseek/deepseek-v4-flash`",
    "- Workflow: OpenClaw planner -> implementer -> reviewer",
    "- Attempts: one clean attempt per task; no selective retries",
    "- Scoring: MultiAgentBench task rubric plus adapted communication/planning judges",
    "- Comparability: adapted experiment; not leaderboard-comparable",
    "",
    "## Aggregate",
    "",
    f"- Workflow complete: {aggregate['workflow_complete']}/20",
    f"- Solutions produced: {aggregate['solutions_produced']}/20",
    f"- Compile pass: {aggregate['compile_pass']}/20",
    f"- Run pass: {aggregate['run_pass']}/20",
    f"- Run timeout: {aggregate['run_timeout']}/20",
    f"- Mean Task Score: {aggregate['mean_task_score']}%",
    f"- Mean adapted coordination: {aggregate['mean_adapted_coordination']}%",
    "",
    "## Per-task results",
    "",
    "| Task | Workflow | Solution | Compile | Run | Task Score | Adapted coordination | Missing handoff |",
    "|---:|---|---|---|---|---:|---:|---|",
]
for x in RESULTS:
    missing = ", ".join(x["missing_required_artifacts"]) or "-"
    run = "timeout" if x["run_timeout"] else ("pass" if x["run_pass"] else "fail")
    lines.append(
        f"| {x['task_id']} | {'complete' if x['workflow_complete'] else 'incomplete'} | "
        f"{'yes' if x['solution_produced'] else 'no'} | {'pass' if x['compile_pass'] else 'fail'} | "
        f"{run} | {x['task_score']:.0f}% | {x['adapted_coordination']:.0f}% | {missing} |"
    )
lines += [
    "",
    "## Interpretation",
    "",
    "`Workflow incomplete` means an agent failed to produce a required artifact or handoff. It does not mean the harness crashed. "
    "A solution can therefore compile and run while the workflow is still incomplete. `Run timeout` means the submitted program "
    "did not terminate within the independent execution limit.",
]
(ROOT / "MINI_BASELINE_01_20.md").write_text("\n".join(lines) + "\n")
print(json.dumps(aggregate, indent=2))
