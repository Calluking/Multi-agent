#!/usr/bin/env python3
"""Parse MAB ratings from OpenClaw envelopes and compute adapted coordination score."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def visible_text(name: str) -> str:
    envelope = json.loads((ROOT / name).read_text(encoding="utf-8"))
    return "\n".join(
        item.get("text", "")
        for item in envelope.get("result", {}).get("payloads", [])
        if isinstance(item, dict)
    )


def rating(content: str) -> int:
    matches = re.findall(r'\{\s*"rating"\s*:\s*([1-5])\s*\}', content)
    if not matches:
        raise ValueError("No valid rating object found")
    return int(matches[-1])


communication_text = visible_text("communication_score_raw.json")
planning_text = visible_text("planning_score_raw.json")
communication = rating(communication_text)
planning = rating(planning_text)
coordination = (communication + planning) / 2

result = {
    "schema": "adapted-multiagentbench-coordination-score-v1",
    "communication_score": communication,
    "planning_score": planning,
    "coordination_score": coordination,
    "coordination_percentage": coordination * 20,
    "task_score": json.loads((ROOT / "mab_score.json").read_text(encoding="utf-8")),
    "comparability": "adapted; not leaderboard-comparable",
    "trace": "converted_trace.json",
    "evaluator_inputs": "coordination_evaluator_inputs.json",
    "raw_responses": ["communication_score_raw.json", "planning_score_raw.json"],
}
(ROOT / "coordination_score.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)

report = f"""# Adapted MultiAgentBench coordination score

| Metric | Score |
| --- | ---: |
| Communication Score | {communication}/5 ({communication * 20:.0f}%) |
| Planning Score | {planning}/5 ({planning * 20:.0f}%) |
| Coordination Score | {coordination:.1f}/5 ({coordination * 20:.0f}%) |
| Coding Task Score | {result['task_score']['mean']:.2f}/5 ({result['task_score']['percentage']}%) |

MultiAgentBench defines Coordination Score as the mean of Communication Score and Planning Score.

## Interpretation

The official prompts judged the artifact handoffs clear, complete, role-aligned, and efficient. Planner, implementer, and reviewer all completed their assigned stages; compilation succeeded; 47 built-in and 24 reviewer edge tests passed.

## Comparability warning

This score is **adapted, not leaderboard-comparable**. The converter maps OpenClaw workspace artifacts to communications because native OpenClaw did not produce MARBLE message objects. The official communication prompt says “Graph structure,” while this run was a sequential artifact pipeline. The rubric also does not penalize the absence of graph-mesh discussion, so 5/5 is probably optimistic for cross-framework comparison.
"""
(ROOT / "COORDINATION_SCORE.md").write_text(report, encoding="utf-8")
print(json.dumps(result, indent=2))
