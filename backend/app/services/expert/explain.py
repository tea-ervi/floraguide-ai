"""Объяснение вывода: какие правила сработали и почему система так считает."""
from __future__ import annotations

from .context import PlantContext
from .engine import Hypothesis
from .knowledge_base import Rule


class _Values(dict):
    def __missing__(self, key: str) -> str:
        return "—"


def render_rule(rule: Rule, ctx: PlantContext) -> str:
    values = _Values({k: ("—" if v is None else v) for k, v in ctx.values.items()})
    try:
        return rule.explain.format_map(values)
    except (ValueError, IndexError):
        return rule.explain


def explain(hypothesis: Hypothesis, ctx: PlantContext, limit: int = 5) -> tuple[list[str], list[str]]:
    """Возвращает (аргументы за, аргументы против)."""
    pros = sorted((r for r in hypothesis.fired if r.cf > 0), key=lambda r: -r.cf)
    cons = sorted((r for r in hypothesis.fired if r.cf < 0), key=lambda r: r.cf)
    return (
        [render_rule(r, ctx) for r in pros[:limit]],
        [render_rule(r, ctx) for r in cons[:limit]],
    )
