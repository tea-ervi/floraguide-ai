"""Диалог: что делать дальше. Выдать диагноз, задать уточняющий вопрос или попросить описать проблему."""
from __future__ import annotations

from dataclasses import dataclass, field

from .context import PlantContext
from .engine import Hypothesis, absent_closure, diagnose, holds, present_closure
from .knowledge_base import Knowledge, split_token


@dataclass
class Decision:
    kind: str                                  # need_info / question / diagnosis / uncertain
    hypotheses: list[Hypothesis] = field(default_factory=list)
    question: str | None = None                # id симптома, о котором спрашиваем
    confident: bool = False


def pick_question(
    kb: Knowledge,
    ctx: PlantContext,
    present: set[str],
    absent: set[str],
    asked: set[str],
    hypotheses: list[Hypothesis],
) -> str | None:
    """Выбирает вопрос, ответ на который сильнее всего разводит ведущие гипотезы.

    Для каждого неизвестного симптома суммируется вес правил ведущих гипотез, которые могли бы
    сработать после ответа. Чем больше вес у одной гипотезы и чем меньше у других, тем лучше вопрос.
    Вопросы про симптомы, способные ослабить лидера, тоже получают баллы.
    """
    present_all = present_closure(kb, present)
    absent_all = absent_closure(kb, absent)
    resolved = present_all | absent_all
    top = [h for h in hypotheses if h.cf > 0][:3]
    if top:
        top_causes = {h.cause for h in top}
        leader = top[0].cause
    else:
        # Ни одно правило ещё не сработало (симптом один, нужны подробности): ищем вопрос по всем причинам
        top_causes = set(kb.causes)
        leader = None

    weights: dict[str, dict[str, float]] = {}
    for rule in kb.rules:
        if rule.cause not in top_causes:
            continue
        if rule.cf < 0 and rule.cause != leader:
            continue
        unknown: list[str] = []
        viable = True
        for token in rule.all:
            negated, is_ctx, name = split_token(token)
            if holds(token, ctx, present_all, absent_all):
                continue
            if is_ctx:
                viable = False
                break
            contradicted = (name in present_all) if negated else (name in absent_all)
            if contradicted or (name in asked and name not in resolved):
                viable = False
                break
            unknown.append(name)
        if not viable or not unknown:
            continue
        share = abs(rule.cf) / len(unknown)
        key = rule.cause if rule.cf > 0 else "_against"
        for name in set(unknown):
            bucket = weights.setdefault(name, {})
            bucket[key] = bucket.get(key, 0.0) + (share if rule.cf > 0 else 0.5 * share)

    best_id, best_score = None, 0.1
    for sid in kb.symptoms:                      # порядок из symptoms.yaml: при равенстве выигрывает первый
        values = sorted(weights.get(sid, {}).values(), reverse=True)
        if not values:
            continue
        score = values[0] - 0.5 * (values[1] if len(values) > 1 else 0.0)
        if score > best_score:
            best_id, best_score = sid, score
    return best_id


def decide(kb: Knowledge, ctx: PlantContext, state: dict) -> Decision:
    cfg = kb.settings["dialog"]
    present = set(state["present"])
    absent = set(state["absent"])
    asked = set(state["asked"])

    hypotheses = diagnose(kb, ctx, present, absent)
    if not any(kb.symptoms[s].kind == "symptom" for s in present if s in kb.symptoms):
        return Decision("need_info", hypotheses)

    top = hypotheses[0] if hypotheses else None
    second = hypotheses[1].cf if len(hypotheses) > 1 else 0.0
    if top and top.cf >= cfg["confirm_cf"] and top.cf - second >= cfg["min_lead"]:
        return Decision("diagnosis", hypotheses, confident=True)

    if state.get("round_questions", 0) < cfg["max_questions"]:
        question = pick_question(kb, ctx, present, absent, asked, hypotheses)
        if question:
            return Decision("question", hypotheses, question=question)

    if top and top.cf >= cfg["min_report_cf"]:
        return Decision("diagnosis", hypotheses, confident=False)
    return Decision("uncertain", hypotheses)
