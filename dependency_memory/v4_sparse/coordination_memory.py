#!/usr/bin/env python3
"""Shared coordination-memory pool for cross-domain interface negotiation.

The pool keeps an append-only contribution history and a compact resolved
projection.  Agents exchange typed events rather than appending free-form chat.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_ACTIONS = {"proposal", "challenge", "revision", "accept", "verification"}
MAX_HISTORY = 50
MAX_CONTRIBUTIONS_PER_TURN = 10


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_pool(task_id: int, run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.2",
        "task_id": task_id,
        "run_id": run_id,
        "memory_type": "shared_coordination_pool",
        "records": [],
    }


def _contract(item: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(item.get(key)) for key in (
        "interface_id", "producer", "consumer", "purpose", "task_evidence",
        "risk", "fields", "producer_obligations", "consumer_obligations",
        "invariants", "boundary_test",
    )}


def initialize_pool(bank: dict[str, Any], task_id: int, run_id: str,
                    actor: str = "planner_agent") -> dict[str, Any]:
    """Create one versioned coordination record per normalized interface."""
    pool = empty_pool(task_id, run_id)
    for item in bank.get("interfaces", []):
        interface_id = str(item.get("interface_id", "")).strip()
        if not interface_id:
            continue
        contract = _contract(item)
        pool["records"].append({
            "memory_id": f"interface:{interface_id}",
            "memory_type": "interface_contract",
            "scope": "boundary",
            "participants": {
                "producer": item.get("producer"),
                "consumers": [item.get("consumer")],
                "reviewers": ["reviewer_agent"],
            },
            "version": 1,
            "status": "proposed",
            "resolved": contract,
            "open_challenges": [],
            "verification": {"state": "pending", "evidence": [], "blocker": None},
            "history": [{
                "event_id": f"interface:{interface_id}:v1:proposal",
                "at": utc_now(),
                "actor": actor,
                "action": "proposal",
                "base_version": 0,
                "version": 1,
                "claim": "Initial contract extracted from task requirements",
            }],
        })
    return pool


def load_pool(path: Path, task_id: int, run_id: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("memory_type") != "shared_coordination_pool" or not isinstance(raw.get("records"), list):
            raise ValueError("invalid pool")
        return raw
    except Exception:
        return empty_pool(task_id, run_id)


def save_pool(path: Path, pool: dict[str, Any]) -> None:
    path.write_text(json.dumps(pool, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _record(pool: dict[str, Any], memory_id: str) -> dict[str, Any] | None:
    return next((x for x in pool.get("records", []) if x.get("memory_id") == memory_id), None)


def _event(raw: dict[str, Any], *, default_actor: str) -> dict[str, Any] | None:
    action = str(raw.get("action", "")).strip().lower()
    memory_id = str(raw.get("memory_id", "")).strip()
    if action not in ALLOWED_ACTIONS or not memory_id:
        return None
    return {
        "memory_id": memory_id,
        "event_id": str(raw.get("event_id") or f"{memory_id}:{action}:{utc_now()}"),
        "at": str(raw.get("at") or utc_now()),
        "actor": str(raw.get("actor") or default_actor)[:100],
        "action": action,
        "base_version": raw.get("base_version"),
        "claim": str(raw.get("claim", ""))[:1000],
        "patch": raw.get("patch") if isinstance(raw.get("patch"), dict) else {},
        "evidence": [str(x)[:1000] for x in raw.get("evidence", [])[:10]]
        if isinstance(raw.get("evidence"), list) else [],
        "passed": raw.get("passed") if isinstance(raw.get("passed"), bool) else None,
        "blocker": str(raw.get("blocker"))[:1000] if raw.get("blocker") else None,
    }


def apply_event(pool: dict[str, Any], raw: dict[str, Any], *, default_actor: str) -> bool:
    """Apply a typed contribution; reject stale revisions and unknown records."""
    event = _event(raw, default_actor=default_actor)
    if not event:
        return False
    record = _record(pool, event["memory_id"])
    if record is None:
        return False
    action = event["action"]
    current = int(record.get("version", 1))
    if action == "challenge":
        challenge = {
            "challenge_id": event["event_id"], "actor": event["actor"],
            "claim": event["claim"], "against_version": current, "status": "open",
        }
        record.setdefault("open_challenges", []).append(challenge)
        record["status"] = "challenged"
        event["version"] = current
    elif action == "revision":
        if event["base_version"] != current:
            return False
        resolved = record.setdefault("resolved", {})
        for key, value in event["patch"].items():
            if key in resolved and key != "interface_id":
                resolved[key] = deepcopy(value)
        record["version"] = current + 1
        event["version"] = record["version"]
        for challenge in record.get("open_challenges", []):
            if challenge.get("status") == "open":
                challenge["status"] = "addressed"
                challenge["resolved_by_version"] = record["version"]
        record["status"] = "revised"
        record["verification"] = {"state": "pending", "evidence": [], "blocker": None}
    elif action == "accept":
        if event["base_version"] not in (None, current):
            return False
        event["version"] = current
        record["status"] = "agreed"
    elif action == "verification":
        event["version"] = current
        passed = event["passed"] is True
        record["verification"] = {
            "state": "verified" if passed else "failed",
            "evidence": event["evidence"],
            "blocker": event["blocker"],
        }
        record["status"] = "verified" if passed else "challenged"
        if not passed and event["blocker"]:
            record.setdefault("open_challenges", []).append({
                "challenge_id": event["event_id"], "actor": event["actor"],
                "claim": event["blocker"], "against_version": current,
                "status": "open", "source": "verification",
            })
    else:  # proposal on an existing record is retained as history, not a replacement
        event["version"] = current
    history = record.setdefault("history", [])
    history.append(event)
    del history[:-MAX_HISTORY]
    return True


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def ingest_contributions(path: Path, pool: dict[str, Any], *, actor: str,
                         event_log: Path | None = None) -> dict[str, int]:
    """Ingest an Agent-authored contribution envelope; malformed input fails open."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"submitted": 0, "applied": 0, "rejected": 0}
    items = raw.get("contributions", []) if isinstance(raw, dict) else []
    if not isinstance(items, list):
        return {"submitted": 0, "applied": 0, "rejected": 0}
    applied = rejected = 0
    for item in items[:MAX_CONTRIBUTIONS_PER_TURN]:
        if not isinstance(item, dict):
            rejected += 1
            continue
        event = {**item, "actor": actor}
        ok = apply_event(pool, event, default_actor=actor)
        applied += int(ok)
        rejected += int(not ok)
        if ok and event_log:
            append_event(event_log, {"at": utc_now(), "actor": actor, **item})
    try:
        path.unlink()
    except OSError:
        pass
    return {"submitted": min(len(items), MAX_CONTRIBUTIONS_PER_TURN),
            "applied": applied, "rejected": rejected}


def ingest_audit(path: Path, pool: dict[str, Any], *, actor: str = "reviewer_agent",
                 event_log: Path | None = None) -> dict[str, int]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"submitted": 0, "applied": 0, "rejected": 0}
    contributions = []
    for item in raw.get("interfaces", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict) or not item.get("interface_id"):
            continue
        contributions.append({
            "memory_id": f"interface:{item['interface_id']}",
            "action": "verification", "passed": item.get("passed") is True,
            "evidence": item.get("evidence", []), "blocker": item.get("blocker"),
            "claim": "Boundary audit result",
        })
    temp = {"contributions": contributions}
    submitted = applied = rejected = 0
    for event in temp["contributions"]:
        submitted += 1
        ok = apply_event(pool, {**event, "actor": actor}, default_actor=actor)
        applied += int(ok)
        rejected += int(not ok)
        if ok and event_log:
            append_event(event_log, {"at": utc_now(), "actor": actor, **event})
    return {"submitted": submitted, "applied": applied, "rejected": rejected}


def targeted_view(pool: dict[str, Any], *, actor: str, limit: int = 3) -> str:
    """Render current contracts and relevant open issues, never full history."""
    records = sorted(pool.get("records", []),
                     key=lambda x: (-int(x.get("resolved", {}).get("risk", 3)), x.get("memory_id", "")))
    if not records:
        return ""
    lines = ["SHARED COORDINATION MEMORY — RESOLVED CONTRACTS AND OPEN CHALLENGES",
             f"Target Agent: {actor}. Use the resolved version; do not replay superseded history."]
    for record in records[:limit]:
        contract = record.get("resolved", {})
        lines += [
            f"\n[{record['memory_id']}] version={record.get('version')} status={record.get('status')}",
            f"{contract.get('producer')} -> {contract.get('consumer')}: {contract.get('purpose')}",
            "Producer must: " + "; ".join(contract.get("producer_obligations", [])),
            "Consumer must: " + "; ".join(contract.get("consumer_obligations", [])),
            "Invariants: " + "; ".join(contract.get("invariants", [])),
        ]
        open_items = [x for x in record.get("open_challenges", []) if x.get("status") == "open"]
        for challenge in open_items:
            lines.append(f"OPEN CHALLENGE from {challenge.get('actor')}: {challenge.get('claim')}")
        verification = record.get("verification", {})
        lines.append(f"Verification: {verification.get('state', 'pending')}"
                     + (f"; blocker={verification.get('blocker')}" if verification.get("blocker") else ""))
    return "\n".join(lines)


CONTRIBUTION_INSTRUCTION = """

SHARED COORDINATION MEMORY WRITEBACK
When the resolved contract is incompatible or incomplete, write coordination_contributions.json as valid JSON:
{"contributions": [{"memory_id": "interface:exact_id", "action": "challenge", "base_version": 1, "claim": "specific incompatibility", "patch": {}}]}.
If you revise a challenged contract, use action=revision, the exact current base_version, and a patch containing only changed contract fields. If you agree with a usable contract, use action=accept. Do not write chat summaries or private reasoning into this file.
"""
