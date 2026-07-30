#!/usr/bin/env python3
"""Compact shared interface memory for cross-domain coding work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MAX_INTERFACES = 5
MAX_FIELDS = 8
MAX_ITEMS = 6

INTERFACE_PATTERNS = (
    {"id": "browser_backend", "keywords": ("web", "frontend", "browser", "mobile application", "interface"),
     "rule": "Provide an executable request/response or event path plus a rendered client artifact; backend objects alone are insufficient.",
     "test": "Drive the public client boundary and observe backend state and client-visible output."},
    {"id": "realtime_event", "keywords": ("real-time", "realtime", "live update", "notification when", "dynamically"),
     "rule": "A producer state change must automatically reach subscribed consumers through an event/push mechanism; a manual polling call is insufficient.",
     "test": "Subscribe two parties, mutate producer state, and assert the non-acting party receives exactly one event."},
    {"id": "external_data", "keywords": ("external", "online retailer", "price update", "scrap", "email", "upload"),
     "rule": "Implement a real adapter seam whose production path does not always return None; deterministic tests may inject a fake at the same seam.",
     "test": "Exercise the adapter contract with a deterministic local server/fake and verify parsed data reaches the consumer."},
    {"id": "interactive_media", "keywords": ("3d", "audio guide", "hotspot", "visual representation", "gantt"),
     "rule": "Provide a consumable media/rendering artifact and interaction handler; storing URLs or labels alone is insufficient.",
     "test": "Load/render the artifact, trigger one interaction, and assert the associated information or media response."},
    {"id": "ml_application", "keywords": ("machine learning", "nlp", "natural language", "analyze user patterns", "adaptive"),
     "rule": "Connect observed application data to a reproducible model/algorithm output that changes application behavior; a disconnected heuristic label is insufficient.",
     "test": "Change training/feedback input, run the model path, and assert a justified downstream behavioral change."},
    {"id": "authorization", "keywords": ("authorization", "unauthorized", "login", "other users", "secure"),
     "rule": "Pass authenticated identity into every protected consumer and enforce object-level permissions, including negative cross-user cases.",
     "test": "Have one user attempt to read and mutate another user's private object and require rejection."},
    {"id": "multi_party_state", "keywords": ("team member", "team schedule", "availability", "collaborative", "all users", "group member"),
     "rule": "Propagate state and side effects to every affected participant, not only the owner or initiating user.",
     "test": "Create a multi-party object, mutate it, then verify constraints/state for a non-owner participant."},
)


def retrieve_patterns(task_text: str, limit: int = 3) -> list[dict[str, Any]]:
    text = task_text.lower()
    scored = []
    for pattern in INTERFACE_PATTERNS:
        hits = sum(1 for keyword in pattern["keywords"] if keyword in text)
        if hits:
            scored.append((hits, pattern["id"], pattern))
    return [item for _, _, item in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]


def render_patterns(patterns: list[dict[str, Any]]) -> str:
    if not patterns:
        return ""
    lines = ["PUBLIC CROSS-DOMAIN PATTERN MEMORY (retrieved from task wording)"]
    for pattern in patterns:
        lines += [f"[{pattern['id']}] Rule: {pattern['rule']}", f"Verification: {pattern['test']}"]
    return "\n".join(lines)


def empty_bank(task_id: int, run_id: str) -> dict[str, Any]:
    return {"schema_version": "0.1", "task_id": task_id, "run_id": run_id,
            "memory_type": "shared_interface", "interfaces": []}


def normalize_bank(raw: Any, task_id: int, run_id: str) -> dict[str, Any]:
    """Validate and bound planner-produced memory; invalid memory fails open."""
    bank = empty_bank(task_id, run_id)
    if not isinstance(raw, dict) or not isinstance(raw.get("interfaces"), list):
        return bank
    seen: set[str] = set()
    for index, item in enumerate(raw["interfaces"][:MAX_INTERFACES], 1):
        if not isinstance(item, dict):
            continue
        producer = str(item.get("producer", "")).strip()[:80]
        consumer = str(item.get("consumer", "")).strip()[:80]
        purpose = str(item.get("purpose", "")).strip()[:240]
        if not producer or not consumer or not purpose:
            continue
        interface_id = str(item.get("interface_id") or f"interface_{index}").strip()[:100]
        if interface_id in seen:
            interface_id = f"{interface_id}_{index}"
        seen.add(interface_id)
        fields = []
        for field in item.get("fields", [])[:MAX_FIELDS]:
            if isinstance(field, dict) and field.get("name"):
                fields.append({"name": str(field["name"])[:80],
                               "type": str(field.get("type", "unspecified"))[:80],
                               "meaning": str(field.get("meaning", ""))[:180]})
        def strings(name: str) -> list[str]:
            value = item.get(name, [])
            return [str(x)[:240] for x in value[:MAX_ITEMS] if str(x).strip()] if isinstance(value, list) else []
        test = item.get("boundary_test", {}) if isinstance(item.get("boundary_test"), dict) else {}
        bank["interfaces"].append({
            "interface_id": interface_id, "producer": producer, "consumer": consumer,
            "purpose": purpose, "task_evidence": str(item.get("task_evidence", ""))[:320],
            "risk": max(1, min(5, int(item.get("risk", 3)))) if str(item.get("risk", 3)).isdigit() else 3,
            "fields": fields,
            "producer_obligations": strings("producer_obligations"),
            "consumer_obligations": strings("consumer_obligations"),
            "invariants": strings("invariants"),
            "boundary_test": {"setup": str(test.get("setup", ""))[:300],
                              "action": str(test.get("action", ""))[:300],
                              "expected": str(test.get("expected", ""))[:300]},
            "runtime": {"state": "agreed", "evidence": [], "blocker": None},
        })
    bank["interfaces"].sort(key=lambda x: (-x["risk"], x["interface_id"]))
    return bank


def load_or_empty(path: Path, task_id: int, run_id: str) -> dict[str, Any]:
    try:
        return normalize_bank(json.loads(path.read_text(encoding="utf-8")), task_id, run_id)
    except Exception:
        return empty_bank(task_id, run_id)


def save_bank(path: Path, bank: dict[str, Any]) -> None:
    path.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compact_view(bank: dict[str, Any], role: str, limit: int | None = None) -> str:
    """Render a bounded shared contract view for an implementation/review turn."""
    interfaces = bank.get("interfaces", [])
    if limit is not None:
        interfaces = interfaces[:limit]
    if not interfaces:
        return ""
    lines = ["SHARED INTERFACE MEMORY — AGREED CROSS-DOMAIN CONTRACTS",
             "Treat these as acceptance criteria. Do not replace real crossings with disconnected simulations."]
    for item in interfaces:
        lines += [f"\n[{item['interface_id']}] {item['producer']} -> {item['consumer']}",
                  f"Required by task: {item['task_evidence']}", f"Purpose: {item['purpose']}"]
        if item["fields"]:
            lines.append("Shared data: " + "; ".join(
                f"{x['name']}:{x['type']} ({x['meaning']})" for x in item["fields"]))
        lines.append("Producer must: " + "; ".join(item["producer_obligations"]))
        lines.append("Consumer must: " + "; ".join(item["consumer_obligations"]))
        lines.append("Shared invariants: " + "; ".join(item["invariants"]))
        test = item["boundary_test"]
        lines.append(f"Boundary test: setup={test['setup']}; action={test['action']}; expected={test['expected']}")
    if role == "reviewer":
        lines.append("\nFor every record, exercise the real producer-to-consumer path, repair mismatches, "
                     "and write exact pass/fail evidence to interface_audit.json.")
    else:
        lines.append("\nImplement both sides against these exact semantics and include executable boundary tests.")
    return "\n".join(lines)


def coverage_summary(bank: dict[str, Any]) -> str:
    """Provide cheap global awareness while detailed injection remains sparse."""
    items = bank.get("interfaces", [])
    if not items:
        return ""
    lines = ["CROSS-DOMAIN COVERAGE INVENTORY (all required; detailed contracts follow for highest risks)"]
    for item in items:
        lines.append(f"- [{item['interface_id']}] {item['producer']} -> {item['consumer']}: "
                     f"{item['task_evidence']} (risk {item['risk']})")
    lines.append("A class name or in-memory placeholder is not integration evidence. Required web, external-data, "
                 "real-time, media, ML, NLP, security, and multi-party state crossings need executable behavior.")
    return "\n".join(lines)


def summarize_audit(path: Path, bank: dict[str, Any]) -> dict[str, Any]:
    """Attach reviewer evidence without trusting it as the sole task score."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    results = raw.get("interfaces", []) if isinstance(raw, dict) else []
    by_id = {str(x.get("interface_id")): x for x in results if isinstance(x, dict)}
    passed = failed = 0
    for item in bank.get("interfaces", []):
        result = by_id.get(item["interface_id"], {})
        state = "verified" if result.get("passed") is True else "failed"
        passed += state == "verified"
        failed += state == "failed"
        item["runtime"] = {"state": state,
                           "evidence": [str(x)[:500] for x in result.get("evidence", [])[:5]]
                           if isinstance(result.get("evidence"), list) else [],
                           "blocker": str(result.get("blocker"))[:500] if result.get("blocker") else None}
    return {"records": len(bank.get("interfaces", [])), "verified": passed, "failed": failed}
