import json

from interface_memory import compact_view, load_or_empty, normalize_bank, summarize_audit


def sample():
    return {"interfaces": [{"interface_id": "team_calendar", "producer": "team",
        "consumer": "calendar", "purpose": "reserve all members",
        "fields": [{"name": "member_ids", "type": "list[str]", "meaning": "all participants"}],
        "producer_obligations": ["send all members"],
        "consumer_obligations": ["reserve all calendars"],
        "invariants": ["no participant is double-booked"],
        "boundary_test": {"setup": "book Alice and Bob", "action": "overlap Bob",
                          "expected": "reject"}}]}


def test_normalize_and_render():
    bank = normalize_bank(sample(), 3, "run")
    assert bank["interfaces"][0]["runtime"]["state"] == "agreed"
    view = compact_view(bank, "implementer")
    assert "team -> calendar" in view
    assert "reserve all calendars" in view


def test_invalid_memory_fails_open(tmp_path):
    path = tmp_path / "interface_memory.json"
    path.write_text("not json")
    assert load_or_empty(path, 1, "r")["interfaces"] == []


def test_audit_updates_state(tmp_path):
    bank = normalize_bank(sample(), 3, "run")
    audit = tmp_path / "interface_audit.json"
    audit.write_text(json.dumps({"interfaces": [{"interface_id": "team_calendar",
        "passed": False, "evidence": ["Bob was not reserved"], "blocker": "owner-only update"}]}))
    summary = summarize_audit(audit, bank)
    assert summary == {"records": 1, "verified": 0, "failed": 1}
    assert bank["interfaces"][0]["runtime"]["blocker"] == "owner-only update"
