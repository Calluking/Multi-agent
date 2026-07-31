#!/usr/bin/env python3
"""Run a 2x2 ablation of dependency and cross-domain memory mechanisms."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

import run_interface_panel as base
from interface_memory import compact_view, load_or_empty, save_bank, summarize_audit
from sparse_memory import append_event, fail_open_observe, observe_blocker, recovery_prompt


DEFAULT_ROOT = Path(__file__).resolve().parent / "runs_feature_ablation"
FEATURES = {
    "baseline": {"dependency": False, "codomain": False},
    "dependency": {"dependency": True, "codomain": False},
    "codomain": {"dependency": False, "codomain": True},
    "both": {"dependency": True, "codomain": True},
}


def safe_stage_call(workspace: Path, *args: Any):
    """Retry only transient provider saturation; preserve all other stage failures."""
    envelope = None
    error = None
    for attempt in range(1, 4):
        envelope, error = base.safe_call(workspace, *args)
        if envelope is not None or not error:
            return envelope, error
        lowered = error.lower()
        if "503" not in lowered and "too busy" not in lowered and "failovererror" not in lowered:
            return envelope, error
        with (workspace / "transient_retries.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"attempt": attempt, "error": error, "label": args[-1]}) + "\n")
        if attempt < 3:
            time.sleep(20 * attempt)
    return envelope, error


def observe_dependency(workspace: Path, *, enabled: bool, task_id: int, run_id: str,
                       role: str, stage: str, verification: dict[str, Any],
                       envelope: dict[str, Any] | None, scaffold_origin: bool = False):
    if not enabled:
        return None
    return fail_open_observe(
        observe_blocker,
        error_log=workspace / "memory_errors.jsonl",
        workspace=workspace,
        task_id=task_id,
        run_id=run_id,
        role=role,
        stage=stage,
        hook="after_first_pass",
        verification=verification,
        stage_meta=base.stage_meta(envelope),
        scaffold_origin=scaffold_origin,
    )


def recover_dependency(workspace: Path, *, enabled: bool, blocker, agent_id: str,
                       session: str, label: str):
    if not enabled or blocker is None:
        return None, "", None
    prompt = recovery_prompt(blocker, "M3")
    (workspace / f"{label}_prompt.txt").write_text(prompt, encoding="utf-8")
    envelope, error = safe_stage_call(workspace, agent_id, session, prompt, label)
    return envelope, prompt, error


def run_one(root: Path, item: dict[str, Any], condition: str, repetition: int) -> dict[str, Any]:
    features = FEATURES[condition]
    task_id = int(item["task_id"])
    started = time.time()
    run_id = f"ablation-{condition}-t{task_id:02d}-r{repetition}-{int(started)}-{uuid.uuid4().hex[:6]}"
    workspace = root / condition / f"task_{task_id:02d}" / f"rep_{repetition:02d}" / run_id
    workspace.mkdir(parents=True, exist_ok=False)
    hashes = {
        "TASK.md": base.immutable_input(workspace / "TASK.md", "# Official coding task\n\n" + item["task"]["content"] + "\n"),
        "official_task.json": base.immutable_input(workspace / "official_task.json", json.dumps(item, indent=2) + "\n"),
        "AGENTS.md": base.immutable_input(workspace / "AGENTS.md", base.AGENTS_TEXT),
    }
    (workspace / "input_manifest.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    (workspace / "feature_flags.json").write_text(json.dumps(features, indent=2) + "\n", encoding="utf-8")

    agent_id = f"mab-ablation-{condition}-t{task_id:02d}-{uuid.uuid4().hex[:6]}"
    base.ensure_agent(agent_id, workspace)
    planner, planner_error = safe_stage_call(
        workspace, agent_id, run_id + "-planner", base.BASELINE_PLANNER_PROMPT, "planner"
    )
    implementer1, impl_error = safe_stage_call(
        workspace, agent_id, run_id + "-implementer", base.IMPLEMENTER_PROMPT, "implementer_pass1"
    )
    impl_verification = base.verify_solution(workspace)
    impl_blocker = observe_dependency(
        workspace, enabled=features["dependency"], task_id=task_id, run_id=run_id,
        role="implementer", stage="implementation", verification=impl_verification,
        envelope=implementer1,
    )
    if features["dependency"]:
        append_event(workspace / "dependency_memory_events.jsonl", impl_blocker,
                     condition=condition, hook="after_implementer_pass1")
    implementer2, impl_recovery_text, impl_recovery_error = recover_dependency(
        workspace, enabled=features["dependency"], blocker=impl_blocker,
        agent_id=agent_id, session=run_id + "-implementer", label="implementer_recovery",
    )
    if implementer2:
        impl_verification = base.verify_solution(workspace)
    scaffold_origin = bool(impl_blocker and impl_blocker.blocker_type == "artifact_missing" and implementer2)

    bank_path = workspace / "interface_memory.json"
    integration = None
    integration_error = None
    if features["codomain"] and (workspace / "solution.py").is_file():
        integration, integration_error = safe_stage_call(
            workspace, agent_id, run_id + "-integration",
            base.POSTHOC_INTEGRATION_PROMPT, "codomain_integration",
        )
    bank = load_or_empty(bank_path, task_id, run_id)
    if features["codomain"]:
        save_bank(bank_path, bank)
    review_memory = compact_view(bank, "reviewer", limit=3) if features["codomain"] else ""
    audit = """

SHARED BOUNDARY AGREEMENT AUDIT
For each shared interface-memory record, exercise the real producer-to-consumer path. Repair semantic mismatches. Create interface_audit.json as valid JSON: {"interfaces": [{"interface_id": "exact ID", "passed": true, "evidence": ["exact observation"], "blocker": null}]}. Do not infer success from class names or isolated unit tests."""
    reviewer_prompt = base.REVIEWER_PROMPT + (("\n\n" + review_memory + audit) if review_memory else "")
    (workspace / "reviewer_interface_memory.txt").write_text(review_memory, encoding="utf-8")
    reviewer1, review_error = safe_stage_call(
        workspace, agent_id, run_id + "-reviewer", reviewer_prompt, "reviewer_pass1"
    )
    review_verification = base.verify_solution(workspace)
    review_blocker = observe_dependency(
        workspace, enabled=features["dependency"], task_id=task_id, run_id=run_id,
        role="reviewer", stage="review", verification=review_verification,
        envelope=reviewer1, scaffold_origin=scaffold_origin,
    )
    if features["dependency"]:
        append_event(workspace / "dependency_memory_events.jsonl", review_blocker,
                     condition=condition, hook="after_reviewer_pass1")
    reviewer2, review_recovery_text, review_recovery_error = recover_dependency(
        workspace, enabled=features["dependency"], blocker=review_blocker,
        agent_id=agent_id, session=run_id + "-reviewer", label="reviewer_recovery",
    )
    if reviewer2:
        review_verification = base.verify_solution(workspace)

    interface_summary = summarize_audit(workspace / "interface_audit.json", bank) if features["codomain"] else {
        "records": 0, "verified": 0, "failed": 0
    }
    if features["codomain"]:
        save_bank(bank_path, bank)

    judge, judge_error = safe_stage_call(
        workspace, agent_id, run_id + "-judge", base.JUDGE_PROMPT, "task_score"
    )
    try:
        scores = base.parse_score(judge) if judge else {k: 1 for k in ("instruction_following", "executability", "consistency", "quality")}
        score_valid = judge is not None
    except Exception:
        scores = {k: 1 for k in ("instruction_following", "executability", "consistency", "quality")}
        score_valid = False
    required = {name: (workspace / name).is_file() for name in ("plan.md", "solution.py", "implementation.md", "review.md")}
    result = {
        "task_id": task_id, "condition": condition, "features": features, "repetition": repetition,
        "run_id": run_id, "workspace": str(workspace), "model": base.MODEL,
        "objective": review_verification,
        "task_scores": {**scores, "mean": sum(scores.values()) / 4, "percentage": sum(scores.values()) * 5},
        "score_valid": score_valid, "required_artifacts": required,
        "workflow_complete": all(required.values()),
        "dependency_memory": {
            "implementer_blocker": impl_blocker.to_dict() if impl_blocker else None,
            "reviewer_blocker": review_blocker.to_dict() if review_blocker else None,
            "implementer_recovery": implementer2 is not None,
            "reviewer_recovery": reviewer2 is not None,
            "injected_chars": len(impl_recovery_text) + len(review_recovery_text),
        },
        "codomain_memory": {**interface_summary, "integration_called": integration is not None,
                            "review_injected_chars": len(review_memory)},
        "stage_meta": {
            "planner": base.stage_meta(planner), "implementer_pass1": base.stage_meta(implementer1),
            "implementer_recovery": base.stage_meta(implementer2), "codomain_integration": base.stage_meta(integration),
            "reviewer_pass1": base.stage_meta(reviewer1), "reviewer_recovery": base.stage_meta(reviewer2),
            "judge": base.stage_meta(judge),
        },
        "stage_errors": {
            "planner": planner_error, "implementer": impl_error, "implementer_recovery": impl_recovery_error,
            "codomain_integration": integration_error, "reviewer": review_error,
            "reviewer_recovery": review_recovery_error, "judge": judge_error,
        },
        "input_hashes": hashes, "wall_time_seconds": time.time() - started,
    }
    (workspace / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="1")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--condition", choices=(*FEATURES, "all"), default="all")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dataset = base.load_tasks()
    conditions = list(FEATURES) if args.condition == "all" else [args.condition]
    results, failures = [], []
    for repetition in range(1, args.repetitions + 1):
        for task_id in base.parse_task_ids(args.tasks):
            for condition in conditions:
                try:
                    result = run_one(root, dataset[task_id], condition, repetition)
                    results.append(result)
                    print(f"{condition} task={task_id} score={result['task_scores']['mean']:.2f}/5 "
                          f"workflow={result['workflow_complete']}", flush=True)
                except Exception as exc:
                    failure = {"condition": condition, "task_id": task_id, "repetition": repetition, "error": repr(exc)}
                    failures.append(failure)
                    print(f"{condition} task={task_id} FAILED {exc}", flush=True)
    summary = {"features": FEATURES, "runs": results, "failures": failures}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
