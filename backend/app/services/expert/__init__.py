"""Экспертная система FloraGuide: диагностика проблем комнатных растений.

Состав:
  knowledge/        база знаний (симптомы, причины, правила, настройки) в YAML
  knowledge_base.py загрузка и проверка базы знаний
  context.py        факты о растении из данных профиля
  schedule.py       расписание полива с учётом сезона
  nlu.py            понимание текста пользователя
  engine.py         машина вывода (коэффициенты уверенности)
  dialog.py         выбор следующего шага диалога
  explain.py        объяснение вывода
  responder.py      формирование ответов
  service.py        один ход диалога
"""
from .context import PlantContext, build_context, make_context
from .knowledge_base import Knowledge, KnowledgeError, get_knowledge, lint, load_knowledge
from .schedule import compute_schedule, suggested_interval
from .service import handle_turn, new_state

__all__ = [
    "Knowledge", "KnowledgeError", "PlantContext", "build_context", "compute_schedule",
    "get_knowledge", "handle_turn", "lint", "load_knowledge", "make_context", "new_state",
    "suggested_interval",
]
