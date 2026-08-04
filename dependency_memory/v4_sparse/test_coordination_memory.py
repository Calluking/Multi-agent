import json

from coordination_memory import (apply_event, ingest_audit, ingest_contributions,
                                  initialize_pool, load_pool, save_pool, targeted_view)
from interface_memory import normalize_bank


def bank():
    raw = {"interfaces": [{"interface_id": "a_to_b", "producer": "Agent A",
        "consumer": "Agent B", "purpose": "share a typed result", "task_evidence": "A feeds B",
        "risk": 5, "fields": [{"name": "value", "type": "int", "meaning": "score"}],
        "producer_obligations": ["emit value"], "consumer_obligations": ["validate value"],
        "invariants": ["value is non-negative"],
        "boundary_test": {"setup": "A has 1", "action": "B reads", "expected": "B sees 1"}}]}
    return normalize_bank(raw, 1, "run")


def test_proposal_challenge_revision_accept_and_verify(tmp_path):
    pool = initialize_pool(bank(), 1, "run")
    record = pool["records"][0]
    assert record["version"] == 1 and record["status"] == "proposed"
    assert apply_event(pool, {"memory_id": "interface:a_to_b", "action": "challenge",
        "claim": "consumer also needs a label"}, default_actor="agent_b")
    assert record["status"] == "challenged"
    assert apply_event(pool, {"memory_id": "interface:a_to_b", "action": "revision",
        "base_version": 1, "patch": {"fields": [{"name": "value", "type": "int"},
        {"name": "label", "type": "str"}]}}, default_actor="agent_a")
    assert record["version"] == 2 and record["status"] == "revised"
    assert apply_event(pool, {"memory_id": "interface:a_to_b", "action": "accept",
        "base_version": 2}, default_actor="agent_b")
    assert record["status"] == "agreed"
    audit = tmp_path / "interface_audit.json"
    audit.write_text(json.dumps({"interfaces": [{"interface_id": "a_to_b", "passed": True,
        "evidence": ["real crossing passed"], "blocker": None}]}))
    assert ingest_audit(audit, pool)["applied"] == 1
    assert record["status"] == "verified"
    assert record["verification"]["evidence"] == ["real crossing passed"]


def test_stale_revision_is_rejected():
    pool = initialize_pool(bank(), 1, "run")
    assert not apply_event(pool, {"memory_id": "interface:a_to_b", "action": "revision",
        "base_version": 0, "patch": {"purpose": "stale"}}, default_actor="agent_a")
    assert pool["records"][0]["version"] == 1


def test_agent_contribution_file_and_targeted_projection(tmp_path):
    pool = initialize_pool(bank(), 1, "run")
    contribution = tmp_path / "coordination_contributions.json"
    contribution.write_text(json.dumps({"contributions": [{"memory_id": "interface:a_to_b",
        "action": "challenge", "claim": "type mismatch"}]}))
    result = ingest_contributions(contribution, pool, actor="implementer_agent")
    assert result == {"submitted": 1, "applied": 1, "rejected": 0}
    view = targeted_view(pool, actor="reviewer_agent")
    assert "type mismatch" in view and "superseded history" in view
    path = tmp_path / "coordination_memory.json"
    save_pool(path, pool)
    assert load_pool(path, 1, "run")["records"][0]["status"] == "challenged"


def test_agent_event_alias_is_normalized(tmp_path):
    pool = initialize_pool(bank(), 1, "run")
    contribution = tmp_path / "coordination_contributions.json"
    contribution.write_text(json.dumps({"events": [{"memory_id": "interface:a_to_b",
        "event": "accept", "base_version": 1}]}))
    result = ingest_contributions(contribution, pool, actor="consumer_agent")
    assert result == {"submitted": 1, "applied": 1, "rejected": 0}
    assert pool["records"][0]["status"] == "agreed"


def test_audit_accepts_pool_prefixed_memory_id(tmp_path):
    pool = initialize_pool(bank(), 1, "run")
    audit = tmp_path / "interface_audit.json"
    audit.write_text(json.dumps({"interfaces": [{"interface_id": "interface:a_to_b",
        "passed": True, "evidence": ["passed"], "blocker": None}]}))
    assert ingest_audit(audit, pool) == {"submitted": 1, "applied": 1, "rejected": 0}
    assert pool["records"][0]["verification"]["state"] == "verified"


def test_explicit_boundary_is_visible_only_to_participants():
    raw = {"interfaces": [{"interface_id": "producer_to_consumer",
        "producer": "producer", "consumer": "consumer", "artifact": "solution.py",
        "producer_agent": "agent-data-7", "consumer_agents": ["agent-model-3"],
        "purpose": "share one artifact contract", "risk": 5,
        "fields": [{"name": "result", "type": "object", "meaning": "public output"}],
        "producer_obligations": ["produce result"],
        "consumer_obligations": ["validate result"],
        "invariants": ["result uses the agreed schema"],
        "boundary_test": {"setup": "artifact exists", "action": "consumer reads it",
                          "expected": "schema is accepted"}}]}
    explicit_bank = normalize_bank(raw, 1, "run")
    pool = initialize_pool(explicit_bank, 1, "run", actor="agent-data-7")
    assert "producer_to_consumer" in targeted_view(pool, actor="agent-data-7")
    assert "producer_to_consumer" in targeted_view(pool, actor="agent-model-3")
    assert "producer_to_consumer" not in targeted_view(pool, actor="unrelated_agent")


def test_consumer_can_atomically_revise_and_accept():
    pool = initialize_pool(bank(), 1, "run")
    assert apply_event(pool, {"memory_id": "interface:a_to_b", "action": "accept_revision",
        "base_version": 1, "claim": "accepted with explicit consumer requirement",
        "patch": {"consumer_obligations": ["validate label and value"]}},
        default_actor="agent_b")
    record = pool["records"][0]
    assert record["version"] == 2
    assert record["status"] == "agreed"
    assert record["resolved"]["consumer_obligations"] == ["validate label and value"]
