"""Формирование ответов: текст для чата и структурированные данные для интерфейса."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .context import PlantContext
from .dialog import Decision
from .explain import explain
from .knowledge_base import Knowledge

URGENCY_TEXT = {
    "high": "Срочность: высокая, лучше заняться этим сегодня.",
    "medium": "Срочность: средняя, займитесь этим в ближайшие дни.",
    "low": "Срочность: низкая, паниковать не нужно.",
}
SUGGESTED_SYMPTOMS = [
    "yellow_leaves", "wilting", "dry_brown_tips", "brown_spots",
    "leaf_drop", "webbing", "tiny_flies", "sticky_leaves",
]
ANSWER_OPTIONS = [
    {"label": "Да", "value": "yes"},
    {"label": "Нет", "value": "no"},
    {"label": "Не знаю", "value": "unknown"},
]


@dataclass
class Reply:
    kind: str                         # question / diagnosis / uncertain / need_info / info
    text: str
    question: dict | None = None      # {"symptom", "text", "options"}
    diagnosis: dict | None = None
    suggestions: list[dict] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def question_reply(kb: Knowledge, symptom_id: str, prefix: str = "") -> Reply:
    sym = kb.symptoms[symptom_id]
    text = f"{prefix}{sym.question}".strip()
    return Reply(
        kind="question",
        text=text,
        question={"symptom": symptom_id, "text": sym.question, "options": ANSWER_OPTIONS},
    )


def need_info_reply(kb: Knowledge, prefix: str = "") -> Reply:
    suggestions = [
        {"label": kb.symptoms[s].name, "text": kb.symptoms[s].synonyms[0]}
        for s in SUGGESTED_SYMPTOMS if s in kb.symptoms
    ]
    text = (
        f"{prefix}Опишите, что вас беспокоит, например: «желтеют нижние листья», «растение поникло», "
        "«паутинка на листьях». Или выберите подходящий вариант."
    )
    return Reply(kind="need_info", text=text.strip(), suggestions=suggestions)


def info_reply(text: str) -> Reply:
    return Reply(kind="info", text=text)


def help_reply() -> Reply:
    return info_reply(
        "Я помогаю разобраться с проблемами этого растения. Опишите симптом своими словами, например "
        "«листья желтеют и земля мокрая», и я задам уточняющие вопросы, если не хватит данных. "
        "Также можно спросить, когда поливать."
    )


def schedule_reply(ctx: PlantContext) -> Reply:
    v = ctx.values
    lines = [f"Сезон: {v['season']}. Рекомендуемый интервал полива для «{v['plant']}»: раз в {v['interval']} дн."]
    if v["interval"] != v["base_interval"]:
        lines.append(f"Базовый интервал {v['base_interval']} дн. скорректирован с учётом сезона.")
    if v["recommended"] != "нет данных":
        lines.append(f"Для этого вида рекомендуют поливать раз в {v['recommended']}")
    nxt, until = v.get("next_date"), v.get("days_until")
    if nxt is not None and until is not None:
        when = (
            "сегодня" if until == 0
            else f"через {until} дн." if until > 0
            else f"просрочен на {-until} дн."
        )
        lines.append(f"Следующий полив: {nxt.strftime('%d.%m.%Y')} ({when}).")
    lines.append("Перед поливом проверьте землю: если верхний слой ещё влажный, подождите.")
    return info_reply("\n".join(lines))


def _percent(cf: float) -> int:
    return max(1, min(99, round(cf * 100)))


def diagnosis_reply(kb: Knowledge, ctx: PlantContext, decision: Decision) -> Reply:
    top = decision.hypotheses[0]
    cause = kb.causes[top.cause]
    why, against = explain(top, ctx)
    confidence = _percent(top.cf)
    alternatives = [
        {"cause": h.cause, "name": kb.causes[h.cause].name, "confidence": _percent(h.cf)}
        for h in decision.hypotheses[1:4] if h.cf >= 0.15
    ]
    sources = [kb.sources[s] for s in cause.sources if s in kb.sources]

    lines = []
    if decision.confident:
        lines.append(f"Скорее всего, причина: {cause.name} (уверенность {confidence}%).")
    else:
        lines.append(f"Данных пока недостаточно, но наиболее вероятная причина: {cause.name} (уверенность {confidence}%).")
    lines.append(cause.summary)
    if why:
        lines += ["", "Почему я так считаю:"] + [f"• {w}" for w in why]
    if against:
        lines += ["", "Что говорит против:"] + [f"• {a}" for a in against]
    lines += ["", "Что делать:"] + [f"{i}. {step}" for i, step in enumerate(cause.steps, 1)]
    lines += ["", URGENCY_TEXT[cause.urgency]]
    if alternatives:
        others = ", ".join(f"{a['name']} ({a['confidence']}%)" for a in alternatives)
        lines.append(f"Также возможно: {others}.")
    lines.append("Это подсказка по описанию, а не замена осмотра растения.")

    return Reply(
        kind="diagnosis",
        text="\n".join(lines),
        diagnosis={
            "cause": cause.id,
            "name": cause.name,
            "confidence": confidence,
            "confident": decision.confident,
            "urgency": cause.urgency,
            "summary": cause.summary,
            "steps": list(cause.steps),
            "why": why,
            "against": against,
            "alternatives": alternatives,
            "sources": sources,
        },
    )


def uncertain_reply(kb: Knowledge, decision: Decision) -> Reply:
    options = [
        f"{kb.causes[h.cause].name} ({_percent(h.cf)}%)"
        for h in decision.hypotheses[:3] if h.cf >= 0.1
    ]
    text = "Пока не могу уверенно назвать причину."
    if options:
        text += " Возможные варианты: " + "; ".join(options) + "."
    text += " Опишите подробнее, что вы видите (листья, стебель, земля), и я уточню."
    return Reply(kind="uncertain", text=text)
