"""能力阶梯 — benchmark 分数 → 等级映射 + 目标锚定。

锚定语义 (北极星: 超越人类代码工程师):
    S (0.95+)  超越级 — 超出典型人类工程师基准分
    A (0.85+)  专家级 — 资深工程师水平
    B (0.70+)  熟练级 — 独立交付能力
    C (0.50+)  入门级 — 能通过测试但工程素养不足
    D (<0.50)  新手级
"""

from __future__ import annotations

LEVELS: list[tuple[str, float]] = [
    ("S", 0.95),
    ("A", 0.85),
    ("B", 0.70),
    ("C", 0.50),
    ("D", 0.0),
]


def level_for(score: float) -> str:
    """分数 → 等级。分数夹取到 [0,1]."""
    score = max(0.0, min(1.0, score))
    for level, threshold in LEVELS:
        if score >= threshold:
            return level
    return "D"


def target_for(level: str) -> float | None:
    """给定等级, 返回升到下一级所需的最低分数; S 级无上级 → None."""
    idx = [l for l, _ in LEVELS].index(level)
    if idx == 0:
        return None
    return LEVELS[idx - 1][1]


def ladder_report(before: float, after: float) -> dict:
    b, a = level_for(before), level_for(after)
    names = [l for l, _ in LEVELS]
    return {
        "before": {"score": round(before, 4), "level": b,
                   "next_target": target_for(b)},
        "after": {"score": round(after, 4), "level": a,
                  "next_target": target_for(a)},
        "promoted": names.index(a) < names.index(b),  # 索引小 = 等级高
        "demoted": names.index(a) > names.index(b),
    }
