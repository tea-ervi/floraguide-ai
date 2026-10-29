"""Тесты экспертной системы. Запуск из папки backend:  python -m pytest tests -q"""
from datetime import date
from pathlib import Path

import pytest

from app.services.expert import compute_schedule, load_knowledge, make_context, suggested_interval
from app.services.expert import nlu
from app.services.expert.engine import combine, diagnose
from app.services.expert.knowledge_base import KnowledgeError, lint, load_knowledge as load_from
from app.services.expert.service import handle_turn, new_state
from app.services.expert.simulate import load_cases, run_case

CASES = load_cases(Path(__file__).parent / "expert_cases.yaml")


@pytest.fixture(scope="module")
def kb():
    return load_knowledge()


def ctx_for(kb, **kwargs):
    base = dict(plant_name="Монстера", min_days=7, max_days=10, today=date(2026, 7, 15))
    base.update(kwargs)
    return make_context(kb.settings, **base)


# ---------------------------------------------------------------- база знаний
def test_knowledge_is_valid_and_complete(kb):
    assert lint(kb) == []


def test_broken_knowledge_is_rejected(tmp_path):
    import shutil
    from app.services.expert.knowledge_base import KNOWLEDGE_DIR

    shutil.copytree(KNOWLEDGE_DIR, tmp_path / "k")
    rules = tmp_path / "k" / "rules.yaml"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n  - {id: bad, cause: nope, all: [unknown_symptom], cf: 2, explain: x}\n",
                     encoding="utf-8")
    with pytest.raises(KnowledgeError) as error:
        load_from(tmp_path / "k")
    assert "unknown_symptom" in str(error.value) and "nope" in str(error.value)


# ---------------------------------------------------------------- коэффициенты уверенности
def test_cf_combination():
    assert combine([0.5, 0.5]) == pytest.approx(0.75)
    assert combine([0.8]) == pytest.approx(0.8)
    assert combine([0.6, -0.6]) == pytest.approx(0.0)
    assert combine([0.9, -0.6]) == pytest.approx(0.75)
    assert combine([0.5, 0.3]) == pytest.approx(combine([0.3, 0.5]))      # порядок не важен
    assert combine([-0.5]) == pytest.approx(-0.5)


# ---------------------------------------------------------------- понимание текста
@pytest.mark.parametrize("text,present,absent", [
    ("желтеют нижние листья", {"yellow_lower_leaves"}, set()),
    ("листья пожелтели и земля мокрая", {"yellow_leaves", "wet_soil"}, set()),
    ("растение поникло", {"wilting"}, set()),
    ("на листьях паутинка", {"webbing"}, set()),
    ("земля не сухая", set(), {"dry_soil"}),
    ("нет паутины, листья желтеют", {"yellow_leaves"}, {"webbing"}),
    ("кончики листьев сохнут, стоит у батареи", {"dry_brown_tips", "near_heater"}, set()),
    ("в горшке нет дырок", {"no_drainage"}, set()),
    ("светлые пятна на листьях", {"bleached_patches"}, set()),     # вложенное «пятна на листьях» вытеснено
    ("концы листьев сильно желтеют", {"dry_brown_tips", "yellow_leaves"}, set()),   # желтеют именно концы, это не общее пожелтение
    ("желтеют кончики листьев", {"dry_brown_tips"}, set()),
    ("листья желтеют, кончики не сохнут", {"yellow_leaves"}, {"dry_brown_tips"}),
])
def test_nlu_extracts_symptoms(kb, text, present, absent):
    result = nlu.analyze(kb, text)
    assert result.present == present and result.absent == absent


def test_nlu_answers_to_pending_question(kb):
    assert nlu.analyze(kb, "нет, она сухая", pending="wet_soil").answer == "no"
    assert nlu.analyze(kb, "да", pending="wet_soil").answer == "yes"
    assert nlu.analyze(kb, "не знаю", pending="wet_soil").answer == "unknown"
    # «нет» входит в синоним «нет дырок в горшке», это не ответ на вопрос
    result = nlu.analyze(kb, "нет дырок в горшке", pending="wet_soil")
    assert result.answer is None and result.present == {"no_drainage"}


def test_nlu_intents(kb):
    assert nlu.analyze(kb, "когда мне поливать?").intent == "schedule"
    assert nlu.analyze(kb, "привет").intent == "help"
    assert nlu.analyze(kb, "после полива листья желтеют").intent is None


def test_semantic_layer_is_used_only_when_dictionary_fails(kb):
    """Векторный слой подключается как запасной: словарь главнее, а ниже порога симптом не выбирается."""
    def fake_embed(texts):
        out = []
        for t in texts:
            if "вянет" in t or "вянут" in t or "скисло" in t:
                out.append([1.0, 0.0, 0.0])        # «вяло»: те же направление, что у симптома wilting
            elif t == "что-то странное":
                out.append([0.0, 0.0, 1.0])        # ни на что не похоже
            else:
                out.append([0.0, 1.0, 0.0])
        return out

    nlu.set_semantic(fake_embed, threshold=0.9)
    try:
        kb.cache.pop("semantic_phrases", None)
        lexical = nlu.analyze(kb, "растение вянет")
        assert lexical.present == {"wilting"} and lexical.semantic is False   # словарь справился сам
        found = nlu.analyze(kb, "растение скисло")
        assert found.present == {"wilting"} and found.semantic is True        # словарь не знает слова «скисло»
        assert nlu.analyze(kb, "что-то странное").present == set()            # ниже порога
    finally:
        nlu.set_semantic(None)
        kb.cache.pop("semantic_phrases", None)


# ---------------------------------------------------------------- расписание и контекст
def test_suggested_interval():
    assert suggested_interval(5, 7) == 6
    assert suggested_interval(7, 10) == 8
    assert suggested_interval(3, None) == 3
    assert suggested_interval(None, None) == 7


def test_schedule_is_seasonal(kb):
    common = dict(interval_days=7, min_days=None, max_days=None, last_watered=date(2026, 1, 1), planted_at=None)
    winter = compute_schedule(kb.settings, is_succulent=False, today=date(2026, 1, 10), **common)
    summer = compute_schedule(kb.settings, is_succulent=False, today=date(2026, 7, 10), **common)
    succulent = compute_schedule(kb.settings, is_succulent=True, today=date(2026, 1, 10), **common)
    assert (summer.interval, winter.interval, succulent.interval) == (7, 9, 13)
    assert winter.next_date == date(2026, 1, 10) and winter.days_until == 0


def test_context_facts(kb):
    overdue = ctx_for(kb, interval_days=7, last_watered=date(2026, 7, 1))
    assert overdue.facts["watering_overdue"] is True and overdue.facts["watering_on_time"] is False
    recent = ctx_for(kb, interval_days=7, last_watered=date(2026, 7, 14))
    assert recent.facts["recently_watered"] is True
    unknown = ctx_for(kb)
    assert unknown.facts["watering_overdue"] is None                      # нет истории поливов
    frequent = ctx_for(kb, interval_days=4, min_days=10, max_days=14)
    assert frequent.facts["interval_below_recommended"] is True


# ---------------------------------------------------------------- вывод и диалог
def test_context_changes_the_diagnosis(kb):
    """Один и тот же симптом: при просроченном поливе вероятнее нехватка воды, при свежем перелив."""
    state = {"present": ["wilting"], "absent": []}
    dry = ctx_for(kb, interval_days=7, last_watered=date(2026, 7, 1))
    wet = ctx_for(kb, interval_days=7, last_watered=date(2026, 7, 14))
    assert diagnose(kb, dry, {"wilting"}, set())[0].cause == "underwatering"
    causes_wet = {h.cause for h in diagnose(kb, wet, {"wilting"}, set())}
    assert "underwatering" not in causes_wet


def test_dialog_asks_then_diagnoses(kb):
    ctx = ctx_for(kb, interval_days=8, last_watered=date(2026, 7, 13))
    reply, state = handle_turn(kb, ctx, new_state(), text="листья желтеют")
    assert reply.kind == "question" and reply.question["symptom"] == "wet_soil"
    reply, state = handle_turn(kb, ctx, state, text="да")
    assert reply.kind == "diagnosis" and reply.diagnosis["cause"] == "overwatering"
    assert reply.diagnosis["why"] and reply.diagnosis["steps"]


def test_dialog_never_repeats_a_question(kb):
    ctx = ctx_for(kb, interval_days=8, last_watered=date(2026, 7, 13))
    reply, state = handle_turn(kb, ctx, new_state(), text="листья желтеют")
    asked = []
    for _ in range(6):
        if reply.kind != "question":
            break
        asked.append(reply.question["symptom"])
        reply, state = handle_turn(kb, ctx, state, answer={"symptom": reply.question["symptom"], "value": "unknown"})
    assert len(asked) == len(set(asked)) and len(asked) <= kb.settings["dialog"]["max_questions"]


def test_dialog_handles_unclear_input(kb):
    ctx = ctx_for(kb)
    reply, state = handle_turn(kb, ctx, new_state(), text="что-то не так")
    assert reply.kind == "need_info" and reply.suggestions
    reply, _ = handle_turn(kb, ctx, new_state(), text="когда поливать?")
    assert reply.kind == "info" and "интервал" in reply.text


def test_state_is_not_mutated(kb):
    ctx = ctx_for(kb)
    state = new_state()
    handle_turn(kb, ctx, state, text="листья желтеют")
    assert state == new_state()


# ---------------------------------------------------------------- сквозные случаи
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(kb, case):
    result = run_case(kb, case)
    assert result["ok"], f"ожидалось {result['expect']}, система: {result['got']}"
