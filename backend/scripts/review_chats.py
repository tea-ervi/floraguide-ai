"""
Разбор реальных диалогов из базы данных: где система не поняла пользователя и в чём сомневалась.

Это главный источник новых тренировочных данных: непонятые фразы становятся синонимами в symptoms.yaml,
а сомнительные диагнозы подсказывают, каких правил и вопросов не хватает.

Запуск из папки backend (нужны таблицы чата и хотя бы несколько диалогов):

  python scripts/review_chats.py
  python scripts/review_chats.py --days 14 --top 30
  python scripts/review_chats.py --export tests/unrecognized.yaml    # фразы для разбора, с пустым полем symptom

В диалогах лежат тексты пользователей. Разбирайте их только на своих тестовых аккаунтах или без
персональных данных, фразы в отчёте и файл экспорта в Git не публикуйте.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import yaml  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BUTTON_ANSWERS = {"да", "нет", "не знаю"}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip()).strip(" .!?,;:")


def main() -> int:
    parser = argparse.ArgumentParser(description="Разбор диалогов экспертной системы")
    parser.add_argument("--days", type=int, default=30, help="за сколько последних дней (по умолчанию 30)")
    parser.add_argument("--top", type=int, default=20, help="сколько фраз показывать в каждом списке")
    parser.add_argument("--export", type=Path, help="сохранить непонятые фразы в YAML для разбора")
    args = parser.parse_args()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.chat import ChatMessage, ChatSession
    from app.models.plant import PlantSpecies  # noqa: F401  (нужны для настройки связей моделей)
    from app.models.user import User, UserPlant  # noqa: F401

    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{n}".format(
        u=os.getenv("DB_USER", "postgres"), p=os.getenv("DB_PASSWORD", "postgres"),
        h=os.getenv("DB_HOST", "127.0.0.1"), port=os.getenv("DB_PORT", "5433"),
        n=os.getenv("DB_NAME", "floraguide_db"),
    )
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.days)
    with sessionmaker(bind=create_engine(url))() as db:
        rows = (
            db.query(ChatMessage.session_id, ChatMessage.role, ChatMessage.text, ChatMessage.meta)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .filter(ChatMessage.created_at >= since)
            .order_by(ChatMessage.session_id, ChatMessage.id)
            .all()
        )
    if not rows:
        print(f"За последние {args.days} дн. диалогов нет.")
        return 0

    sessions = {r.session_id for r in rows}
    user_messages = sum(1 for r in rows if r.role == "user")
    unrecognized: Counter[str] = Counter()     # система не нашла симптомов
    unclear_answers: Counter[str] = Counter()  # не поняла ответ на свой вопрос
    no_new_info: Counter[str] = Counter()
    causes: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    shaky: list[tuple[str, int, str]] = []     # диагнозы с низкой уверенностью: (причина, процент, фраза)

    previous_user: dict[int, str] = {}
    for r in rows:
        if r.role == "user":
            previous_user[r.session_id] = r.text
            continue
        meta = r.meta or {}
        kind = meta.get("kind", "?")
        kinds[kind] += 1
        said = clean(previous_user.get(r.session_id, ""))
        if said in BUTTON_ANSWERS or not said:
            said = ""
        if kind == "need_info" and r.text.startswith("Не совсем поняла") and said:
            unrecognized[said] += 1
        elif kind == "question" and r.text.startswith("Не совсем поняла ответ") and said:
            unclear_answers[said] += 1
        elif kind == "info" and r.text.startswith("Не нашла в сообщении") and said:
            no_new_info[said] += 1
        elif kind == "diagnosis" and meta.get("diagnosis"):
            d = meta["diagnosis"]
            causes[d["cause"]] += 1
            if not d.get("confident"):
                shaky.append((d["cause"], d["confidence"], said))

    print(f"За {args.days} дн.: диалогов {len(sessions)}, сообщений пользователей {user_messages}, "
          f"ответов системы {sum(kinds.values())}.\n")
    print("Ответы системы по типам: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    if causes:
        print("Диагнозы: " + ", ".join(f"{k} {v}" for k, v in causes.most_common()))

    def show(title: str, counter: Counter, hint: str) -> None:
        if counter:
            print(f"\n{title} ({hint}):")
            for text, count in counter.most_common(args.top):
                print(f"  {count:>3} × «{text}»")

    show("Не поняла сообщение", unrecognized, "добавьте синонимы в symptoms.yaml")
    show("Не поняла ответ на свой вопрос", unclear_answers, "проверьте формулировку вопроса и синонимы")
    show("Нет новых симптомов", no_new_info, "возможно, это новые симптомы без синонимов")
    if shaky:
        print(f"\nДиагнозы с низкой уверенностью ({len(shaky)}), нужны правила или вопросы:")
        for cause, pct, said in shaky[: args.top]:
            print(f"  {cause} {pct}% после «{said or '...'}»")

    if args.export:
        items = [{"text": t, "count": c, "symptom": ""} for t, c in (unrecognized + unclear_answers + no_new_info).most_common()]
        args.export.write_text(
            "# Фразы, которые система не поняла. Впишите в symptom код симптома (из symptoms.yaml),\n"
            "# затем добавьте фразу в synonyms этого симптома и в tests/phrases.yaml.\n"
            + yaml.safe_dump({"unrecognized": items}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"\nСохранено фраз: {len(items)} в {args.export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
