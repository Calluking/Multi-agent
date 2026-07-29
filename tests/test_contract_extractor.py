#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest

from contract_extractor import consolidate_acceptance_facets, validate_extraction


WORKFLOW = {
    "stages": [
        {"stage_id": "build", "role": "builder"},
        {"stage_id": "review", "role": "reviewer"},
        {"stage_id": "consume", "role": "frontend"},
    ]
}


def dependency(dep_id: str, *, scope: str = "workflow", resource_type: str = "file", location: str | None = None) -> dict:
    return {
        "dependency_id": dep_id,
        "type": "artifact" if resource_type == "file" else "interface",
        "dependency_scope": scope,
        "name": dep_id,
        "description": dep_id,
        "resource_type": resource_type,
        "location": location,
        "producer_role": "builder",
        "consumers": [{"role": "reviewer", "intended_action": "review"}],
        "prerequisites": [],
        "expected_state": "produced",
        "acceptance_criteria": [{
            "criterion_id": "exists",
            "type": "existence" if resource_type == "file" else "semantic",
            "specification": "exists or is satisfied",
            "values": [],
        }],
        "verification": {"method": "inspection", "command": None, "expected": {}, "timeout_seconds": None},
        "deadline": "before_consumer_start",
        "deadline_stage": "review",
        "recovery_role": "builder",
        "next_action": "produce it",
        "semantic_text": dep_id,
        "keywords": [dep_id],
        "entities": [dep_id],
        "applicable_actions": ["create", "review"],
        "applicable_stages": ["build", "review"],
        "priority": "critical",
        "confidence": 0.9,
        "evidence": [{"source": "workflow", "text": "test evidence"}],
    }


class ContractExtractorTests(unittest.TestCase):
    def test_reserved_environment_producer_is_allowed(self) -> None:
        item = dependency("runtime", scope="environment", resource_type="other")
        item["type"] = "capability"
        item["producer_role"] = "environment"
        result = validate_extraction({"dependencies": [item]}, WORKFLOW)
        self.assertTrue(result.valid, result.errors)

    def test_product_actor_is_not_a_workflow_consumer(self) -> None:
        item = dependency("program", location="program.py")
        item["consumers"] = [{"role": "end_user", "intended_action": "use"}]
        result = validate_extraction({"dependencies": [item]}, WORKFLOW)
        self.assertFalse(result.valid)
        self.assertTrue(any("unknown consumer role" in error for error in result.errors))

    def test_empty_deterministic_content_values_are_rejected(self) -> None:
        item = dependency("report", location="report.md")
        item["acceptance_criteria"] = [{
            "criterion_id": "contains_command",
            "type": "content_contains_all",
            "specification": "contains exact command",
            "values": [],
        }]
        result = validate_extraction({"dependencies": [item]}, WORKFLOW)
        self.assertFalse(result.valid)
        self.assertTrue(any("without literal values" in error for error in result.errors))

    def test_same_boundary_product_facet_is_folded(self) -> None:
        program = dependency("program", scope="product", location="program.py")
        facet = dependency("permissions", scope="product", resource_type="interface")
        facet["prerequisites"] = [{
            "dependency_id": "program", "relation": "requires", "required_state": "produced"
        }]
        consolidated, decisions = consolidate_acceptance_facets({"dependencies": [program, facet]})
        self.assertEqual(["program"], [item["dependency_id"] for item in consolidated["dependencies"]])
        self.assertEqual("permissions", decisions[0]["folded_dependency"])
        self.assertTrue(any(
            criterion["criterion_id"].startswith("permissions__")
            for criterion in consolidated["dependencies"][0]["acceptance_criteria"]
        ))

    def test_cross_agent_interface_is_preserved(self) -> None:
        program = dependency("backend_code", scope="product", location="backend.py")
        interface = dependency("backend_api", scope="product", resource_type="interface")
        interface["prerequisites"] = [{
            "dependency_id": "backend_code", "relation": "requires", "required_state": "produced"
        }]
        interface["consumers"] = [{"role": "frontend", "intended_action": "integrate"}]
        consolidated, decisions = consolidate_acceptance_facets({"dependencies": [program, interface]})
        self.assertEqual(2, len(consolidated["dependencies"]))
        self.assertEqual([], decisions)


if __name__ == "__main__":
    unittest.main()

