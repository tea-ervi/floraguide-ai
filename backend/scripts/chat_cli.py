"""
Консольный чат с экспертной системой: можно пробовать диалог без базы данных и интерфейса.

Запуск из папки backend:

  python scripts/chat_cli.py
  python scripts/chat_cli.py --plant Монстера --min-days 7 --max-days 10 --interval 8 --days-since-watering 3 --season summer
  python scripts/chat_cli.py --category "Суккуленты и кактусы" --season winter

Команды в чате: /сброс (начать заново), /состояние (что система уже знает), /выход.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.expert import KnowledgeError, handle_turn, load_knowledge, new_state  # noqa: E402
from app.services.expert.simulate import context_from_case  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Консольный чат с экспертной системой")
    parser.add_argument("--plant", default="Монстера")
    parser.add_argument("--category", default="Комнатные растения")
    parser.add_argument("--interval", type=int, help="интервал полива пользователя, дней")
    parser.add_argument("--min-days", type=int, default=7)
    parser.add_argument("--max-days", type=int, default=10)
    parser.add_argument("--days-since-watering", type=int, help="сколько дней назад поливали")
    parser.add_argument("--season", choices=["winter", "spring", "summer", "autumn"], default="summer")
    parser.add_argument("--lux", type=int)
    parser.add_argument("--humidity", type=int)
    args = parser.parse_args()

    try:
        kb = load_knowledge()
    except KnowledgeError as e:
        print(e)
        return 1

    ctx = context_from_case(kb, {
        "name": args.plant, "category": args.category, "interval": args.interval,
        "min_days": args.min_days, "max_days": args.max_days,
        "days_since_watering": args.days_since_watering, "season": args.season,
        "lux": args.lux, "humidity": args.humidity,
    })
    print(f"Растение: {args.plant}. Сезон: {ctx.values['season']}. Интервал полива: {ctx.values['interval']} дн. "
          f"Полив: {ctx.values['days_since']} дн. назад.")
    print("Опишите проблему. Команды: /сброс, /состояние, /выход\n")

    state = new_state()
    while True:
        try:
            line = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("/выход", "/exit"):
            return 0
        if line in ("/сброс", "/reset"):
            state = new_state()
            print("Начали заново.\n")
            continue
        if line in ("/состояние", "/state"):
            print({k: state[k] for k in ("present", "absent", "asked", "pending")}, "\n")
            continue

        reply, state = handle_turn(kb, ctx, state, text=line)
        print(f"\nСистема: {reply.text}")
        if reply.kind == "question":
            print("         (ответьте: да / нет / не знаю)")
        if reply.suggestions:
            print("         Например: " + "; ".join(s["text"] for s in reply.suggestions[:4]))
        print()


if __name__ == "__main__":
    raise SystemExit(main())
