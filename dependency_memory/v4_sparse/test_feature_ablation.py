from run_feature_ablation import FEATURES


def test_feature_matrix_is_complete_and_orthogonal():
    assert FEATURES == {
        "baseline": {"dependency": False, "codomain": False},
        "dependency": {"dependency": True, "codomain": False},
        "codomain": {"dependency": False, "codomain": True},
        "both": {"dependency": True, "codomain": True},
    }
    assert len({tuple(flags.values()) for flags in FEATURES.values()}) == 4
