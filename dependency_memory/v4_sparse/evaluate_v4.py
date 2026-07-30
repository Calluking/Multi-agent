#!/usr/bin/env python3
"""Evaluate paired C0 (matched control) and M1 (sparse memory) v4 runs.

The evaluator is deliberately independent of the runner.  It recursively finds
``result.json`` files, infers condition/repetition from manifests or paths, and
normalizes both the old baseline-like schema and the v3/v4 result schema.

Typical layouts accepted::

    ROOT/C0/rep_01/task_01/result.json
    ROOT/M1/rep_01/task_01/result.json

or any layout where a nearby ``run_manifest.json`` provides ``condition`` and
``repetition``.  Optional memory telemetry can live in the result itself or in
``memory_events.json`` / ``memory_events.jsonl`` beside it.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PILOT_TASKS = (1, 17)
PANEL_TASKS = (1, 2, 5, 15, 17)
PILOT_HEALTHY = (1,)
PANEL_HEALTHY = (1, 5, 15)
PILOT_FAILED = (17,)
PANEL_FAILED = (2, 17)


def nested(data: Mapping[str, Any], *paths: str) -> Any:
    """Return the first non-None dotted-path value."""
    for path in paths:
        cur: Any = data
        for part in path.split("."):
            if not isinstance(cur, Mapping) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur is not None:
            return cur
    return None


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "pass", "passed", "complete", "success"}:
            return True
        if lowered in {"false", "no", "fail", "failed", "incomplete", "error"}:
            return False
    return None


def infer_int(path: Path, patterns: Sequence[str]) -> int | None:
    text = "/".join(path.parts)
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def infer_condition(path: Path, data: Mapping[str, Any], manifest: Mapping[str, Any]) -> str | None:
    raw = nested(data, "condition", "experiment.condition") or nested(manifest, "condition")
    if raw:
        value = str(raw).upper()
        if value in {"C0", "M1", "M2", "M3"}:
            return value
    for part in reversed(path.parts):
        value = part.upper()
        if value in {"C0", "M1", "M2", "M3"}:
            return value
        match = re.search(r"(?:^|[_-])(C0|M1|M2|M3)(?:$|[_-])", value)
        if match:
            return match.group(1)
    return None


def infer_repetition(path: Path, data: Mapping[str, Any], manifest: Mapping[str, Any]) -> int | None:
    """Infer the experimental repetition, preferring the outer rep directory.

    Pilot batches currently have paths such as
    ``runs_pilot_v4/rep2/M1/task_01/rep_01/<run>/result.json``.  The inner
    ``rep_01`` and result field describe the runner-local repetition and are
    always one; the outer ``rep2`` is the experimental pair ID.  Locate the
    condition directory and prefer the nearest preceding rep component.
    """
    parts = list(path.parts)
    condition_index = next(
        (index for index, part in enumerate(parts) if part.upper() in {"C0", "M1", "M2", "M3"}),
        None,
    )
    if condition_index is not None:
        for part in reversed(parts[:condition_index]):
            match = re.fullmatch(r"rep(?:etition)?[_-]?0*(\d+)", part, re.IGNORECASE)
            if match:
                return int(match.group(1))
    raw = nested(data, "experiment_repetition", "experiment.repetition") or nested(
        manifest, "experiment_repetition", "experiment.repetition"
    )
    if number(raw) is not None:
        return int(raw)
    raw = nested(data, "repetition", "rep") or nested(manifest, "repetition", "rep")
    if number(raw) is not None:
        return int(raw)
    return infer_int(path, (r"rep(?:etition)?[_-]0*(\d+)", r"run[_-]0*(\d+)"))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def nearby_manifest(result_path: Path) -> Mapping[str, Any]:
    for directory in (result_path.parent, *list(result_path.parents)[:4]):
        for name in ("run_manifest.json", "manifest.json"):
            candidate = directory / name
            if candidate.exists():
                data = load_json(candidate)
                if isinstance(data, Mapping):
                    return data
    return {}


def memory_events(result_path: Path, result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    embedded = nested(result, "memory_events", "memory.events", "telemetry.memory_events")
    if isinstance(embedded, list):
        return [event for event in embedded if isinstance(event, Mapping)]
    for name in ("memory_events.json", "memory_telemetry.json"):
        candidate = result_path.parent / name
        if candidate.exists():
            loaded = load_json(candidate)
            if isinstance(loaded, list):
                return [event for event in loaded if isinstance(event, Mapping)]
            if isinstance(loaded, Mapping):
                events = nested(loaded, "events", "memory_events")
                if isinstance(events, list):
                    return [event for event in events if isinstance(event, Mapping)]
    candidate = result_path.parent / "memory_events.jsonl"
    if candidate.exists():
        events = []
        for line in candidate.read_text(encoding="utf-8").splitlines():
            if line.strip():
                event = json.loads(line)
                if isinstance(event, Mapping):
                    events.append(event)
        return events
    return []


def sum_stage_metric(data: Mapping[str, Any], metric: str) -> float | None:
    stages = nested(data, "stage_meta", "stages")
    if not isinstance(stages, Mapping):
        return None
    values: list[float] = []
    for stage in stages.values():
        if not isinstance(stage, Mapping):
            continue
        if metric == "tokens":
            value = number(nested(stage, "usage.total", "usage.total_tokens", "total_tokens"))
        else:
            value = number(nested(stage, "duration_ms", "elapsed_ms"))
        if value is not None:
            values.append(value)
    return sum(values) if values else None


def event_flag(events: Sequence[Mapping[str, Any]], names: set[str]) -> bool | None:
    observed = False
    for event in events:
        kind = str(nested(event, "event", "type", "kind", "name") or "").lower()
        if kind:
            observed = True
        if kind in names:
            return True
    return False if observed else None


def injection_tokens(data: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> float | None:
    direct = number(nested(data, "memory.injection_tokens", "telemetry.injection_tokens", "injection_tokens"))
    if direct is not None:
        return direct
    direct_chars = number(nested(data, "injection.total_chars", "memory.injection_chars"))
    if direct_chars is not None:
        return math.ceil(direct_chars / 4)
    total = 0.0
    found = False
    for event in events:
        kind = str(nested(event, "event", "type", "kind", "name") or "").lower()
        if "inject" not in kind and not boolean(nested(event, "injected")):
            continue
        value = number(nested(event, "tokens", "token_count", "injection_tokens"))
        if value is None:
            text = nested(event, "text", "payload", "injected_text", "content")
            if isinstance(text, str):
                # Stable tokenizer-independent approximation for an overhead gate.
                value = math.ceil(len(text) / 4)
        if value is not None:
            total += value
            found = True
    return total if found else None


@dataclass(frozen=True)
class Run:
    task_id: int
    repetition: int
    condition: str
    result_path: str
    workflow_complete: bool | None
    run_pass: bool | None
    score: float | None
    tokens: float | None
    duration_ms: float | None
    injection_tokens: float | None
    recovery_triggered: bool | None
    recovery_success: bool | None
    fail_open: bool | None
    checkpoint_success: bool | None
    first_write_ms: float | None


def normalize(result_path: Path) -> Run | None:
    data = load_json(result_path)
    if not isinstance(data, Mapping):
        return None
    manifest = nearby_manifest(result_path)
    condition = infer_condition(result_path, data, manifest)
    task_id = nested(data, "task_id", "task.id") or nested(manifest, "task_id", "task.id")
    task_id = int(task_id) if number(task_id) is not None else infer_int(result_path, (r"task[_-]0*(\d+)",))
    repetition = infer_repetition(result_path, data, manifest)
    if condition is None or task_id is None or repetition is None:
        return None

    workflow = boolean(nested(data, "workflow_complete", "outcome.workflow_complete"))
    run_exit = nested(data, "objective.run_exit", "run_exit", "outcome.run_exit")
    run_pass = boolean(nested(data, "objective.run_pass", "run_pass", "outcome.run_pass"))
    if run_pass is None and run_exit is not None:
        run_pass = number(run_exit) == 0
    score = number(nested(data, "task_scores.percentage", "task_percentage", "score", "outcome.score"))
    tokens = number(nested(data, "telemetry.total_tokens", "total_tokens", "usage.total"))
    duration = number(nested(data, "telemetry.duration_ms", "duration_ms", "elapsed_ms"))
    if duration is None:
        wall_seconds = number(nested(data, "wall_time_seconds", "telemetry.wall_time_seconds"))
        if wall_seconds is not None:
            duration = wall_seconds * 1000
    if tokens is None:
        tokens = sum_stage_metric(data, "tokens")
    if duration is None:
        duration = sum_stage_metric(data, "duration")

    events = memory_events(result_path, data)
    triggered = boolean(nested(data, "recovery.triggered", "recovery_triggered"))
    success = boolean(nested(data, "recovery.success", "recovery_success"))
    if triggered is None:
        triggered = event_flag(events, {"recovery_trigger", "recovery_triggered", "missing_artifact_trigger"})
    if triggered is None:
        triggers = nested(data, "triggers")
        if isinstance(triggers, Mapping):
            triggered = any(value is not None for value in triggers.values())
    if success is None:
        success = event_flag(events, {"recovery_success", "artifact_recovered", "recovery_completed"})
    if success is None and triggered:
        triggers = nested(data, "triggers")
        artifacts = nested(data, "required_artifacts")
        recovered: list[bool] = []
        if isinstance(triggers, Mapping) and isinstance(artifacts, Mapping):
            for trigger in triggers.values():
                if isinstance(trigger, Mapping):
                    subject = nested(trigger, "subject")
                    if isinstance(subject, str) and subject in artifacts:
                        recovered.append(bool(artifacts[subject]))
        success = all(recovered) if recovered else None
    fail_open = boolean(nested(data, "memory.fail_open", "fail_open", "telemetry.fail_open"))
    checkpoint_success = boolean(nested(data, "memory.checkpoint_success", "checkpoint_success"))
    first_write = number(nested(data, "telemetry.first_write_ms", "first_write_ms", "recovery.first_write_ms"))

    return Run(
        task_id=task_id,
        repetition=repetition,
        condition=condition,
        result_path=str(result_path),
        workflow_complete=workflow,
        run_pass=run_pass,
        score=score,
        tokens=tokens,
        duration_ms=duration,
        injection_tokens=injection_tokens(data, events),
        recovery_triggered=triggered,
        recovery_success=success,
        fail_open=fail_open,
        checkpoint_success=checkpoint_success,
        first_write_ms=first_write,
    )


def mean_known(values: Iterable[float | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    return statistics.fmean(known) if known else None


def rate_known(values: Iterable[bool | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def delta(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else left - right


def gate(name: str, passed: bool | None, value: Any, threshold: str, note: str = "") -> dict[str, Any]:
    return {"name": name, "passed": passed, "value": value, "threshold": threshold, "note": note}


def evaluate(runs: Sequence[Run], phase: str, treatment: str = "M1") -> dict[str, Any]:
    treatment = treatment.upper()
    if treatment not in {"M1", "M2", "M3"}:
        raise ValueError(f"unsupported treatment: {treatment}")
    tasks = PILOT_TASKS if phase == "pilot" else PANEL_TASKS
    healthy = PILOT_HEALTHY if phase == "pilot" else PANEL_HEALTHY
    failed = PILOT_FAILED if phase == "pilot" else PANEL_FAILED
    required_reps = 3 if phase == "pilot" else 5
    selected = [run for run in runs if run.task_id in tasks and run.condition in {"C0", treatment}]
    by_key = {(run.task_id, run.repetition, run.condition): run for run in selected}
    pairs = []
    for task in tasks:
        reps = sorted({run.repetition for run in selected if run.task_id == task})
        for rep in reps:
            c0 = by_key.get((task, rep, "C0"))
            m1 = by_key.get((task, rep, treatment))
            if c0 and m1:
                pairs.append((task, rep, c0, m1))

    expected_runs = len(tasks) * required_reps * 2
    expected_pairs = len(tasks) * required_reps
    coverage = len(selected) / expected_runs
    pair_coverage = len(pairs) / expected_pairs

    def subset(condition: str, task_set: Sequence[int] = tasks) -> list[Run]:
        return [run for run in selected if run.condition == condition and run.task_id in task_set]

    def summary(condition: str, task_set: Sequence[int] = tasks) -> dict[str, Any]:
        values = subset(condition, task_set)
        return {
            "runs": len(values),
            "workflow_rate": rate_known(run.workflow_complete for run in values),
            "run_rate": rate_known(run.run_pass for run in values),
            "mean_score": mean_known(run.score for run in values),
            "mean_tokens": mean_known(run.tokens for run in values),
            "mean_duration_ms": mean_known(run.duration_ms for run in values),
            "mean_injection_tokens": mean_known(run.injection_tokens for run in values),
            "recovery_trigger_rate": rate_known(run.recovery_triggered for run in values),
            "recovery_success_rate": rate_known(run.recovery_success for run in values if run.recovery_triggered),
        }

    c0_all, m1_all = summary("C0"), summary(treatment)
    c0_healthy, m1_healthy = summary("C0", healthy), summary(treatment, healthy)
    c0_failed, m1_failed = summary("C0", failed), summary(treatment, failed)

    pair_rows = []
    severe = 0
    for task, rep, c0, m1 in pairs:
        score_delta = delta(m1.score, c0.score)
        severe_regression = bool(
            (score_delta is not None and score_delta <= -10)
            or (c0.workflow_complete is True and m1.workflow_complete is False)
            or (c0.run_pass is True and m1.run_pass is False)
        )
        severe += severe_regression
        pair_rows.append({
            "task_id": task,
            "repetition": rep,
            "score_delta": score_delta,
            "workflow_delta": delta(number(m1.workflow_complete), number(c0.workflow_complete)),
            "run_delta": delta(number(m1.run_pass), number(c0.run_pass)),
            "token_ratio": ratio(m1.tokens, c0.tokens),
            "duration_ratio": ratio(m1.duration_ms, c0.duration_ms),
            "first_write_delta_ms": delta(m1.first_write_ms, c0.first_write_ms),
            "severe_regression": severe_regression,
        })

    paired_score_delta = mean_known(row["score_delta"] for row in pair_rows)
    token_ratio = mean_known(row["token_ratio"] for row in pair_rows)
    duration_ratio = mean_known(row["duration_ratio"] for row in pair_rows)
    healthy_score_delta = delta(m1_healthy["mean_score"], c0_healthy["mean_score"])
    healthy_workflow_delta = delta(m1_healthy["workflow_rate"], c0_healthy["workflow_rate"])
    healthy_run_delta = delta(m1_healthy["run_rate"], c0_healthy["run_rate"])
    failed_score_delta = delta(m1_failed["mean_score"], c0_failed["mean_score"])
    failed_workflow_delta = delta(m1_failed["workflow_rate"], c0_failed["workflow_rate"])
    failed_run_delta = delta(m1_failed["run_rate"], c0_failed["run_rate"])

    m1_runs = subset(treatment)
    fail_open_values = [run.fail_open for run in m1_runs if run.fail_open is not None]
    checkpoint_values = [run.checkpoint_success for run in m1_runs if run.checkpoint_success is not None]
    max_injection = max((run.injection_tokens for run in m1_runs if run.injection_tokens is not None), default=None)

    enough_data = coverage >= 1.0 and pair_coverage >= 1.0
    gates = [
        gate("coverage", enough_data, {"run": coverage, "pair": pair_coverage}, "100% preregistered runs and pairs"),
        gate("fail_open", (all(fail_open_values) if fail_open_values else None), rate_known(fail_open_values), "100%", "unknown if telemetry absent"),
        gate("checkpoint_reliability", (rate_known(checkpoint_values) >= .95 if checkpoint_values else None), rate_known(checkpoint_values), ">= 0.95", "unknown if telemetry absent"),
        gate("healthy_workflow_noninferiority", healthy_workflow_delta >= -.05 if healthy_workflow_delta is not None else None, healthy_workflow_delta, ">= -0.05"),
        gate("healthy_run_noninferiority", healthy_run_delta >= -.05 if healthy_run_delta is not None else None, healthy_run_delta, ">= -0.05"),
        gate("healthy_score_noninferiority", healthy_score_delta >= -5 if healthy_score_delta is not None else None, healthy_score_delta, ">= -5 points"),
        gate("no_severe_regressions", severe == 0, severe, "0"),
        gate("failed_task_score_efficacy", failed_score_delta >= 10 if failed_score_delta is not None else None, failed_score_delta, ">= +10 points"),
        gate("failed_task_workflow_efficacy", failed_workflow_delta >= .20 if failed_workflow_delta is not None else None, failed_workflow_delta, ">= +0.20"),
        gate("failed_task_run_efficacy", failed_run_delta >= .20 if failed_run_delta is not None else None, failed_run_delta, ">= +0.20"),
        gate("token_overhead", token_ratio <= 1.20 if token_ratio is not None else None, token_ratio, "<= 1.20x"),
        gate("wall_time_overhead", duration_ratio <= 1.25 if duration_ratio is not None else None, duration_ratio, "<= 1.25x"),
        gate("injection_size", max_injection <= 500 if max_injection is not None else None, max_injection, "<= 500 tokens", "unknown if telemetry absent"),
    ]

    # The pilot is a screening experiment, not sufficient to declare the full
    # five-task system good. It passes screening when safety/reliability/
    # efficiency pass and Task 17 shows either more successful recovery or a
    # materially earlier first write. The general efficacy gates remain shown.
    if phase == "pilot":
        recovery_delta = delta(m1_failed["recovery_success_rate"], c0_failed["recovery_success_rate"])
        first_write_delta = mean_known(
            row["first_write_delta_ms"] for row in pair_rows if row["task_id"] in failed
        )
        signal = ((recovery_delta is not None and recovery_delta > 0)
                  or (first_write_delta is not None and first_write_delta < 0)
                  or (failed_workflow_delta is not None and failed_workflow_delta > 0))
        gates.append(gate(
            "pilot_recovery_signal", signal,
            {"recovery_success_delta": recovery_delta, "first_write_delta_ms": first_write_delta,
             "workflow_delta": failed_workflow_delta},
            "M1 improves recovery success/workflow or reaches first write earlier",
        ))

    known_required = [item for item in gates if item["name"] not in {"checkpoint_reliability", "fail_open", "injection_size"}]
    all_known_pass = enough_data and all(item["passed"] is True for item in known_required)
    telemetry_complete = all(item["passed"] is not None for item in gates)
    verdict = "PASS" if all_known_pass and telemetry_complete else "INCOMPLETE" if not enough_data or not telemetry_complete else "FAIL"

    return {
        "phase": phase,
        "comparison": f"{treatment}-vs-C0",
        "treatment": treatment,
        "tasks": list(tasks),
        "required_repetitions": required_reps,
        "coverage": {
            "observed_runs": len(selected), "expected_runs": expected_runs, "rate": coverage,
            "observed_pairs": len(pairs), "expected_pairs": expected_pairs, "pair_rate": pair_coverage,
        },
        "condition_summary": {"C0": c0_all, treatment: m1_all},
        "healthy_summary": {"tasks": list(healthy), "C0": c0_healthy, treatment: m1_healthy},
        "failed_summary": {"tasks": list(failed), "C0": c0_failed, treatment: m1_failed},
        "paired": {
            "mean_score_delta": paired_score_delta,
            "mean_token_ratio": token_ratio,
            "mean_duration_ratio": duration_ratio,
            "severe_regressions": severe,
            "rows": pair_rows,
        },
        "gates": gates,
        "verdict": verdict,
        "interpretation": (
            "Pilot PASS only authorizes the five-task panel; it is not a final effectiveness claim."
            if phase == "pilot" else
            "Panel PASS means all preregistered reliability, safety, efficacy, and efficiency gates passed."
        ),
    }


def discover(root: Path) -> tuple[list[Run], list[str]]:
    runs: list[Run] = []
    warnings: list[str] = []
    for path in sorted(root.rglob("result.json")):
        try:
            run = normalize(path)
            if run is None:
                warnings.append(f"Skipped {path}: could not infer task, repetition, or C0/M1 condition")
            else:
                runs.append(run)
        except Exception as exc:  # evaluation should report bad artifacts, not conceal them
            warnings.append(f"Skipped {path}: {type(exc).__name__}: {exc}")
    return runs, warnings


def direct_contrast(runs: Sequence[Run], phase: str, left: str, right: str) -> dict[str, Any]:
    """Return a descriptive paired contrast (left minus right).

    Gate decisions remain treatment-vs-C0.  This additional contrast makes the
    incremental M2-vs-M1 effect visible without incorrectly reusing C0 gate
    thresholds for that different scientific question.
    """
    tasks = PILOT_TASKS if phase == "pilot" else PANEL_TASKS
    relevant = [run for run in runs if run.task_id in tasks and run.condition in {left, right}]
    indexed = {(run.task_id, run.repetition, run.condition): run for run in relevant}
    rows: list[dict[str, Any]] = []
    for task in tasks:
        reps = sorted({run.repetition for run in relevant if run.task_id == task})
        for repetition in reps:
            lhs = indexed.get((task, repetition, left))
            rhs = indexed.get((task, repetition, right))
            if lhs is None or rhs is None:
                continue
            rows.append({
                "task_id": task,
                "repetition": repetition,
                "score_delta": delta(lhs.score, rhs.score),
                "workflow_delta": delta(number(lhs.workflow_complete), number(rhs.workflow_complete)),
                "run_delta": delta(number(lhs.run_pass), number(rhs.run_pass)),
                "token_ratio": ratio(lhs.tokens, rhs.tokens),
                "duration_ratio": ratio(lhs.duration_ms, rhs.duration_ms),
                "first_write_delta_ms": delta(lhs.first_write_ms, rhs.first_write_ms),
            })
    expected = len(tasks) * (3 if phase == "pilot" else 5)
    return {
        "comparison": f"{left}-vs-{right}",
        "observed_pairs": len(rows),
        "expected_pairs": expected,
        "pair_coverage": len(rows) / expected,
        "mean_score_delta": mean_known(row["score_delta"] for row in rows),
        "mean_workflow_delta": mean_known(row["workflow_delta"] for row in rows),
        "mean_run_delta": mean_known(row["run_delta"] for row in rows),
        "mean_token_ratio": mean_known(row["token_ratio"] for row in rows),
        "mean_duration_ratio": mean_known(row["duration_ratio"] for row in rows),
        "rows": rows,
    }


def self_test() -> None:
    runs = []
    for repetition in range(1, 4):
        for task in PILOT_TASKS:
            base_score = 85 if task == 1 else 20
            runs.append(Run(task, repetition, "C0", "", task == 1, task == 1, base_score,
                            100, 1000, 0, task == 17, False, True, True, 500))
            runs.append(Run(task, repetition, "M1", "", True, True,
                            base_score if task == 1 else 75, 110, 1100, 100,
                            task == 17, task == 17, True, True, 300))
    report = evaluate(runs, "pilot")
    assert report["coverage"]["rate"] == 1
    assert report["paired"]["severe_regressions"] == 0
    assert next(g for g in report["gates"] if g["name"] == "pilot_recovery_signal")["passed"]
    # Outer experimental repetition must override an inner runner-local rep.
    fake = Path("/tmp/runs/rep3/M2/task_17/rep_01/run/result.json")
    assert infer_repetition(fake, {"repetition": 1}, {}) == 3
    assert infer_condition(fake, {}, {}) == "M2"
    m2_runs = [Run(**{**asdict(run), "condition": "M2"}) for run in runs if run.condition == "M1"]
    m2_report = evaluate([run for run in runs if run.condition == "C0"] + m2_runs, "pilot", "M2")
    assert m2_report["coverage"]["observed_pairs"] == 6
    contrast = direct_contrast(runs + m2_runs, "pilot", "M2", "M1")
    assert contrast["observed_pairs"] == 6
    assert contrast["mean_score_delta"] == 0
    print("self-test passed")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="Root containing C0/M1 result.json files")
    parser.add_argument("--phase", choices=("pilot", "panel"), default="pilot")
    parser.add_argument(
        "--treatments", nargs="+", choices=("M1", "M2", "M3"),
        help="Treatments to compare independently with C0 (default: all discovered)",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.root is None:
        parser.error("root is required unless --self-test is used")
    runs, warnings = discover(args.root)
    discovered = sorted({run.condition for run in runs if run.condition in {"M1", "M2", "M3"}})
    treatments = args.treatments or discovered or ["M1"]
    comparisons = {treatment: evaluate(runs, args.phase, treatment) for treatment in treatments}
    report = {
        "phase": args.phase,
        "source_root": str(args.root.resolve()),
        "treatments": treatments,
        "comparisons": comparisons,
        "direct_treatment_comparisons": (
            {"M2-vs-M1": direct_contrast(runs, args.phase, "M2", "M1")}
            if {"M1", "M2"}.issubset(treatments) else {}
        ),
        "warnings": warnings,
    }
    verdicts = [comparison["verdict"] for comparison in comparisons.values()]
    report["verdict"] = (
        "PASS" if verdicts and all(value == "PASS" for value in verdicts)
        else "FAIL" if any(value == "FAIL" for value in verdicts)
        else "INCOMPLETE"
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
