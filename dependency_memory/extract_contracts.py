#!/usr/bin/env python3
"""CLI: ask an OpenClaw agent to extract dependency contracts and compile complete YAML."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml

from contract_extractor import (
    build_extraction_prompt,
    consolidate_acceptance_facets,
    normalize_specs,
    parse_model_yaml,
    validate_extraction,
)
from dependency_memory import DependencyMemoryStore


MODEL = "deepseek/deepseek-v4-flash"


def run(command: list[str], cwd: Path, timeout: int = 660) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def payload_text(envelope: dict) -> str:
    return "\n".join(
        item.get("text", "") for item in envelope.get("result", {}).get("payloads", [])
        if isinstance(item, dict)
    )


def ensure_agent(agent_id: str, workspace: Path) -> None:
    proc = run([
        "openclaw", "agents", "add", agent_id, "--non-interactive",
        "--workspace", str(workspace), "--model", MODEL, "--json",
    ], workspace, 120)
    (workspace / "agent_add.stdout").write_text(proc.stdout, encoding="utf-8")
    (workspace / "agent_add.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(proc.stderr or proc.stdout)
    for _ in range(20):
        listed = run(["openclaw", "agents", "list", "--json"], workspace, 60)
        if listed.returncode == 0:
            try:
                if any(item.get("id") == agent_id for item in json.loads(listed.stdout)):
                    # The configuration list can update before the gateway reloads it.
                    time.sleep(5)
                    return
            except json.JSONDecodeError:
                pass
        time.sleep(1)
    raise RuntimeError(f"Agent {agent_id} did not become discoverable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    task_path = args.task.expanduser().resolve()
    workflow_path = args.workflow.expanduser().resolve()
    task_text = task_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    run_id = args.run_id or f"contract-extraction-{int(time.time())}"
    workspace = args.output_dir.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "task_input.md").write_text(task_text, encoding="utf-8")
    (workspace / "workflow_input.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8"
    )
    prompt = build_extraction_prompt(task_text, workflow)
    (workspace / "extraction_prompt.md").write_text(prompt, encoding="utf-8")

    agent_id = f"dependency-contract-extractor-{int(time.time())}"
    ensure_agent(agent_id, workspace)
    current_prompt = prompt
    extracted = None
    validation = None
    raw_text = ""
    for attempt in range(1, 4):
        proc = None
        for gateway_attempt in range(1, 7):
            proc = run([
                "openclaw", "agent", "--agent", agent_id, "--session-id", run_id,
                "--model", MODEL, "--thinking", "off", "--timeout", "600",
                "--json", "--message", current_prompt,
            ], workspace)
            if "unknown agent id" not in (proc.stderr or "").lower():
                break
            time.sleep(5 * gateway_attempt)
        assert proc is not None
        (workspace / f"extractor_attempt_{attempt}.stdout.json").write_text(proc.stdout, encoding="utf-8")
        (workspace / f"extractor_attempt_{attempt}.stderr").write_text(proc.stderr, encoding="utf-8")
        if not proc.stdout.strip():
            raise RuntimeError(proc.stderr or "Extractor returned no output")
        envelope = json.loads(proc.stdout)
        raw_text = payload_text(envelope)
        (workspace / f"extracted_attempt_{attempt}.txt").write_text(raw_text, encoding="utf-8")
        try:
            extracted = parse_model_yaml(raw_text)
        except ValueError:
            generated_artifact = None
            extracted = None
            excluded = {"workflow_input.yaml", "compiled_dependency_memory.yaml", "extracted_contracts.yaml"}
            candidates = sorted(
                [*workspace.glob("*.yaml"), *workspace.glob("*.yml")],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for candidate in candidates:
                if candidate.name in excluded:
                    continue
                try:
                    candidate_data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                except yaml.YAMLError:
                    continue
                if isinstance(candidate_data, dict) and isinstance(candidate_data.get("dependencies"), list):
                    generated_artifact = candidate
                    extracted = candidate_data
                    break
            if generated_artifact is None or extracted is None:
                (workspace / f"parse_failure_attempt_{attempt}.txt").write_text(
                    "No dependency YAML was returned inline or written as an artifact.\n" + raw_text,
                    encoding="utf-8",
                )
                current_prompt = (
                    "The previous response contained no parseable dependency YAML. "
                    "Return the COMPLETE YAML document required by the original extraction request. "
                    "You may output it directly or write exactly one YAML artifact in this workspace. "
                    "Do not return a prose summary."
                )
                continue
        validation = validate_extraction(extracted, workflow)
        (workspace / f"validation_attempt_{attempt}.json").write_text(json.dumps({
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }, indent=2) + "\n", encoding="utf-8")
        if validation.valid:
            break
        current_prompt = (
            "Your proposed dependency YAML failed schema validation. Return the complete corrected YAML only. "
            "Do not omit valid dependencies merely to hide an error.\n\nValidation errors:\n- "
            + "\n- ".join(validation.errors)
            + "\n\nPrevious proposal:\n"
            + yaml.safe_dump(extracted, sort_keys=False, allow_unicode=True)
        )
    if extracted is None or validation is None:
        print(json.dumps({"valid": False, "errors": ["No parseable dependency YAML after three attempts"]}, indent=2))
        return 2
    consolidation_decisions = []
    if validation.valid:
        extracted, consolidation_decisions = consolidate_acceptance_facets(extracted)
        validation = validate_extraction(extracted, workflow)
        (workspace / "consolidation.json").write_text(
            json.dumps(consolidation_decisions, indent=2) + "\n", encoding="utf-8"
        )
    (workspace / "extracted_raw.txt").write_text(raw_text, encoding="utf-8")
    (workspace / "validation.json").write_text(json.dumps({
        "valid": validation.valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "consolidated_facets": consolidation_decisions,
    }, indent=2) + "\n", encoding="utf-8")
    (workspace / "extracted_contracts.yaml").write_text(
        yaml.safe_dump(extracted, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    if not validation.valid:
        print(json.dumps({"valid": False, "errors": validation.errors}, indent=2))
        return 2

    stages = workflow.get("stages", [])
    store = DependencyMemoryStore(workspace, workspace / "compiled_dependency_memory.yaml")
    evidence = []
    confidence_values = []
    for dep in extracted["dependencies"]:
        confidence_values.append(float(dep.get("confidence", 0.5)))
        evidence.extend(
            f"{item.get('source')}: {item.get('text')}" for item in dep.get("evidence", [])
        )
    store.compile_contracts(
        system_id=workflow.get("system_id", "multi-agent-workflow"),
        task_id=str(args.task_id),
        run_id=run_id,
        workflow_id=workflow.get("workflow_id", "workflow"),
        producer_role=None,
        consumer_role=None,
        artifacts=normalize_specs(extracted),
        extraction_provenance={
            "extraction_method": "llm_semantic_extraction",
            "source_agent_id": agent_id,
            "source_events": [{
                "event_type": "contract_extraction",
                "event_id": run_id,
                "observation": f"Extracted {len(extracted['dependencies'])} proposed dependencies",
            }],
            "evidence_refs": evidence,
            "confidence": sum(confidence_values) / max(1, len(confidence_values)),
            "inferred_fields": [
                "dependency", "contract", "ownership", "recovery", "selection"
            ],
            "verified_fields": ["scope.task_id", "scope.run_id"],
        },
    )
    result = {
        "valid": True,
        "dependency_count": len(extracted["dependencies"]),
        "dependency_ids": [dep["dependency_id"] for dep in extracted["dependencies"]],
        "workflow_roles": [stage.get("role") for stage in stages],
        "output": str(store.store_path),
        "warnings": validation.warnings,
    }
    (workspace / "extraction_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
