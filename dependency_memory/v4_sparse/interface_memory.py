#!/usr/bin/env python3
"""Compact shared interface memory for cross-domain coding work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MAX_INTERFACES = 3
MAX_FIELDS = 8
MAX_ITEMS = 6


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
            "purpose": purpose, "fields": fields,
            "producer_obligations": strings("producer_obligations"),
            "consumer_obligations": strings("consumer_obligations"),
            "invariants": strings("invariants"),
            "boundary_test": {"setup": str(test.get("setup", ""))[:300],
                              "action": str(test.get("action", ""))[:300],
                              "expected": str(test.get("expected", ""))[:300]},
            "runtime": {"state": "agreed", "evidence": [], "blocker": None},
        })
    return bank


def load_or_empty(path: Path, task_id: int, run_id: str) -> dict[str, Any]:
    try:
        return normalize_bank(json.loads(path.read_text(encoding="utf-8")), task_id, run_id)
    except Exception:
        return empty_bank(task_id, run_id)


def save_bank(path: Path, bank: dict[str, Any]) -> None:
    path.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compact_view(bank: dict[str, Any], role: str) -> str:
    """Render a bounded shared contract view for an implementation/review turn."""
    interfaces = bank.get("interfaces", [])
    if not interfaces:
        return ""
    lines = ["SHARED INTERFACE MEMORY — AGREED CROSS-DOMAIN CONTRACTS",
             "Treat these as acceptance criteria. Do not replace real crossings with disconnected simulations."]
    for item in interfaces:
        lines += [f"\n[{item['interface_id']}] {item['producer']} -> {item['consumer']}",
                  f"Purpose: {item['purpose']}"]
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
