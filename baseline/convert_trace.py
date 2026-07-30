#!/usr/bin/env python3
"""Convert a clean OpenClaw artifact workflow into auditable MAB evaluator inputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def text(name: str) -> str:
    path = ROOT / name
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def raw(name: str) -> dict:
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def timestamp(name: str) -> str | None:
    path = ROOT / name
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def stage_meta(name: str) -> dict:
    data = raw(name + ".json")
    meta = data.get("result", {}).get("meta", {})
    agent_meta = meta.get("agentMeta", {})
    return {
        "status": data.get("status"),
        "duration_ms": meta.get("durationMs"),
        "usage": agent_meta.get("usage", {}),
        "tool_summary": meta.get("toolSummary", {}),
        "stop_reason": meta.get("stopReason"),
        "fallback_used": meta.get("executionTrace", {}).get("fallbackUsed"),
    }


def main() -> None:
    task = text("TASK.md")
    plan = text("plan.md")
    implementation = text("implementation.md")
    review = text("review.md")
    final_output = text("final_test.stdout")

    stages = {
        "planner": stage_meta("planner"),
        "implementer": stage_meta("implementer"),
        "reviewer": stage_meta("reviewer"),
    }
    trace = {
        "schema": "openclaw-to-multiagentbench-trace-v1",
        "conversion": {
            "method": "deterministic artifact conversion; no LLM used",
            "source": str(ROOT),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "inferences": [
                "Workspace artifacts are treated as asynchronous inter-agent messages.",
                "Agent roles are derived from the explicit launcher stage prompts.",
                "Artifact modification times approximate handoff completion times.",
            ],
            "limitations": [
                "Not a native MARBLE event stream.",
                "No direct private reasoning or token-level message transcript is reconstructed.",
                "Communication scores are adapted and not leaderboard-comparable.",
            ],
        },
        "agents": [
            {"agent_id": "planner", "profile": "architecture, requirements, dependencies, tests"},
            {"agent_id": "implementer", "profile": "implementation and initial executable tests"},
            {"agent_id": "reviewer", "profile": "independent audit, edge tests, repair authority"},
        ],
        "task": task,
        "stages": stages,
        "events": [
            {
                "event": "artifact_handoff",
                "from": "planner",
                "to": "implementer",
                "artifact": "plan.md",
                "timestamp": timestamp("plan.md"),
                "content": plan,
            },
            {
                "event": "artifact_handoff",
                "from": "implementer",
                "to": "reviewer",
                "artifact": "implementation.md + solution.py",
                "timestamp": timestamp("implementation.md"),
                "content": implementation,
            },
            {
                "event": "artifact_handoff",
                "from": "reviewer",
                "to": "team",
                "artifact": "review.md + test_edge_cases.py",
                "timestamp": timestamp("review.md"),
                "content": review,
            },
        ],
        "objective_result": {
            "compile_exit": int(text("final_compile.exit").strip() or -1),
            "test_exit": int(text("final_test.exit").strip() or -1),
            "test_output": final_output,
            "reviewer_edge_test_claim": "24 passed, 0 failed" if "24/24 PASS" in review else None,
        },
    }
    (ROOT / "converted_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    communications = "\n\n".join(
        f"From {event['from']} to {event['to']} via {event['artifact']}:\n{event['content']}"
        for event in trace["events"]
    )
    profiles = "\n".join(
        f"{agent['agent_id']}: {agent['profile']}" for agent in trace["agents"]
    )
    agent_tasks = (
        "planner: convert the task into architecture, dependencies, requirement mapping, and tests\n"
        "implementer: implement plan and task, execute initial tests, document exact result\n"
        "reviewer: independently audit requirements, add edge tests, repair if needed, rerun tests"
    )
    results = (
        f"Planner result:\n{plan}\n\nImplementer result:\n{implementation}\n\n"
        f"Reviewer result:\n{review}\n\nFinal objective output:\n{final_output}"
    )
    inputs = {
        "task": task,
        "communication": {"communications": communications},
        "planning": {
            "summary": "Fresh three-stage run; no previous coordination round.",
            "agent_profiles": profiles,
            "agent_tasks": agent_tasks,
            "results": results,
        },
    }
    (ROOT / "coordination_evaluator_inputs.json").write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    communication_prompt = f"""
[Context]
**Task:** {task}

**Communications:** {communications}

[System]
Evaluate the communication quality between agents in the Graph structure. Focus on:
- **Information Exchange:** Was relevant information effectively transmitted?
- **Clarity:** Were intentions and messages clear?
- **Task Assistance:** Did communication help task completion?
- **Efficiency:** Was communication concise and purposeful?

Rate on a 5-point scale:
1. Poor communication with major failures.
2. Significant issues in clarity or relevance.
3. Adequate but required clarification.
4. Effective with minor improvements needed.
5. Clear, effective communication that maximized efficiency.

Respond with ONLY: {{"rating": X}}
"""
    planning_prompt = f"""
[Context]
**Summary:** Fresh three-stage run; no previous coordination round.

**Agent Profiles:** {profiles}

**Agent Tasks:** {agent_tasks}

**Results:** {results}

[System]
Evaluate the effectiveness of agent self-coordination in the Graph structure. Focus on:
- **Role Clarity:** Did agents understand their roles and responsibilities?
- **Task Alignment:** Were tasks aligned with goals?
- **Autonomy:** Did agents work independently without central oversight?

Rate on a 5-point scale:
1. Very poor self-coordination, with major inefficiencies.
2. Frequent role confusion, causing inefficiencies.
3. Moderate overlap or confusion in roles.
4. Effective with minor role clarification needed.
5. Clear roles, effective self-coordination.

Respond with ONLY: {{"rating": X}}
"""
    (ROOT / "communication_evaluator_prompt.md").write_text(
        communication_prompt, encoding="utf-8"
    )
    (ROOT / "planning_evaluator_prompt.md").write_text(
        planning_prompt, encoding="utf-8"
    )
    print(json.dumps({"events": len(trace["events"]), "stages": stages}, indent=2))


if __name__ == "__main__":
    main()
