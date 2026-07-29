#!/usr/bin/env python3
"""Validate an extracted dependency YAML file and compile complete memory records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from contract_extractor import consolidate_acceptance_facets, normalize_specs, validate_extraction
from dependency_memory import DependencyMemoryStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-agent", default="semantic-contract-extractor")
    args = parser.parse_args()

    contracts_path = args.contracts.expanduser().resolve()
    workflow_path = args.workflow.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    output = args.output.expanduser().resolve()
    extracted = yaml.safe_load(contracts_path.read_text(encoding="utf-8"))
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    validation = validate_extraction(extracted, workflow)
    if not validation.valid:
        print(json.dumps({"valid": False, "errors": validation.errors}, indent=2))
        return 2
    extracted, consolidation_decisions = consolidate_acceptance_facets(extracted)
    validation = validate_extraction(extracted, workflow)
    if not validation.valid:
        print(json.dumps({"valid": False, "errors": validation.errors}, indent=2))
        return 2
    (output.parent / "consolidation.json").write_text(
        json.dumps(consolidation_decisions, indent=2) + "\n", encoding="utf-8"
    )

    evidence = []
    confidence = []
    for dep in extracted["dependencies"]:
        confidence.append(float(dep.get("confidence", 0.5)))
        evidence.extend(f"{item.get('source')}: {item.get('text')}" for item in dep.get("evidence", []))
    store = DependencyMemoryStore(workspace, output)
    store.compile_contracts(
        system_id=workflow.get("system_id", "multi-agent-workflow"),
        task_id=str(args.task_id),
        run_id=args.run_id,
        workflow_id=workflow.get("workflow_id", "workflow"),
        producer_role=None,
        consumer_role=None,
        artifacts=normalize_specs(extracted),
        extraction_provenance={
            "extraction_method": "llm_semantic_extraction",
            "source_agent_id": args.source_agent,
            "source_events": [{
                "event_type": "contract_extraction",
                "event_id": args.run_id,
                "observation": f"Compiled {len(extracted['dependencies'])} validated dependencies",
            }],
            "evidence_refs": evidence,
            "confidence": sum(confidence) / max(1, len(confidence)),
            "inferred_fields": ["dependency", "contract", "ownership", "recovery", "selection"],
            "verified_fields": ["scope.task_id", "scope.run_id"],
        },
    )
    print(json.dumps({
        "valid": True,
        "dependency_count": len(extracted["dependencies"]),
        "output": str(output),
        "warnings": validation.warnings,
        "consolidated_facets": consolidation_decisions,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
