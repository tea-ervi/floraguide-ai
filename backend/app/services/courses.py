"""Курсы: загрузка из файлов и проверка ответов теста.

Содержимое лежит в backend/content/courses/<slug>/:
  course.yaml  описание курса и источники
  notes.md     конспект (Markdown)
  test.yaml    вопросы теста с вариантами и пояснениями

Правильные ответы никогда не отдаются в браузер: проверка идёт на сервере по одному ответу.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "courses"

TOPICS = {
    "plants": "Растения",
    "vegetables": "Овощи и фрукты",
    "mushrooms": "Грибы",
}


class CourseError(Exception):
    """В материалах курса найдены ошибки."""


@dataclass(frozen=True)
class Option:
    id: str
    text: str
    correct: bool
    feedback: str


@dataclass(frozen=True)
class Question:
    id: str
    topic: str
    situation: str
    question: str
    options: tuple[Option, ...]


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class Course:
    slug: str
    title: str
    description: str
    topic: str
    level: str
    duration_minutes: int
    sources: tuple[Source, ...]
    notes: str
    test_title: str
    questions: tuple[Question, ...]

    @property
    def topic_label(self) -> str:
        return TOPICS.get(self.topic, self.topic)


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise CourseError(f"{path.parent.name}/{path.name}: не удалось прочитать файл ({e})") from None
    if not isinstance(data, dict):
        raise CourseError(f"{path.parent.name}/{path.name}: ожидается словарь верхнего уровня")
    return data


def _load_course(folder: Path) -> Course:
    name = folder.name
    errors: list[str] = []
    meta = _read_yaml(folder / "course.yaml")
    test = _read_yaml(folder / "test.yaml")
    try:
        notes = (folder / "notes.md").read_text(encoding="utf-8").strip()
    except OSError:
        notes = ""

    for field in ("slug", "title", "description", "topic", "level"):
        if not str(meta.get(field) or "").strip():
            errors.append(f"course.yaml: не заполнено поле {field}")
    if meta.get("slug") and meta["slug"] != name:
        errors.append(f"course.yaml: slug «{meta['slug']}» не совпадает с названием папки «{name}»")
    if meta.get("topic") not in TOPICS:
        errors.append(f"course.yaml: topic должен быть одним из {', '.join(TOPICS)}")
    if not isinstance(meta.get("duration_minutes"), int) or meta["duration_minutes"] < 1:
        errors.append("course.yaml: duration_minutes должно быть целым числом больше нуля")
    if not notes:
        errors.append("notes.md: конспект пуст или не найден")

    sources = []
    for s in meta.get("sources") or []:
        if not (isinstance(s, dict) and s.get("title") and str(s.get("url", "")).startswith(("http://", "https://"))):
            errors.append(f"course.yaml: источник должен иметь title и ссылку http(s): {s}")
            continue
        sources.append(Source(s["title"], s["url"]))

    questions: list[Question] = []
    seen_questions: set[str] = set()
    for q in test.get("questions") or []:
        qid = str(q.get("id", "?"))
        if qid in seen_questions:
            errors.append(f"вопрос {qid}: повторяющийся id")
        seen_questions.add(qid)
        if not str(q.get("question") or "").strip():
            errors.append(f"вопрос {qid}: нет текста вопроса")
        raw_options = q.get("options") or []
        if not 3 <= len(raw_options) <= 5:
            errors.append(f"вопрос {qid}: нужно от 3 до 5 вариантов, найдено {len(raw_options)}")
        options, seen_options = [], set()
        for o in raw_options:
            oid = str(o.get("id", "?"))
            if oid in seen_options:
                errors.append(f"вопрос {qid}: повторяющийся id варианта {oid}")
            seen_options.add(oid)
            if not str(o.get("text") or "").strip():
                errors.append(f"вопрос {qid}, вариант {oid}: нет текста")
            if not str(o.get("feedback") or "").strip():
                errors.append(f"вопрос {qid}, вариант {oid}: нет пояснения (feedback)")
            options.append(Option(oid, str(o.get("text", "")), bool(o.get("correct")), str(o.get("feedback", ""))))
        if sum(o.correct for o in options) != 1:
            errors.append(f"вопрос {qid}: должен быть ровно один верный вариант")
        questions.append(
            Question(qid, str(q.get("topic", "")), str(q.get("situation", "")), str(q.get("question", "")), tuple(options))
        )
    if not questions:
        errors.append("test.yaml: нет вопросов")

    if errors:
        raise CourseError(f"Курс «{name}»:\n  - " + "\n  - ".join(errors))
    return Course(
        slug=meta["slug"], title=meta["title"], description=meta["description"], topic=meta["topic"],
        level=meta["level"], duration_minutes=meta["duration_minutes"], sources=tuple(sources), notes=notes,
        test_title=str(test.get("title") or "Тест"), questions=tuple(questions),
    )


def load_courses(directory: Path | None = None) -> dict[str, Course]:
    directory = directory or CONTENT_DIR
    courses: dict[str, Course] = {}
    if not directory.exists():
        return courses
    for folder in sorted(p for p in directory.iterdir() if p.is_dir() and (p / "course.yaml").exists()):
        course = _load_course(folder)
        courses[course.slug] = course
    return courses


@lru_cache(maxsize=1)
def get_courses() -> dict[str, Course]:
    return load_courses()


def quality_warnings(course: Course) -> list[str]:
    """Признаки слабого теста: по ним можно угадывать ответ, не понимая тему."""
    warnings: list[str] = []
    n = len(course.questions)
    if n < 5:
        warnings.append(f"в тесте всего {n} вопросов")
    positions = [next(i for i, o in enumerate(q.options) if o.correct) for q in course.questions]
    for pos in sorted(set(positions)):
        share = positions.count(pos) / n
        if share > 0.5:
            warnings.append(f"верный ответ стоит на позиции {pos + 1} в {share:.0%} вопросов")
    longest = sum(1 for q in course.questions if max(q.options, key=lambda o: len(o.text)).correct)
    shortest = sum(1 for q in course.questions if min(q.options, key=lambda o: len(o.text)).correct)
    if longest / n > 0.6:
        warnings.append(f"верный ответ самый длинный в {longest} из {n} вопросов: его можно угадать по длине")
    if shortest / n > 0.6:
        warnings.append(f"верный ответ самый короткий в {shortest} из {n} вопросов: его можно угадать по длине")
    return warnings


def check_answer(course: Course, question_id: str, option_id: str) -> tuple[bool, str] | None:
    """(верно ли, пояснение) или None, если вопроса или варианта нет."""
    question = next((q for q in course.questions if q.id == question_id), None)
    if question is None:
        return None
    option = next((o for o in question.options if o.id == option_id), None)
    if option is None:
        return None
    return option.correct, option.feedback
