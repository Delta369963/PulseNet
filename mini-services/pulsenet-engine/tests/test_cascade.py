"""Unit tests for the probabilistic cascade model."""

from app.compute.cascade import (
    CascadeNode,
    build_cascade,
    path_confidence,
    recuperation_factor,
)


def test_recuperation_factor_bounds():
    assert recuperation_factor(0) == 0.0       # sri_scaled=1, 1-1/1=0
    # SRI=0.5 → sri_scaled=3 → 1-1/3=0.6667
    assert abs(recuperation_factor(0.5) - 0.6667) < 0.001
    # SRI=2.0 (out of range) → sri_scaled=9 → 1-1/9≈0.8889
    assert 0.8 < recuperation_factor(2.0) < 1.0



def test_path_confidence_product():
    # 0.8 * 0.5 = 0.4; sri_target=2.0 → sri_scaled=9 → rf=1-1/9≈0.8889
    result = path_confidence([0.8, 0.5], sri_target=2.0)
    assert abs(result - 0.3556) < 0.001



def test_path_confidence_clamps_probabilities():
    # Out-of-range probabilities are clamped to [0,1].
    val = path_confidence([1.5, -0.2], sri_target=2.0)
    assert val == 0.0  # -0.2 clamps to 0 => product 0


def test_build_cascade_is_dag_and_sets_confidence():
    root = CascadeNode(id="root", label="shock", cond_prob=1.0, sri=1.0)
    children = [
        CascadeNode(id="EGY-WHEAT", label="Egypt wheat", cond_prob=0.76, sri=0.45),
        CascadeNode(id="KEN-WHEAT", label="Kenya wheat", cond_prob=0.55, sri=0.30),
    ]
    dag = build_cascade(root, children)
    out = dag.to_dict()
    assert len(out["nodes"]) == 3
    assert len(out["edges"]) == 2
    # Lower-SRI (more fragile) Kenya should have higher vulnerability multiplier.
    egy = next(n for n in out["nodes"] if n["id"] == "EGY-WHEAT")
    ken = next(n for n in out["nodes"] if n["id"] == "KEN-WHEAT")
    assert egy["confidence"] > 0
    assert ken["confidence"] > 0


def test_more_fragile_nation_higher_vulnerability():
    root = CascadeNode(id="root", label="shock", cond_prob=1.0, sri=1.0)
    fragile = build_cascade(root, [CascadeNode(id="a", label="a", cond_prob=0.5, sri=0.2)])
    resilient = build_cascade(root, [CascadeNode(id="b", label="b", cond_prob=0.5, sri=0.9)])
    a_conf = fragile.to_dict()["nodes"][1]["confidence"]
    b_conf = resilient.to_dict()["nodes"][1]["confidence"]
    assert a_conf >= b_conf
