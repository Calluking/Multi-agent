from pathlib import Path

from sparse_memory import fail_open_observe, observe_blocker, recovery_prompt


def test_missing_solution_has_highest_priority(tmp_path: Path):
    blocker = observe_blocker(workspace=tmp_path, task_id=17, run_id="r", role="implementer",
                              stage="implementation", hook="after_first_pass",
                              verification={"compile_exit": None, "run_exit": None})
    assert blocker is not None
    assert blocker.blocker_type == "artifact_missing"
    assert blocker.priority == 100


def test_runtime_failure_precedes_missing_report(tmp_path: Path):
    (tmp_path / "solution.py").write_text("raise RuntimeError('x')")
    blocker = observe_blocker(workspace=tmp_path, task_id=9, run_id="r", role="implementer",
                              stage="implementation", hook="after_first_pass",
                              verification={"compile_exit": 0, "run_exit": 1, "stderr": "boom"})
    assert blocker is not None
    assert blocker.blocker_type == "runtime_failure"
    assert blocker.subject == "solution.py"


def test_missing_report_only_after_healthy_solution(tmp_path: Path):
    (tmp_path / "solution.py").write_text("print('ok')")
    blocker = observe_blocker(workspace=tmp_path, task_id=5, run_id="r", role="reviewer",
                              stage="review", hook="after_first_pass",
                              verification={"compile_exit": 0, "run_exit": 0})
    assert blocker is not None
    assert blocker.blocker_type == "handoff_missing"
    assert blocker.subject == "review.md"


def test_no_blocker_for_complete_role_output(tmp_path: Path):
    (tmp_path / "solution.py").write_text("print('ok')")
    (tmp_path / "implementation.md").write_text("python3 solution.py: exit 0")
    assert observe_blocker(workspace=tmp_path, task_id=5, run_id="r", role="implementer",
                           stage="implementation", hook="after_first_pass",
                           verification={"compile_exit": 0, "run_exit": 0}) is None


def test_matched_prompts_differ_only_in_information_policy(tmp_path: Path):
    blocker = observe_blocker(workspace=tmp_path, task_id=17, run_id="r", role="implementer",
                              stage="implementation", hook="after_first_pass",
                              verification={"compile_exit": None, "run_exit": None})
    assert blocker is not None
    assert "PRIVATE RECOVERY MEMORY" not in recovery_prompt(blocker, "C0")
    assert "PRIVATE RECOVERY MEMORY" in recovery_prompt(blocker, "M1")
    assert "Persist a minimal runnable solution.py immediately" in recovery_prompt(blocker, "M1")
    assert "first and only substantive action" in recovery_prompt(blocker, "M2")
    assert "at most 4,000 characters" in recovery_prompt(blocker, "M2")
    m3 = recovery_prompt(blocker, "M3")
    assert "CHECKPOINT-THEN-COMPLETE" in m3
    assert "do not stop at the scaffold" in m3
    assert "first and only substantive action" not in m3


def test_observation_failure_is_fail_open(tmp_path: Path):
    def broken(**_kwargs):
        raise RuntimeError("optional memory failed")

    error_log = tmp_path / "memory_errors.jsonl"
    assert fail_open_observe(broken, error_log=error_log) is None
    assert "baseline_continue" in error_log.read_text()


def test_reviewer_detects_missing_implementation_after_review_exists(tmp_path: Path):
    (tmp_path / "solution.py").write_text("print('ok')")
    (tmp_path / "review.md").write_text("reviewed")
    blocker = observe_blocker(workspace=tmp_path, task_id=19, run_id="r", role="reviewer",
                              stage="review", hook="after_first_pass",
                              verification={"compile_exit": 0, "run_exit": 0})
    assert blocker is not None
    assert blocker.subject == "implementation.md"


def test_observation_failure_stays_open_when_log_path_is_invalid(tmp_path: Path):
    def broken(**_kwargs):
        raise RuntimeError("optional memory failed")

    invalid_log = tmp_path / "already-a-file"
    invalid_log.write_text("x")
    assert fail_open_observe(broken, error_log=invalid_log / "child.jsonl") is None


def test_scaffold_debt_precedes_missing_review_report(tmp_path: Path):
    (tmp_path / "solution.py").write_text("print('ok')")
    blocker = observe_blocker(
        workspace=tmp_path, task_id=17, run_id="r", role="reviewer",
        stage="review", hook="after_first_pass",
        verification={"compile_exit": 0, "run_exit": 0}, scaffold_origin=True,
    )
    assert blocker is not None
    assert blocker.blocker_type == "scaffold_handoff_incomplete"
    assert blocker.priority == 70
    assert "Do not merely report that the scaffold runs" in recovery_prompt(blocker, "M3")


def test_scaffold_debt_clears_after_implementation_handoff(tmp_path: Path):
    (tmp_path / "solution.py").write_text("print('ok')")
    (tmp_path / "implementation.md").write_text("python3 solution.py: exit 0")
    blocker = observe_blocker(
        workspace=tmp_path, task_id=1, run_id="r", role="reviewer",
        stage="review", hook="after_first_pass",
        verification={"compile_exit": 0, "run_exit": 0}, scaffold_origin=True,
    )
    assert blocker is not None
    assert blocker.blocker_type == "handoff_missing"
    assert blocker.subject == "review.md"
