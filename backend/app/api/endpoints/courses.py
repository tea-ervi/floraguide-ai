from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.course import (
    CheckRequest, CheckResponse, CourseDetail, CourseSummary, OptionOut, QuestionOut, SourceOut, TestOut,
)
from app.services.courses import TOPICS, Course, check_answer, get_courses

router = APIRouter(prefix="/courses", tags=["Courses"])


def _summary(course: Course) -> dict:
    return {
        "slug": course.slug, "title": course.title, "description": course.description, "topic": course.topic,
        "topic_label": course.topic_label, "level": course.level, "duration_minutes": course.duration_minutes,
        "questions_count": len(course.questions),
    }


def _course_or_404(slug: str) -> Course:
    course = get_courses().get(slug)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    return course


@router.get("", response_model=list[CourseSummary])
def list_courses(topic: str | None = Query(None, description=f"Тема: {', '.join(TOPICS)}")):
    """Все курсы, при необходимости по одной теме."""
    courses = get_courses().values()
    return [_summary(c) for c in courses if topic is None or c.topic == topic]


@router.get("/{slug}", response_model=CourseDetail)
def get_course(slug: str):
    """Описание курса и конспект (Markdown)."""
    course = _course_or_404(slug)
    return {**_summary(course), "notes": course.notes, "sources": [SourceOut(title=s.title, url=s.url) for s in course.sources]}


@router.get("/{slug}/test", response_model=TestOut)
def get_test(slug: str):
    """Вопросы теста. Верные ответы и пояснения здесь не передаются."""
    course = _course_or_404(slug)
    return TestOut(
        course=course.slug,
        title=course.test_title,
        questions=[
            QuestionOut(
                id=q.id, topic=q.topic, situation=q.situation, question=q.question,
                options=[OptionOut(id=o.id, text=o.text) for o in q.options],
            )
            for q in course.questions
        ],
    )


@router.post("/{slug}/test/check", response_model=CheckResponse)
def check(slug: str, data: CheckRequest):
    """Проверяет один выбранный вариант. Верный вариант при ошибке не раскрывается, только пояснение."""
    course = _course_or_404(slug)
    result = check_answer(course, data.question_id, data.option_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Вопрос или вариант ответа не найден")
    correct, feedback = result
    return CheckResponse(correct=correct, feedback=feedback)
