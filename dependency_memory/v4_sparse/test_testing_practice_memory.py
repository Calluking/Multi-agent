import json

from testing_practice_memory import load_bank, make_episode, render_packet, retrieve


def test_bank_is_valid_and_ids_are_unique():
    bank = load_bank()
    ids = [item["practice_id"] for item in bank["practices"]]
    assert len(ids) == len(set(ids))
    assert all(item["rule"] and item["required_evidence"] for item in bank["practices"])


def test_ml_task_retrieves_semantic_substitution_practice():
    selected = retrieve("Use machine learning on historical performance to adapt strategy", "reviewer")
    assert selected[0]["practice_id"] == "reject_semantic_substitute"


def test_packet_is_role_specific_and_explicitly_inject_only():
    packet, ids = render_packet("A real-time multi-user application with tests", "implementer")
    assert ids
    assert "independent_requirement_audit" not in ids
    assert "Target role: implementer" in packet
    assert "does not add turns, retries, gates, or rerouting" in packet


def test_reviewer_only_practice_never_leaks_to_other_roles():
    for role in ("planner", "implementer"):
        selected = retrieve("Review every requirement and collaboration feature", role, limit=4)
        assert "independent_requirement_audit" not in {item["practice_id"] for item in selected}


def test_episode_has_no_control_effect():
    episode = make_episode(task_id=11, run_id="r1", condition="testing",
                           selected_by_role={"reviewer": ["reject_semantic_substitute"]},
                           result={"workflow_complete": True, "objective": {},
                                   "task_scores": {"mean": 4.0}, "required_artifacts": {}})
    assert episode["control_effect"] == "none"
    assert "next_action" not in json.dumps(episode)
