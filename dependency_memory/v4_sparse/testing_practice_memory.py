#!/usr/bin/env python3
"""Inject-only semantic testing-practice memory.

This module performs deterministic retrieval and prompt rendering.  It never
creates an Agent turn, blocks a handoff, reroutes work, or requests a retry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_BANK = HERE / "testing_practices.json"
ROLE_HINTS = {
    "planner": "Translate the selected practice into acceptance criteria and planned executable checks.",
    "implementer": "Use the selected practice while implementing and designing tests; do not optimize tests merely for green output.",
    "reviewer": "Audit the original requirement independently and reject unsupported PASS claims.",
}


def load_bank(path: Path = DEFAULT_BANK) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("memory_type") != "semantic_testing_practice_bank":
        raise ValueError("invalid testing practice bank")
    if not isinstance(raw.get("practices"), list):
        raise ValueError("testing practice bank has no practices")
    return raw


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_+-]+", text.lower()))


def _score(item: dict[str, Any], task_text: str, role: str) -> float:
    lowered = task_text.lower()
    task_terms = _terms(task_text)
    score = 0.0
    for trigger in item.get("triggers", []):
        phrase = str(trigger).lower().strip()
        if not phrase:
            continue
        if phrase in lowered:
            score += 4.0 if " " in phrase else 2.0
        else:
            overlap = len(_terms(phrase) & task_terms)
            score += 0.35 * overlap
    if role in item.get("roles", []):
        score += 1.5
    score += float(item.get("confidence", 0.0)) * 0.25
    return score


def retrieve(task_text: str, role: str, *, limit: int = 2,
             bank: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    source = bank or load_bank()
    eligible = [item for item in source["practices"] if role in item.get("roles", [])]
    ranked = sorted(eligible,
                    key=lambda item: (-_score(item, task_text, role), item["practice_id"]))
    selected = [item for item in ranked if _score(item, task_text, role) >= 1.5]
    return selected[:limit]


def render_packet(task_text: str, role: str, *, limit: int = 2,
                  bank: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    selected = retrieve(task_text, role, limit=limit, bank=bank)
    if not selected:
        return "", []
    lines = [
        "TEAM VERIFICATION PRACTICE MEMORY — INJECT-ONLY",
        f"Target role: {role}. This memory adds guidance only; it does not add turns, retries, gates, or rerouting.",
        ROLE_HINTS.get(role, "Apply only practices relevant to the current work."),
    ]
    for index, item in enumerate(selected, 1):
        lines += [
            f"\nPRACTICE {index}: {item['title']} [memory_id={item['practice_id']}]",
            "Rule: " + item["rule"],
            "Invalid evidence: " + "; ".join(item.get("invalid_substitutes", [])),
            "Required evidence: " + "; ".join(item.get("required_evidence", [])),
        ]
    return "\n".join(lines), [item["practice_id"] for item in selected]


def save_packet(workspace: Path, role: str, packet: str,
                selected_ids: list[str]) -> None:
    (workspace / f"testing_memory_{role}.txt").write_text(packet, encoding="utf-8")
    (workspace / f"testing_memory_{role}.json").write_text(json.dumps({
        "memory_type": "role_working_memory",
        "role": role,
        "selected_practices": selected_ids,
        "injected_chars": len(packet),
        "mode": "inject_only",
    }, indent=2) + "\n", encoding="utf-8")


def make_episode(*, task_id: int, run_id: str, condition: str,
                 selected_by_role: dict[str, list[str]], result: dict[str, Any]) -> dict[str, Any]:
    """Create compact history after the run; this has no control-flow effect."""
    return {
        "schema_version": "0.1",
        "memory_type": "testing_episode",
        "task_id": task_id,
        "run_id": run_id,
        "condition": condition,
        "selected_practices": selected_by_role,
        "outcome": {
            "workflow_complete": result.get("workflow_complete"),
            "objective": result.get("objective"),
            "task_scores": result.get("task_scores"),
            "required_artifacts": result.get("required_artifacts"),
        },
        "control_effect": "none",
    }
