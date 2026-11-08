"""
Проверка материалов курсов: ошибки в YAML, один верный вариант на вопрос, пояснения, признаки слабого теста.

Запуск из папки backend:  python scripts/validate_courses.py
Код выхода 1, если найдены ошибки. Запускайте после каждой правки курса.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.api.endpoints.courses import CONTENT_DIR, CourseError, load_courses, quality_warnings  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        courses = load_courses()
    except CourseError as e:
        print(e)
        return 1
    if not courses:
        print(f"Курсов нет в {CONTENT_DIR}")
        return 1
    for course in courses.values():
        positions = [next(i for i, o in enumerate(q.options) if o.correct) for q in course.questions]
        letters = "abcde"
        spread = ", ".join(f"{letters[p]}: {positions.count(p)}" for p in sorted(set(positions)))
        words = len(course.notes.split())
        print(f"{course.slug}: «{course.title}» ({course.topic_label})")
        print(f"  конспект: {words} слов; вопросов: {len(course.questions)}; источников: {len(course.sources)}")
        print(f"  позиции верных ответов: {spread}")
        warnings = quality_warnings(course)
        for w in warnings:
            print(f"  [!] {w}")
        if not warnings:
            print("  предупреждений нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
