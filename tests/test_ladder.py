"""能力阶梯测试: 分数 → 等级映射 + 目标锚定。"""

from __future__ import annotations

from code_agent.ladder import ladder_report, level_for, target_for


def test_level_boundaries():
    assert level_for(0.0) == "D"
    assert level_for(0.49) == "D"
    assert level_for(0.5) == "C"
    assert level_for(0.69) == "C"
    assert level_for(0.7) == "B"
    assert level_for(0.84) == "B"
    assert level_for(0.85) == "A"
    assert level_for(0.94) == "A"
    assert level_for(0.95) == "S"
    assert level_for(1.0) == "S"
    # 越界夹取
    assert level_for(-1) == "D"
    assert level_for(1.5) == "S"


def test_target_for():
    assert target_for("D") == 0.5
    assert target_for("C") == 0.7
    assert target_for("B") == 0.85
    assert target_for("A") == 0.95
    assert target_for("S") is None


def test_ladder_report_promotion():
    r = ladder_report(0.72, 0.96)  # B → S
    assert r["promoted"] is True and r["demoted"] is False
    assert r["before"]["level"] == "B"
    assert r["after"]["level"] == "S"


def test_ladder_report_demotion():
    r = ladder_report(0.90, 0.60)  # A → C
    assert r["promoted"] is False and r["demoted"] is True
