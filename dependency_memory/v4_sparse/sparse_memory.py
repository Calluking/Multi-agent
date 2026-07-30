#!/usr/bin/env python3
"""Sparse, event-grounded recovery memory for the v4 experiment.

This module deliberately models only the single current operational blocker.  It
does not infer a task DAG or use unresolved memory as a workflow-completion gate.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Blocker:
    schema_version: str
    blocker_id: str
    task_id: int
    run_id: str
    recipient_role: str
    stage: str
    hook: str
    blocker_type: str
    subject: str
    expected: str
    observed: str
    priority: int
    evidence: dict[str, Any]
    recovery_target: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blocker(
    *, task_id: int, run_id: str, role: str, stage: str, hook: str,
    blocker_type: str, subject: str, expected: str, observed: str,
    priority: int, evidence: dict[str, Any], recovery_target: str,
) -> Blocker:
    return Blocker(
        schema_version="0.4",
        blocker_id=f"recovery:{run_id}:{role}:{blocker_type}:{subject}",
        task_id=task_id,
        run_id=run_id,
        recipient_role=role,
        stage=stage,
        hook=hook,
        blocker_type=blocker_type,
        subject=subject,
        expected=expected,
        observed=observed,
        priority=priority,
        evidence=evidence,
        recovery_target=recovery_target,
        created_at=utc_now(),
    )


def observe_blocker(
    *, workspace: Path, task_id: int, run_id: str, role: str,
    stage: str, hook: str, verification: dict[str, Any],
    stage_meta: dict[str, Any] | None = None, scaffold_origin: bool = False,
) -> Blocker | None:
    """Return exactly one deterministic blocker using fixed priority order."""
    solution = workspace / "solution.py"
    report_name = "implementation.md" if role == "implementer" else "review.md"
    evidence_base = {"source": "runner", **(stage_meta or {})}

    if not solution.is_file():
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="artifact_missing", subject="solution.py", priority=100,
            expected="solution.py exists and is executable", observed="solution.py is absent",
            evidence={**evidence_base, "writes_observed": 0},
            recovery_target="persist_minimal_runnable_artifact",
        )
    if verification.get("compile_exit") not in (None, 0):
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="compile_failure", subject="solution.py", priority=90,
            expected="python -m py_compile solution.py exits 0",
            observed=f"compile exited {verification.get('compile_exit')}",
            evidence={**evidence_base, "command": "python -m py_compile solution.py",
                      "exit_code": verification.get("compile_exit"),
                      "error_excerpt": verification.get("compile_stderr", "")[-1200:]},
            recovery_target="repair_smallest_compile_dependency",
        )
    if verification.get("run_exit") not in (None, 0):
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="runtime_failure", subject="solution.py", priority=80,
            expected="python3 solution.py exits 0",
            observed=f"execution exited {verification.get('run_exit')}",
            evidence={**evidence_base, "command": "python3 solution.py",
                      "exit_code": verification.get("run_exit"),
                      "error_excerpt": (verification.get("stderr") or verification.get("stdout") or "")[-1200:]},
            recovery_target="repair_smallest_runtime_dependency",
        )
    if role == "reviewer" and scaffold_origin and not (workspace / "implementation.md").is_file():
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="scaffold_handoff_incomplete", subject="solution.py", priority=70,
            expected="the recovered checkpoint is extended and implementation.md documents the handoff",
            observed="solution.py runs, but it originated from atomic recovery and implementation.md is absent",
            evidence={**evidence_base, "scaffold_origin": True,
                      "command": "python3 solution.py", "exit_code": 0},
            recovery_target="extend_scaffold_before_review_completion",
        )
    report = workspace / report_name
    if not report.is_file():
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="handoff_missing", subject=report_name,
            priority=50 if role == "reviewer" else 40,
            expected=f"{report_name} records the exact verification result",
            observed=f"{report_name} is absent",
            evidence={**evidence_base, "command": "python3 solution.py", "exit_code": 0},
            recovery_target="persist_missing_report",
        )
    if role == "reviewer" and not (workspace / "implementation.md").is_file():
        return _blocker(
            task_id=task_id, run_id=run_id, role=role, stage=stage, hook=hook,
            blocker_type="handoff_missing", subject="implementation.md", priority=40,
            expected="implementation.md records the exact verification result",
            observed="implementation.md is absent",
            evidence={**evidence_base, "command": "python3 solution.py", "exit_code": 0},
            recovery_target="persist_missing_report",
        )
    return None


def fail_open_observe(
    observer: Callable[..., Blocker | None], *, error_log: Path, **kwargs: Any,
) -> Blocker | None:
    """Memory failure must never become a task failure."""
    try:
        return observer(**kwargs)
    except Exception as exc:  # intentionally catches optional-layer failures
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with error_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"at": utc_now(), "error": repr(exc), "fallback": "baseline_continue"}) + "\n")
        except Exception:
            pass
        return None


def append_event(path: Path, blocker: Blocker | None, *, condition: str, hook: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"at": utc_now(), "condition": condition, "hook": hook,
                 "blocker": blocker.to_dict() if blocker else None}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def recovery_prompt(blocker: Blocker, condition: str) -> str:
    """Render matched C0 or M1 recovery text. Both conditions get one call."""
    if condition == "C0":
        return (
            "Continue the same task. Inspect the current workspace, complete any remaining "
            "implementation or review work, run the required command, and persist the required reports."
        )
    if condition not in {"M1", "M2", "M3"}:
        raise ValueError(f"Unknown condition: {condition}")

    if blocker.blocker_type == "artifact_missing":
        if condition == "M3":
            return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
The runner observed that solution.py is absent because the previous turn ended before an implementation write was persisted.

CHECKPOINT-THEN-COMPLETE POLICY
Your first substantive action must be a file-write tool call that creates a syntactically valid, runnable solution.py. Keep this first checkpoint small enough to persist reliably.

After that write succeeds, do not stop at the scaffold. Continue using bounded writes or edits:
1. Implement an end-to-end vertical slice for every top-level requirement in TASK.md.
2. Replace placeholders, mock-only boundaries, not-implemented paths, and disconnected structural markers with working behavior.
3. Connect required subsystems through executable interfaces.
4. Run python3 solution.py and repair failures.
5. Write implementation.md with the exact result and any genuinely incomplete requirements.

If the turn ends early, leave as many working requirement slices as possible on disk. Do not regenerate the entire file in chat. Do not restate this memory. Make the first file write now."""
        if condition == "M2":
            return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
The runner observed that solution.py is absent after the previous attempt.

ATOMIC RECOVERY POLICY
Your first and only substantive action in this turn must be a file-write tool call that creates a syntactically valid, runnable solution.py of at most 4,000 characters. Include a minimal executable smoke test. Do not reread the task, do not design the full system, do not explain, and do not attempt full feature coverage in this turn. Persist the scaffold, run it once if space permits, then stop. The next stage will extend it.

Do not restate this memory. Write the file now."""
        return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
The runner observed that solution.py is absent after the previous attempt.

Resolve this blocker first:
1. Persist a minimal runnable solution.py immediately; do not draft the whole file in chat.
2. Extend it through bounded file writes or edits.
3. Run python3 solution.py and repair failures.
4. Persist the required {('implementation.md' if blocker.recipient_role == 'implementer' else 'review.md')} report.
If the complete implementation cannot fit, leave the best runnable partial artifact on disk.

Do not restate this memory. Act on it."""
    if blocker.blocker_type == "scaffold_handoff_incomplete":
        return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
solution.py runs, but it was created as an emergency checkpoint after implementation failed, and implementation.md is still absent. A successful exit code does not establish requirement completion.

Before writing the final review:
1. Compare the implementation against every top-level TASK.md requirement.
2. Extend the existing file with bounded edits; do not replace it wholesale.
3. Implement missing end-to-end behavior, prioritizing disconnected or marker-only subsystem boundaries.
4. Run python3 solution.py and relevant reviewer tests.
5. Write implementation.md and review.md with exact evidence and identify anything still incomplete.

Do not merely report that the scaffold runs. Improve it first."""
    if blocker.blocker_type in {"compile_failure", "runtime_failure"}:
        evidence = blocker.evidence
        return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
{blocker.subject} exists, but the runner observed:
Command: {evidence.get('command')}
Exit code: {evidence.get('exit_code')}
Failure: {evidence.get('error_excerpt') or '(no output)'}

Repair the smallest dependency that explains this failure. Preserve the current artifact, use bounded edits, rerun the same command, and persist the exact result in the required report. Do not replace the whole program unless a bounded repair is impossible.

Do not restate this memory. Act on it."""
    return f"""Continue the same {blocker.stage} task.

PRIVATE RECOVERY MEMORY — ONE CURRENT BLOCKER
solution.py currently runs successfully, but {blocker.subject} is absent.
Do not rewrite working code. Run python3 solution.py once to confirm the current result, then write {blocker.subject} with the exact command, exit status, and test summary.

Do not restate this memory. Act on it."""
