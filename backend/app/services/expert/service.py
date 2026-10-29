"""Один ход диалога: сообщение пользователя на входе, ответ и новое состояние на выходе.

Модуль не знает ни о базе данных, ни о веб-фреймворке: состояние диалога это обычный словарь,
который вызывающий код сохраняет сам (в API это таблица chat_sessions).
"""
from __future__ import annotations

import copy
from typing import Any

from . import nlu
from .context import PlantContext
from .dialog import decide
from .knowledge_base import Knowledge
from .responder import (
    Reply, diagnosis_reply, help_reply, info_reply, need_info_reply, question_reply,
    schedule_reply, uncertain_reply,
)


def new_state() -> dict[str, Any]:
    return {
        "present": [],          # подтверждённые симптомы
        "absent": [],           # симптомы, которые пользователь явно отрицает
        "asked": [],            # о чём уже спрашивали (повторно не спрашиваем)
        "pending": None,        # симптом, ответа на который ждём
        "round_questions": 0,   # сколько вопросов задано с последнего диагноза
        "turns": 0,
        "last_cause": None,
    }


def _apply(state: dict, symptom: str, value: str) -> None:
    present, absent = set(state["present"]), set(state["absent"])
    if value == "yes":
        present.add(symptom)
        absent.discard(symptom)
    elif value == "no":
        absent.add(symptom)
        present.discard(symptom)
    asked = list(state["asked"])
    if symptom not in asked:
        asked.append(symptom)
    state["present"], state["absent"], state["asked"] = sorted(present), sorted(absent), asked
    if state.get("pending") == symptom:
        state["pending"] = None


def handle_turn(
    kb: Knowledge,
    ctx: PlantContext,
    state: dict[str, Any] | None,
    *,
    text: str | None = None,
    answer: dict[str, str] | None = None,
) -> tuple[Reply, dict[str, Any]]:
    st = copy.deepcopy(state) if state else new_state()
    for key, default in new_state().items():
        st.setdefault(key, default)
    st["turns"] += 1
    pending = st["pending"]
    changed = False

    # ответ кнопкой: {"symptom": "wet_soil", "value": "yes"}
    if answer and answer.get("symptom") in kb.symptoms and answer.get("value") in ("yes", "no", "unknown"):
        _apply(st, answer["symptom"], answer["value"])
        changed = True

    # свободный текст
    if text and text.strip():
        result = nlu.analyze(kb, text, pending=st["pending"])
        if result.answer and st["pending"]:
            _apply(st, st["pending"], result.answer)
            changed = True
        for sid in sorted(result.present):
            _apply(st, sid, "yes")
            changed = True
        for sid in sorted(result.absent):
            _apply(st, sid, "no")
            changed = True

        if not changed and result.intent:
            reply = schedule_reply(ctx) if result.intent == "schedule" else help_reply()
            return reply, st

    if not changed:
        if st["pending"]:
            reply = question_reply(kb, st["pending"], prefix="Не совсем поняла ответ. Выберите вариант: ")
            return reply, st
        if st["present"]:
            reply = info_reply(
                "Не нашла в сообщении новых симптомов. Опишите, что изменилось, или начните новый разговор."
            )
            return reply, st
        return need_info_reply(kb, prefix="Не совсем поняла. "), st

    decision = decide(kb, ctx, st)
    if decision.kind == "question":
        st["pending"] = decision.question
        if decision.question not in st["asked"]:
            st["asked"].append(decision.question)
        st["round_questions"] += 1
        return question_reply(kb, decision.question), st

    st["pending"] = None
    if decision.kind == "diagnosis":
        st["last_cause"] = decision.hypotheses[0].cause
        st["round_questions"] = 0
        return diagnosis_reply(kb, ctx, decision), st
    if decision.kind == "uncertain":
        st["round_questions"] = 0
        return uncertain_reply(kb, decision), st
    return need_info_reply(kb, prefix="Записала. "), st
