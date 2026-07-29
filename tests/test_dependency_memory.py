#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from dependency_memory import DependencyMemoryStore


class DependencyMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.store = DependencyMemoryStore(self.workspace, self.workspace / "memory.yaml")
        self.store.compile_contracts(
            system_id="test",
            task_id="1",
            run_id="run-1",
            workflow_id="workflow",
            producer_role="builder",
            consumer_role="reviewer",
            artifacts=[
                {
                    "dependency_id": "program",
                    "location": "program.py",
                    "description": "Executable program",
                    "expected_state": "verified",
                    "verification": {"method": "command", "command": "python3 program.py"},
                    "resolution_conditions": ["program exists", "program exits 0"],
                    "applicable_actions": ["create", "review", "finalize"],
                },
                {
                    "dependency_id": "report",
                    "location": "report.md",
                    "description": "Report with command and result",
                    "expected_state": "produced",
                    "prerequisites": [{
                        "dependency_id": "program",
                        "relation": "requires",
                        "required_state": "verified",
                    }],
                    "acceptance_criteria": [
                        {"criterion_id": "exists", "type": "existence"},
                        {"criterion_id": "command", "type": "content_contains_all", "values": ["python3 program.py"]},
                        {"criterion_id": "result", "type": "content_contains_any", "values": ["passed", "exit code 0"]},
                    ],
                    "resolution_conditions": ["report exists", "command and result recorded"],
                    "applicable_actions": ["create", "review", "finalize"],
                },
            ],
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_root_dependency_is_selected_before_dependent(self) -> None:
        self.store.observe_files(stage="reviewer", event_id="start")
        selected = self.store.select(
            task_id="1", run_id="run-1", recipient_role="reviewer", stage="reviewer",
            action="finalize", query="Which program and report dependencies remain?",
        )
        self.assertEqual("program", selected[0]["identity"]["dependency_id"])

    def test_content_and_prerequisite_acceptance(self) -> None:
        (self.workspace / "program.py").write_text("print('ok')\n", encoding="utf-8")
        (self.workspace / "report.md").write_text("placeholder\n", encoding="utf-8")
        self.store.observe_files(stage="reviewer", event_id="created")
        report = self.store._by_id("report")
        self.assertEqual("failed", report["state"]["status"])

        proc = subprocess.run(
            ["python3", "program.py"], cwd=self.workspace, text=True, capture_output=True
        )
        self.store.record_verification(
            dependency_id="program", command="python3 program.py", exit_code=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr, stage="reviewer", event_id="verify",
        )
        (self.workspace / "report.md").write_text(
            "Command: python3 program.py\nResult: passed; exit code 0\n", encoding="utf-8"
        )
        self.store.observe_files(stage="reviewer", event_id="report-fixed")
        self.assertTrue(self.store._by_id("report")["state"]["readiness"])

    def test_edit_invalidates_verified_artifact(self) -> None:
        program = self.workspace / "program.py"
        program.write_text("print('v1')\n", encoding="utf-8")
        self.store.observe_files(stage="reviewer", event_id="v1")
        self.store.record_verification(
            dependency_id="program", command="python3 program.py", exit_code=0,
            stdout="v1\n", stderr="", stage="reviewer", event_id="verify-v1",
        )
        self.store.observe_files(stage="reviewer", event_id="after-v1")
        self.assertEqual("verified", self.store._by_id("program")["state"]["status"])

        program.write_text("print('v2')\n", encoding="utf-8")
        self.store.observe_files(stage="reviewer", event_id="v2")
        program_record = self.store._by_id("program")
        self.assertEqual("produced", program_record["state"]["status"])
        self.assertEqual("stale", program_record["state"]["verification"]["status"])

    def test_non_file_dependency_accepts_typed_observation(self) -> None:
        other = DependencyMemoryStore(self.workspace, self.workspace / "other.yaml")
        other.compile_contracts(
            system_id="test", task_id="2", run_id="run-2", workflow_id="workflow",
            producer_role=None, consumer_role=None,
            artifacts=[{
                "dependency_id": "approval",
                "type": "approval",
                "dependency_scope": "environment",
                "resource_type": "decision",
                "location": None,
                "name": "Deployment approval",
                "description": "User approves deployment",
                "producer_role": "user",
                "consumers": [{"role": "reviewer", "intended_action": "deploy"}],
                "expected_state": "approved",
                "acceptance_criteria": [{
                    "criterion_id": "explicit_approval", "type": "approval",
                    "specification": "Explicit approval is recorded", "values": [],
                }],
                "applicable_actions": ["deploy"],
                "applicable_stages": ["reviewer"],
            }],
        )
        other.record_observation(
            dependency_id="approval", event_type="approval_result", passed=True,
            observed_state="explicitly_approved", evidence={"summary": "User approved"},
            stage="reviewer", event_id="approval-1",
        )
        record = other._by_id("approval")
        self.assertEqual("approved", record["state"]["status"])
        self.assertTrue(record["state"]["readiness"])

    def test_command_verifies_non_file_interface(self) -> None:
        other = DependencyMemoryStore(self.workspace, self.workspace / "interface.yaml")
        other.compile_contracts(
            system_id="test", task_id="3", run_id="run-3", workflow_id="workflow",
            producer_role=None, consumer_role=None,
            artifacts=[{
                "dependency_id": "api_contract", "type": "interface",
                "dependency_scope": "product", "resource_type": "interface",
                "location": "program.py", "name": "API", "description": "API contract",
                "producer_role": "builder", "consumers": [{"role": "reviewer"}],
                "expected_state": "verified",
                "verification": {"method": "command", "command": "python3 program.py"},
                "acceptance_criteria": [{"criterion_id": "runs", "type": "execution", "specification": "runs"}],
                "applicable_actions": ["review"], "applicable_stages": ["reviewer"],
            }],
        )
        other.record_verification(
            dependency_id="api_contract", command="python3 program.py", exit_code=0,
            stdout="ok", stderr="", stage="reviewer", event_id="api-verify",
        )
        record = other._by_id("api_contract")
        self.assertEqual("verified", record["state"]["status"])
        self.assertTrue(record["state"]["readiness"])


if __name__ == "__main__":
    unittest.main()
