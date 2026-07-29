#!/usr/bin/env python3
"""Extract and validate dependency contracts from arbitrary task/workflow text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml


ALLOWED_DEPENDENCY_TYPES = {
    "artifact", "interface", "data", "execution", "capability",
    "decision", "approval", "handoff", "service",
}
ALLOWED_EXPECTED_STATES = {"available", "produced", "verified", "approved"}
ALLOWED_CRITERION_TYPES = {
    "existence", "execution", "content_contains_all", "content_contains_any",
    "schema", "interface", "approval", "semantic",
}
ALLOWED_DEPENDENCY_SCOPES = {"workflow", "product", "environment"}
RESERVED_PRODUCER_ROLES = {"environment", "orchestrator", "user", "external_system"}


EXTRACTION_INSTRUCTIONS = """You are a dependency-contract extractor for a general multi-agent workflow.

Infer dependencies required for agents and workflow stages to complete the supplied task. A dependency may be an artifact, interface, dataset, command result, capability, decision, approval, handoff, or service.

Rules:
1. Extract only dependencies supported by the task or workflow text.
2. Distinguish producer obligations from consumer prerequisites.
3. Include workflow deliverables and important product/interface dependencies.
   Create a separate product/interface dependency only when it is independently produced or consumed, crosses an agent boundary, or has its own lifecycle. Otherwise represent a requirement as an acceptance criterion of its containing artifact.
4. Use file locations and commands only when explicitly stated or unambiguously implied.
5. Do not claim any dependency is satisfied. You are generating contracts, not runtime state.
6. Acceptance criteria must be observable. Mark criteria requiring judgment as type semantic.
7. Every prerequisite dependency_id must reference another dependency in the output.
8. Avoid duplicates. Use stable snake_case dependency IDs.
9. Keep semantic_text concise and useful for later retrieval.
10. producer_role must be a workflow role. For an externally supplied capability use the reserved role environment, never null.
   Consumer roles must also be workflow roles. Product users or domain actors belong in entities and acceptance criteria, not consumers.
11. Do not convert the original task text into a separate dependency unless a workflow agent must produce a transformed requirements artifact.
12. For content_contains_all/content_contains_any, values must contain exact strings to check. Otherwise use semantic.
13. applicable_actions and applicable_stages must be non-empty and relevant to retrieval.
14. Confidence is confidence in the inferred contract, not confidence that it is satisfied. Do not use 1.0 for inferred contracts.
15. Output only YAML matching this structure:

schema_version: "0.1"
task_summary: "short summary"
dependencies:
  - dependency_id: stable_snake_case_id
    type: artifact|interface|data|execution|capability|decision|approval|handoff|service
    dependency_scope: workflow|product|environment
    name: short name
    description: precise obligation
    resource_type: file|interface|data|command_result|decision|service|other
    location: path_or_null
    producer_role: role from workflow or environment
    consumers:
      - role: role from workflow
        intended_action: action
    prerequisites:
      - dependency_id: another_id
        relation: requires|blocks|consumes
        required_state: available|produced|verified|approved
    expected_state: available|produced|verified|approved
    acceptance_criteria:
      - criterion_id: stable_id
        type: existence|execution|content_contains_all|content_contains_any|schema|interface|approval|semantic
        specification: observable requirement
        values: []
    verification:
      method: command|inspection|semantic|approval
      command: command_or_null
      expected: {}
      timeout_seconds: null
    deadline: before_consumer_start|before_consumer_completion|before_workflow_completion
    deadline_stage: workflow_stage
    recovery_role: workflow_role
    next_action: smallest action that can satisfy or advance the dependency
    semantic_text: concise retrieval text
    keywords: []
    entities: []
    applicable_actions: []
    applicable_stages: []
    priority: critical|high|medium|low
    confidence: 0.0
    evidence:
      - source: task|workflow
        text: short supporting paraphrase
"""


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def build_extraction_prompt(task_text: str, workflow: dict[str, Any]) -> str:
    workflow_text = yaml.safe_dump(workflow, sort_keys=False, allow_unicode=True)
    return (
        EXTRACTION_INSTRUCTIONS
        + "\n\n--- TASK ---\n"
        + task_text.strip()
        + "\n\n--- WORKFLOW ---\n"
        + workflow_text
    )


def parse_model_yaml(text: str) -> dict[str, Any]:
    fences = re.findall(r"```(?:yaml|yml)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = list(reversed(fences)) + [text]
    errors = []
    for candidate in candidates:
        try:
            data = yaml.safe_load(candidate)
        except yaml.YAMLError as exc:
            errors.append(str(exc))
            continue
        if isinstance(data, dict) and isinstance(data.get("dependencies"), list):
            return data
    raise ValueError("No valid dependency YAML found: " + " | ".join(errors[-2:]))


def validate_extraction(data: dict[str, Any], workflow: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        return ValidationResult(False, ["dependencies must be a non-empty list"], [])

    workflow_roles = {
        stage.get("role") for stage in workflow.get("stages", []) if stage.get("role")
    }
    ids: list[str] = []
    for index, dep in enumerate(dependencies):
        prefix = f"dependencies[{index}]"
        if not isinstance(dep, dict):
            errors.append(f"{prefix} must be an object")
            continue
        dep_id = dep.get("dependency_id")
        if not isinstance(dep_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", dep_id):
            errors.append(f"{prefix}.dependency_id must be snake_case")
        else:
            ids.append(dep_id)
        if dep.get("type") not in ALLOWED_DEPENDENCY_TYPES:
            errors.append(f"{prefix}.type is invalid")
        if dep.get("dependency_scope") not in ALLOWED_DEPENDENCY_SCOPES:
            errors.append(f"{prefix}.dependency_scope is invalid")
        if not dep.get("description"):
            errors.append(f"{prefix}.description is required")
        producer = dep.get("producer_role")
        if producer not in workflow_roles | RESERVED_PRODUCER_ROLES:
            errors.append(f"{prefix}.producer_role {producer!r} is not a workflow role")
        for consumer in dep.get("consumers") or []:
            if consumer.get("role") not in workflow_roles:
                errors.append(f"{prefix} has unknown consumer role {consumer.get('role')!r}")
        if dep.get("expected_state") not in ALLOWED_EXPECTED_STATES:
            errors.append(f"{prefix}.expected_state is invalid")
        resource_type = dep.get("resource_type")
        if resource_type == "file" and not dep.get("location"):
            errors.append(f"{prefix}.location is required for a file")
        for criterion in dep.get("acceptance_criteria") or []:
            if criterion.get("type") not in ALLOWED_CRITERION_TYPES:
                errors.append(f"{prefix} has invalid criterion type {criterion.get('type')!r}")
            if criterion.get("type") in {"content_contains_all", "content_contains_any"} and not criterion.get("values"):
                errors.append(f"{prefix} has content criterion without literal values")
        confidence = dep.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{prefix}.confidence must be between 0 and 1")
        if not dep.get("evidence"):
            warnings.append(f"{prefix} has no evidence")
        if not dep.get("applicable_actions"):
            errors.append(f"{prefix}.applicable_actions must be non-empty")
        if not dep.get("applicable_stages"):
            errors.append(f"{prefix}.applicable_stages must be non-empty")

    if len(ids) != len(set(ids)):
        errors.append("dependency_id values must be unique")
    id_set = set(ids)
    graph: dict[str, set[str]] = {dep_id: set() for dep_id in ids}
    for dep in dependencies:
        dep_id = dep.get("dependency_id")
        if dep_id not in graph:
            continue
        for prerequisite in dep.get("prerequisites") or []:
            target = prerequisite.get("dependency_id")
            if target not in id_set:
                errors.append(f"{dep_id} references unknown prerequisite {target!r}")
            else:
                graph[dep_id].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"dependency cycle detected at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for upstream in graph[node]:
            visit(upstream)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return ValidationResult(not errors, errors, warnings)


def normalize_specs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate extractor output into DependencyMemoryStore compiler specs."""
    specs = []
    for dep in data["dependencies"]:
        spec = dict(dep)
        spec["required"] = True
        spec["resolution_conditions"] = [
            criterion["specification"] for criterion in dep.get("acceptance_criteria", [])
        ]
        spec["injection_policy"] = "proactive" if dep.get("priority") in {"critical", "high"} else "on_demand"
        specs.append(spec)
    return specs


def consolidate_acceptance_facets(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Fold non-independent product facets into their containing artifact contract.

    A semantic product node is treated as an acceptance facet when it has no concrete
    location, has exactly one prerequisite that is a file artifact from the same
    producer, and has exactly the same workflow consumers as that artifact. A true
    cross-agent interface therefore remains independent.
    """
    import copy

    result = copy.deepcopy(data)
    dependencies = result["dependencies"]
    by_id = {dep["dependency_id"]: dep for dep in dependencies}
    fold_map: dict[str, str] = {}
    decisions: list[dict[str, str]] = []
    for dep in dependencies:
        if dep.get("dependency_scope") != "product" or dep.get("location"):
            continue
        prerequisites = dep.get("prerequisites") or []
        if len(prerequisites) != 1:
            continue
        parent = by_id.get(prerequisites[0].get("dependency_id"))
        if not parent or parent.get("resource_type") != "file":
            continue
        if parent.get("producer_role") != dep.get("producer_role"):
            continue
        parent_consumers = {item.get("role") for item in parent.get("consumers") or []}
        dep_consumers = {item.get("role") for item in dep.get("consumers") or []}
        if parent_consumers != dep_consumers:
            continue
        fold_map[dep["dependency_id"]] = parent["dependency_id"]

    for child_id, parent_id in fold_map.items():
        child = by_id[child_id]
        parent = by_id[parent_id]
        existing_ids = {item.get("criterion_id") for item in parent.get("acceptance_criteria") or []}
        parent.setdefault("acceptance_criteria", [])
        for criterion in child.get("acceptance_criteria") or []:
            folded = copy.deepcopy(criterion)
            base_id = f"{child_id}__{criterion.get('criterion_id', 'criterion')}"
            folded["criterion_id"] = base_id
            suffix = 2
            while folded["criterion_id"] in existing_ids:
                folded["criterion_id"] = f"{base_id}_{suffix}"
                suffix += 1
            existing_ids.add(folded["criterion_id"])
            parent["acceptance_criteria"].append(folded)
        parent.setdefault("keywords", []).extend(
            value for value in child.get("keywords", []) if value not in parent.get("keywords", [])
        )
        parent.setdefault("entities", []).extend(
            value for value in child.get("entities", []) if value not in parent.get("entities", [])
        )
        parent.setdefault("evidence", []).extend(child.get("evidence", []))
        decisions.append({
            "folded_dependency": child_id,
            "into": parent_id,
            "reason": "same producer/consumers, no independent location or lifecycle",
        })

    if fold_map:
        result["dependencies"] = [
            dep for dep in dependencies if dep["dependency_id"] not in fold_map
        ]
        for dep in result["dependencies"]:
            new_prerequisites = []
            seen = set()
            for prerequisite in dep.get("prerequisites") or []:
                item = copy.deepcopy(prerequisite)
                item["dependency_id"] = fold_map.get(item.get("dependency_id"), item.get("dependency_id"))
                key = (item.get("dependency_id"), item.get("required_state"))
                if key not in seen and item.get("dependency_id") != dep["dependency_id"]:
                    new_prerequisites.append(item)
                    seen.add(key)
            dep["prerequisites"] = new_prerequisites
    return result, decisions
