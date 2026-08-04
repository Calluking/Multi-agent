#!/usr/bin/env python3
"""Run feature ablations for dependency, cross-domain, and testing memory."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

import run_interface_panel as base
from coordination_memory import (CONTRIBUTION_INSTRUCTION, ingest_audit,
                                  ingest_contributions, initialize_pool, load_pool,
                                  save_pool, targeted_view)
from interface_memory import compact_view, load_or_empty, save_bank, summarize_audit
from sparse_memory import append_event, fail_open_observe, observe_blocker, recovery_prompt
from testing_practice_memory import make_episode, render_packet, save_packet


DEFAULT_ROOT = Path(__file__).resolve().parent / "runs_feature_ablation"
FEATURES = {
    "baseline": {"dependency": False, "codomain": False, "testing": False, "prework": False},
    "dependency": {"dependency": True, "codomain": False, "testing": False, "prework": False},
    "codomain": {"dependency": False, "codomain": True, "testing": False, "prework": False},
    "both": {"dependency": True, "codomain": True, "testing": False, "prework": False},
    "testing": {"dependency": False, "codomain": False, "testing": True, "prework": False},
    "dependency_testing": {"dependency": True, "codomain": False, "testing": True, "prework": False},
    "codomain_testing": {"dependency": False, "codomain": True, "testing": True, "prework": False},
    "all_three": {"dependency": True, "codomain": True, "testing": True, "prework": False},
    "all_three_prework_v2": {"dependency": True, "codomain": True, "testing": True,
                              "prework": True, "optimized_prework": True},
    "codomain_prework": {"dependency": False, "codomain": True, "testing": False, "prework": True},
    "codomain_prework_v2": {"dependency": False, "codomain": True, "testing": False,
                             "prework": True, "optimized_prework": True},
    "codomain_boundary": {"dependency": False, "codomain": True, "testing": False,
                          "prework": False, "selective": True},
}


PREWORK_PROPOSAL_PROMPT = base.BOUNDARY_EXTRACTOR_PROMPT.replace(
    "Read only TASK.md and AGENTS.md.",
    "Read TASK.md, AGENTS.md, and plan.md. Before implementation begins, act as the producer-side "
    "contract proposer. Do not create solution.py or implementation.md."
)

PREWORK_CONSUMER_PROMPT = """Act as the consumer-side contract negotiator before implementation begins. Read TASK.md, plan.md, interface_memory.json, and the shared coordination memory appended below. Check whether fields, semantics, producer obligations, consumer obligations, invariants, and the boundary test are sufficient for the consumer to implement without guessing. Do not create solution.py or implementation.md.

Write coordination_contributions.json using exactly this top-level shape:
{"contributions": [{"memory_id": "interface:exact_id", "action": "accept", "base_version": 1, "claim": "usable as written"}]}.
Use the key contributions (not events) and action (not event). Emit one decision for every proposed record. If a proposal is usable, accept its exact memory_id and base_version. If incomplete, emit in order: (1) challenge naming the incompatibility, (2) revision with the exact current base_version and a minimal patch resolving it, and (3) accept for the revised version. Keep chat under three lines."""

PREWORK_V2_PRODUCER_PROMPT = """You are the actual Producer Agent assigned to create an artifact in your next turn. Read TASK.md, AGENTS.md, and plan.md. Before working, identify exactly one highest-risk artifact boundary where your output will be used by the downstream Consumer Agent named in the required JSON template. Do not create the artifact yet.

Write interface_memory.json as valid JSON using exactly this shape and exactly one interface:
{"interfaces": [{"interface_id": "short_id", "artifact": "concrete artifact or API", "producer_agent": "__PRODUCER_AGENT_ID__", "consumer_agents": ["__CONSUMER_AGENT_ID__"], "producer": "component that produces it", "consumer": "component or activity that consumes it", "purpose": "why this crossing exists", "task_evidence": "exact task requirement", "risk": 5, "fields": [{"name": "field", "type": "type", "meaning": "semantic meaning"}], "producer_obligations": ["one concrete guarantee"], "consumer_obligations": ["one concrete consumption requirement"], "invariants": ["one cross-boundary invariant"], "boundary_test": {"setup": "concrete setup", "action": "real crossing", "expected": "observable result"}}]}.
All strings must be grounded in this task. This is a proposal for the real work you will perform, not a generic architecture summary. Keep chat under three lines."""

PREWORK_V2_CONSUMER_PROMPT = """You are the actual downstream Consumer Agent that will use or verify the Producer's artifact in your next turn. Read TASK.md, plan.md, interface_memory.json, and the single proposed contract appended below. Before work begins, decide whether this contract gives you enough concrete information to consume the artifact without guessing. Do not consume or modify the artifact yet.

Write coordination_contributions.json as valid JSON with exactly one contribution. If usable without changes, use:
{"contributions": [{"memory_id": "interface:exact_id", "action": "accept", "base_version": 1, "claim": "The consumer can use and verify this artifact without guessing because ..."}]}.
If one or more consumer requirements are missing, use the atomic accept_revision action with a minimal patch containing only valid contract keys:
{"contributions": [{"memory_id": "interface:exact_id", "action": "accept_revision", "base_version": 1, "claim": "Accepted after adding the required consumer detail: ...", "patch": {"consumer_obligations": ["complete revised obligations"], "boundary_test": {"setup": "setup", "action": "crossing", "expected": "observable result"}}}]}.
Do not emit a standalone challenge, introduce another interface, or add unrelated requirements. Keep chat under three lines."""

BOUNDARY_PRODUCER_INSTRUCTION = """

BOUNDARY-SCOPED COORDINATION MEMORY
While implementing the task normally, identify exactly one highest-impact artifact boundary that your work produces and the downstream Reviewer must consume or verify. Do not invent pairwise relationships with unrelated Agents. Write interface_memory.json with exactly one interface record using the normal interface schema plus these routing fields:
{"interfaces": [{"interface_id": "short_id", "artifact": "actual artifact or API", "producer_agent": "implementer_agent", "consumer_agents": ["reviewer_agent"], "producer": "actual producing component", "consumer": "actual consuming component", "purpose": "why the crossing exists", "task_evidence": "exact task requirement", "risk": 5, "fields": [], "producer_obligations": ["one concrete obligation"], "consumer_obligations": ["one concrete obligation"], "invariants": ["one invariant"], "boundary_test": {"setup": "setup", "action": "real producer-to-consumer crossing", "expected": "observable result"}}]}.
The record is visible only to implementer_agent and reviewer_agent. Keep it concise and grounded in the artifact you actually create; do not add a separate negotiation transcript.
"""


def inject_testing_memory(workspace: Path, task_text: str, role: str,
                          prompt: str, *, enabled: bool) -> tuple[str, str, list[str]]:
    """Append a role packet without creating any additional Agent call."""
    packet, selected = render_packet(task_text, role) if enabled else ("", [])
    save_packet(workspace, role, packet, selected)
    combined = prompt + (("\n\n" + packet) if packet else "")
    return combined, packet, selected


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
    task_text = item["task"]["content"]
    selected_testing: dict[str, list[str]] = {}

    agent_id = f"mab-ablation-{condition}-t{task_id:02d}-{uuid.uuid4().hex[:6]}"
    producer_actor = f"agent-{uuid.uuid4().hex[:8]}"
    consumer_actor = f"agent-{uuid.uuid4().hex[:8]}"
    participant_registry = {
        "boundary_routing": "runtime_agent_ids",
        "producer": {"agent_id": producer_actor, "session": run_id + "-implementer"},
        "consumers": [{"agent_id": consumer_actor, "session": run_id + "-reviewer"}],
        "note": "Stage/session bindings belong to this runner; coordination memory routes only by agent_id.",
    }
    (workspace / "coordination_participants.json").write_text(
        json.dumps(participant_registry, indent=2) + "\n", encoding="utf-8"
    )
    base.ensure_agent(agent_id, workspace)
    planner_prompt, planner_testing_packet, selected_testing["planner"] = inject_testing_memory(
        workspace, task_text, "planner", base.BASELINE_PLANNER_PROMPT,
        enabled=features["testing"],
    )
    planner, planner_error = safe_stage_call(
        workspace, agent_id, run_id + "-planner", planner_prompt, "planner"
    )

    bank_path = workspace / "interface_memory.json"
    pool_path = workspace / "coordination_memory.json"
    pool_events = workspace / "coordination_memory_events.jsonl"
    prework_proposal = prework_feedback = None
    prework_proposal_error = prework_feedback_error = None
    prework_contract_valid = True
    prework_contributions = {"submitted": 0, "applied": 0, "rejected": 0}
    if features["prework"]:
        optimized_prework = features.get("optimized_prework", False)
        producer_prompt = PREWORK_V2_PRODUCER_PROMPT if optimized_prework else PREWORK_PROPOSAL_PROMPT
        if optimized_prework:
            producer_prompt = (producer_prompt
                .replace("__PRODUCER_AGENT_ID__", producer_actor)
                .replace("__CONSUMER_AGENT_ID__", consumer_actor))
        producer_session = run_id + ("-implementer" if optimized_prework else "-prework-producer")
        prework_proposal, prework_proposal_error = safe_stage_call(
            workspace, agent_id, producer_session,
            producer_prompt, "codomain_prework_proposal",
        )
        prework_bank = load_or_empty(bank_path, task_id, run_id)
        if optimized_prework and len(prework_bank.get("interfaces", [])) > 1:
            prework_bank["interfaces"] = prework_bank["interfaces"][:1]
        if optimized_prework and len(prework_bank.get("interfaces", [])) != 1:
            prework_contract_valid = False
            prework_proposal_error = prework_proposal_error or "prework_v2 produced no valid boundary contract"
        save_bank(bank_path, prework_bank)
        prework_pool = initialize_pool(
            prework_bank, task_id, run_id,
            actor=producer_actor if optimized_prework else "producer_agent"
        )
        save_pool(pool_path, prework_pool)
        consumer_view = targeted_view(
            prework_pool,
            actor=consumer_actor if optimized_prework else "consumer_agent",
            limit=1 if optimized_prework else 3,
        )
        consumer_prompt = (
            PREWORK_V2_CONSUMER_PROMPT if optimized_prework else PREWORK_CONSUMER_PROMPT
        ) + "\n\n" + consumer_view
        consumer_session = run_id + ("-reviewer" if optimized_prework else "-prework-consumer")
        prework_feedback, prework_feedback_error = safe_stage_call(
            workspace, agent_id, consumer_session,
            consumer_prompt, "codomain_prework_feedback",
        )
        prework_contributions = ingest_contributions(
            workspace / "coordination_contributions.json", prework_pool,
            actor=consumer_actor if optimized_prework else "consumer_agent",
            event_log=pool_events,
        )
        if optimized_prework:
            agreed_records = [r for r in prework_pool.get("records", [])
                              if r.get("status") == "agreed"]
            if len(agreed_records) != 1:
                prework_contract_valid = False
                prework_feedback_error = prework_feedback_error or (
                    "prework_v2 consumer did not produce exactly one agreed contract"
                )
        save_pool(pool_path, prework_pool)
        (workspace / "prework_coordination_memory.json").write_text(
            json.dumps(prework_pool, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    implementation_contract = ""
    if features["prework"]:
        implementation_contract = targeted_view(
            load_pool(pool_path, task_id, run_id),
            actor=producer_actor if features.get("optimized_prework") else "implementer_agent",
            limit=1 if features.get("optimized_prework") else 3,
        )
    implementer_prompt, implementer_testing_packet, selected_testing["implementer"] = inject_testing_memory(
        workspace, task_text, "implementer", base.IMPLEMENTER_PROMPT,
        enabled=features["testing"],
    )
    if features.get("selective"):
        implementer_prompt += BOUNDARY_PRODUCER_INSTRUCTION
    if implementation_contract:
        implementer_prompt += "\n\n" + implementation_contract + "\n\n" + (
            "PREWORK CONTRACT IS BINDING: produce the named artifact according to the resolved "
            "interface, producer obligations, and invariants. The downstream Consumer owns its listed "
            "obligations and will execute the boundary test; do not implement work assigned only to it."
        )
    implementer1, impl_error = safe_stage_call(
        workspace, agent_id, run_id + "-implementer", implementer_prompt, "implementer_pass1"
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

    if features.get("selective"):
        selective_bank = load_or_empty(bank_path, task_id, run_id)
        if len(selective_bank.get("interfaces", [])) > 1:
            selective_bank["interfaces"] = selective_bank["interfaces"][:1]
        save_bank(bank_path, selective_bank)
        selective_pool = initialize_pool(
            selective_bank, task_id, run_id, actor="implementer_agent"
        )
        save_pool(pool_path, selective_pool)

    integration = None
    integration_error = None
    if (features["codomain"] and not features["prework"] and not features.get("selective")
            and (workspace / "solution.py").is_file()):
        integration, integration_error = safe_stage_call(
            workspace, agent_id, run_id + "-integration",
            base.POSTHOC_INTEGRATION_PROMPT, "codomain_integration",
        )
    bank = load_or_empty(bank_path, task_id, run_id)
    if features["codomain"]:
        save_bank(bank_path, bank)
    pool = load_pool(pool_path, task_id, run_id)
    if features["codomain"] and not pool.get("records"):
        pool = initialize_pool(bank, task_id, run_id, actor="integration_agent")
        save_pool(pool_path, pool)
    review_actor = consumer_actor if features.get("optimized_prework") else "reviewer_agent"
    review_memory = targeted_view(
        pool, actor=review_actor,
        limit=1 if (features.get("selective") or features.get("optimized_prework")) else 3
    ) if features["codomain"] else ""
    audit = """

SHARED BOUNDARY AGREEMENT AUDIT
For each shared interface-memory record, exercise the real producer-to-consumer path. Repair semantic mismatches. Create interface_audit.json as valid JSON: {"interfaces": [{"interface_id": "exact ID", "passed": true, "evidence": ["exact observation"], "blocker": null}]}. Do not infer success from class names or isolated unit tests."""
    reviewer_base, reviewer_testing_packet, selected_testing["reviewer"] = inject_testing_memory(
        workspace, task_text, "reviewer", base.REVIEWER_PROMPT,
        enabled=features["testing"],
    )
    reviewer_prompt = reviewer_base + (("\n\n" + review_memory + CONTRIBUTION_INSTRUCTION + audit)
                                        if review_memory else "")
    (workspace / "reviewer_interface_memory.txt").write_text(review_memory, encoding="utf-8")
    reviewer1, review_error = safe_stage_call(
        workspace, agent_id, run_id + "-reviewer", reviewer_prompt, "reviewer_pass1"
    )
    contribution_summary = (ingest_contributions(
        workspace / "coordination_contributions.json", pool,
        actor=review_actor, event_log=pool_events,
    ) if features["codomain"] else {"submitted": 0, "applied": 0, "rejected": 0})
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

    # In codomain-only runs an incomplete implementer may leave no artifact for
    # the pre-review integration hook, while the reviewer subsequently creates
    # or repairs solution.py.  Do not permanently miss the memory mechanism:
    # initialize it at the first later point where a real artifact exists, then
    # run a second boundary-aware review to produce current audit evidence.
    late_integration = None
    late_integration_error = None
    late_reviewer = None
    late_reviewer_error = None
    if (features["codomain"] and not features["prework"] and not features.get("selective") and integration is None
            and (workspace / "solution.py").is_file()):
        late_integration, late_integration_error = safe_stage_call(
            workspace, agent_id, run_id + "-late-integration",
            base.POSTHOC_INTEGRATION_PROMPT, "codomain_late_integration",
        )
        if late_integration is not None:
            integration = late_integration
            bank = load_or_empty(bank_path, task_id, run_id)
            save_bank(bank_path, bank)
            pool = initialize_pool(bank, task_id, run_id, actor="integration_agent")
            save_pool(pool_path, pool)
            late_memory = targeted_view(pool, actor="reviewer_agent", limit=3)
            late_prompt = reviewer_base + (("\n\n" + late_memory
                + CONTRIBUTION_INSTRUCTION + audit) if late_memory else "")
            (workspace / "late_reviewer_interface_memory.txt").write_text(
                late_memory, encoding="utf-8")
            late_reviewer, late_reviewer_error = safe_stage_call(
                workspace, agent_id, run_id + "-late-reviewer",
                late_prompt, "codomain_late_reviewer",
            )
            late_contributions = ingest_contributions(
                workspace / "coordination_contributions.json", pool,
                actor="reviewer_agent", event_log=pool_events,
            )
            contribution_summary = {
                key: contribution_summary.get(key, 0) + late_contributions.get(key, 0)
                for key in ("submitted", "applied", "rejected")
            }
            review_verification = base.verify_solution(workspace)

    interface_summary = summarize_audit(workspace / "interface_audit.json", bank) if features["codomain"] else {
        "records": 0, "verified": 0, "failed": 0
    }
    if features["codomain"]:
        audit_contributions = ingest_audit(
            workspace / "interface_audit.json", pool,
            actor=review_actor, event_log=pool_events,
        )
        save_pool(pool_path, pool)
        save_bank(bank_path, bank)
    else:
        audit_contributions = {"submitted": 0, "applied": 0, "rejected": 0}

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
        "coordination_participants": participant_registry,
        "objective": review_verification,
        "task_scores": {**scores, "mean": sum(scores.values()) / 4, "percentage": sum(scores.values()) * 5},
        "score_valid": score_valid, "required_artifacts": required,
        "workflow_complete": all(required.values()) and prework_contract_valid,
        "dependency_memory": {
            "implementer_blocker": impl_blocker.to_dict() if impl_blocker else None,
            "reviewer_blocker": review_blocker.to_dict() if review_blocker else None,
            "implementer_recovery": implementer2 is not None,
            "reviewer_recovery": reviewer2 is not None,
            "injected_chars": len(impl_recovery_text) + len(review_recovery_text),
        },
        "codomain_memory": {**interface_summary, "integration_called": integration is not None,
                            "mode": ("boundary_scoped_inline" if features.get("selective") else
                                     ("prework_v2_real_sessions" if features.get("optimized_prework") else
                                      ("prework_negotiation" if features["prework"] else "posthoc_integration"))),
                            "contract_valid": prework_contract_valid,
                            "prework_proposal_called": prework_proposal is not None,
                            "prework_feedback_called": prework_feedback is not None,
                            "prework_contributions": prework_contributions,
                            "implementation_injected_chars": len(implementation_contract),
                            "review_injected_chars": len(review_memory),
                            "coordination_records": len(pool.get("records", [])),
                            "agent_contributions": contribution_summary,
                            "audit_contributions": audit_contributions,
                            "open_challenges": sum(1 for record in pool.get("records", [])
                                for challenge in record.get("open_challenges", [])
                                if challenge.get("status") == "open")},
        "testing_memory": {
            "enabled": features["testing"],
            "mode": "inject_only",
            "selected_by_role": selected_testing,
            "injected_chars": {
                "planner": len(planner_testing_packet),
                "implementer": len(implementer_testing_packet),
                "reviewer": len(reviewer_testing_packet),
                "total": len(planner_testing_packet) + len(implementer_testing_packet)
                         + len(reviewer_testing_packet),
            },
            "extra_agent_calls": 0,
            "rerouting": False,
            "automatic_retry": False,
        },
        "stage_meta": {
            "planner": base.stage_meta(planner), "implementer_pass1": base.stage_meta(implementer1),
            "codomain_prework_proposal": base.stage_meta(prework_proposal),
            "codomain_prework_feedback": base.stage_meta(prework_feedback),
            "implementer_recovery": base.stage_meta(implementer2), "codomain_integration": base.stage_meta(integration),
            "reviewer_pass1": base.stage_meta(reviewer1), "reviewer_recovery": base.stage_meta(reviewer2),
            "codomain_late_integration": base.stage_meta(late_integration),
            "codomain_late_reviewer": base.stage_meta(late_reviewer),
            "judge": base.stage_meta(judge),
        },
        "stage_errors": {
            "planner": planner_error, "implementer": impl_error, "implementer_recovery": impl_recovery_error,
            "codomain_prework_proposal": prework_proposal_error,
            "codomain_prework_feedback": prework_feedback_error,
            "codomain_integration": integration_error, "reviewer": review_error,
            "reviewer_recovery": review_recovery_error, "judge": judge_error,
            "codomain_late_integration": late_integration_error,
            "codomain_late_reviewer": late_reviewer_error,
        },
        "input_hashes": hashes, "wall_time_seconds": time.time() - started,
    }
    if features["testing"]:
        episode = make_episode(task_id=task_id, run_id=run_id, condition=condition,
                               selected_by_role=selected_testing, result=result)
        (workspace / "testing_episode.json").write_text(
            json.dumps(episode, indent=2) + "\n", encoding="utf-8")
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
