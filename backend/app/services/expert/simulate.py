"""Прогон диалога без базы данных и интерфейса: для тестов, оценки качества и консольного чата."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .context import PlantContext
from .engine import Hypothesis, diagnose
from .knowledge_base import Knowledge
from .responder import Reply
from .service import handle_turn, new_state


@dataclass
class SimResult:
    final: Reply
    replies: list[Reply] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    ranking: list[Hypothesis] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


def simulate(
    kb: Knowledge,
    ctx: PlantContext,
    text: str,
    answers: dict[str, str] | None = None,
    max_turns: int = 8,
) -> SimResult:
    """Пользователь пишет text, на уточняющие вопросы отвечает по словарю answers (иначе «не знаю»)."""
    answers = answers or {}
    reply, state = handle_turn(kb, ctx, new_state(), text=text)
    replies, questions = [reply], []
    for _ in range(max_turns):
        if reply.kind != "question":
            break
        symptom = reply.question["symptom"]
        questions.append(symptom)
        value = answers.get(symptom, "unknown")
        reply, state = handle_turn(kb, ctx, state, answer={"symptom": symptom, "value": value})
        replies.append(reply)
    ranking = diagnose(kb, ctx, set(state["present"]), set(state["absent"]))
    return SimResult(final=reply, replies=replies, state=state, ranking=ranking, questions=questions)


# ---------------------------------------------------------------- тестовые случаи
from datetime import date, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

SEASON_DATES = {
    "winter": date(2026, 1, 15),
    "spring": date(2026, 4, 15),
    "summer": date(2026, 7, 15),
    "autumn": date(2026, 10, 15),
}


def context_from_case(kb: Knowledge, plant: dict) -> PlantContext:
    """Контекст из описания растения в тестовом случае (days_since_watering, season и т.д.)."""
    from .context import make_context

    today = SEASON_DATES[plant.get("season", "summer")]
    ds = plant.get("days_since_watering")
    return make_context(
        kb.settings,
        plant_name=plant.get("name", "Растение"),
        category_name=plant.get("category", "Комнатные растения"),
        interval_days=plant.get("interval"),
        min_days=plant.get("min_days"),
        max_days=plant.get("max_days"),
        optimal_lux=plant.get("lux"),
        optimal_humidity=plant.get("humidity"),
        sunlight=plant.get("sunlight"),
        last_watered=(today - timedelta(days=ds)) if ds is not None else None,
        planted_at=today - timedelta(days=plant.get("planted_days_ago", 200)),
        today=today,
    )


def load_cases(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]


def run_case(kb: Knowledge, case: dict) -> dict:
    """Прогоняет случай и сравнивает результат с ожидаемым диагнозом."""
    ctx = context_from_case(kb, case.get("plant", {}))
    result = simulate(kb, ctx, case["text"], case.get("answers"))
    causes = [h.cause for h in result.ranking]
    final_cause = result.final.diagnosis["cause"] if result.final.diagnosis else None
    expect = case.get("expect")
    expect_not = case.get("expect_not")
    top1 = bool(expect) and bool(causes) and causes[0] == expect
    top2 = bool(expect) and expect in causes[:2]
    if expect_not:
        ok = final_cause != expect_not and (not causes or causes[0] != expect_not)
    else:
        ok = top1
    return {
        "id": case["id"],
        "ok": ok,
        "top1": top1,
        "top2": top2,
        "expect": expect or f"не {expect_not}",
        "got": [(h.cause, round(h.cf, 2)) for h in result.ranking[:3]],
        "final_kind": result.final.kind,
        "questions": result.questions,
    }
