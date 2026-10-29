"""Машина логического вывода: правила и коэффициенты уверенности (по аналогии с MYCIN)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .context import PlantContext
from .knowledge_base import Knowledge, Rule, split_token


@dataclass
class Hypothesis:
    cause: str
    cf: float
    fired: list[Rule] = field(default_factory=list)


def combine_same_sign(values: list[float]) -> float:
    """CF = CF1 + CF2 * (1 - CF1) для нескольких подтверждающих правил (значения от 0 до 1)."""
    total = 0.0
    for v in values:
        total = total + v * (1 - total)
    return total


def combine(cfs: list[float]) -> float:
    """Объединение свидетельств за и против: (CFпро - CFпротив) / (1 - min(CFпро, CFпротив))."""
    pos = combine_same_sign([c for c in cfs if c > 0])
    neg = combine_same_sign([-c for c in cfs if c < 0])
    if neg == 0:
        return pos
    if pos == 0:
        return -neg
    return (pos - neg) / (1 - min(pos, neg))


def present_closure(kb: Knowledge, present: set[str]) -> set[str]:
    """Добавляет следствия: «нижние листья желтеют» означает и «листья желтеют»."""
    result = set(present)
    stack = list(present)
    while stack:
        sid = stack.pop()
        sym = kb.symptoms.get(sid)
        for target in (sym.implies if sym else ()):
            if target not in result:
                result.add(target)
                stack.append(target)
    return result


def absent_closure(kb: Knowledge, absent: set[str]) -> set[str]:
    """Если «листья не желтеют», то и «нижние листья не желтеют»."""
    result = set(absent)
    changed = True
    while changed:
        changed = False
        for sym in kb.symptoms.values():
            if sym.id not in result and any(t in result for t in sym.implies):
                result.add(sym.id)
                changed = True
    return result


def holds(token: str, ctx: PlantContext, present: set[str], absent: set[str]) -> bool:
    negated, is_ctx, name = split_token(token)
    if is_ctx:
        value = ctx.facts.get(name)
        return (value is False) if negated else (value is True)
    return (name in absent) if negated else (name in present)


def diagnose(kb: Knowledge, ctx: PlantContext, present: set[str], absent: set[str]) -> list[Hypothesis]:
    """Список гипотез с уверенностью больше нуля, от самой вероятной."""
    present_all = present_closure(kb, present)
    absent_all = absent_closure(kb, absent)

    fired: dict[str, list[Rule]] = {}
    for rule in kb.rules:
        if all(holds(t, ctx, present_all, absent_all) for t in rule.all):
            fired.setdefault(rule.cause, []).append(rule)

    hypotheses = []
    for cause, rules in fired.items():
        cf = combine([r.cf for r in rules])
        if cf > 0:
            hypotheses.append(Hypothesis(cause=cause, cf=round(cf, 4), fired=rules))
    hypotheses.sort(key=lambda h: (-h.cf, h.cause))
    return hypotheses
