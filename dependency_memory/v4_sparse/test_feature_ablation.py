from run_feature_ablation import FEATURES


def test_feature_matrix_is_complete_and_orthogonal():
    assert FEATURES == {
        "baseline": {"dependency": False, "codomain": False, "testing": False},
        "dependency": {"dependency": True, "codomain": False, "testing": False},
        "codomain": {"dependency": False, "codomain": True, "testing": False},
        "both": {"dependency": True, "codomain": True, "testing": False},
        "testing": {"dependency": False, "codomain": False, "testing": True},
        "dependency_testing": {"dependency": True, "codomain": False, "testing": True},
        "codomain_testing": {"dependency": False, "codomain": True, "testing": True},
        "all_three": {"dependency": True, "codomain": True, "testing": True},
    }
    assert len({tuple(flags.values()) for flags in FEATURES.values()}) == 8


def test_testing_toggle_does_not_enable_recovery_mechanisms():
    assert FEATURES["testing"] == {"dependency": False, "codomain": False, "testing": True}
