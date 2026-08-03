from run_feature_ablation import FEATURES


def test_feature_matrix_is_complete_and_orthogonal():
    assert FEATURES == {
        "baseline": {"dependency": False, "codomain": False, "testing": False, "prework": False},
        "dependency": {"dependency": True, "codomain": False, "testing": False, "prework": False},
        "codomain": {"dependency": False, "codomain": True, "testing": False, "prework": False},
        "both": {"dependency": True, "codomain": True, "testing": False, "prework": False},
        "testing": {"dependency": False, "codomain": False, "testing": True, "prework": False},
        "dependency_testing": {"dependency": True, "codomain": False, "testing": True, "prework": False},
        "codomain_testing": {"dependency": False, "codomain": True, "testing": True, "prework": False},
        "all_three": {"dependency": True, "codomain": True, "testing": True, "prework": False},
        "codomain_prework": {"dependency": False, "codomain": True, "testing": False, "prework": True},
    }
    assert len({tuple(flags.values()) for flags in FEATURES.values()}) == 9


def test_testing_toggle_does_not_enable_recovery_mechanisms():
    assert FEATURES["testing"] == {
        "dependency": False, "codomain": False, "testing": True, "prework": False,
    }


def test_prework_is_codomain_only_and_disables_posthoc_mode():
    assert FEATURES["codomain_prework"] == {
        "dependency": False, "codomain": True, "testing": False, "prework": True,
    }
