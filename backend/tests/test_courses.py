"""Тесты курсов. Запуск из папки backend:  python -m pytest tests/test_courses.py -q"""
import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import courses as courses_api
from backend.app.api.endpoints import courses as service
from backend.app.api.endpoints.courses import CONTENT_DIR, CourseError, load_courses, quality_warnings

app = FastAPI()
app.include_router(courses_api.router)
client = TestClient(app)


@pytest.fixture(scope="module")
def champignon():
    return load_courses()["champignon"]


# ---------------------------------------------------------------- содержимое курса
def test_champignon_course_is_complete(champignon):
    assert len(champignon.questions) == 15
    assert len(champignon.notes.split()) > 300
    assert champignon.sources
    for q in champignon.questions:
        assert sum(o.correct for o in q.options) == 1
        assert all(o.feedback.strip() for o in q.options)


def test_champignon_test_has_no_giveaways(champignon):
    assert quality_warnings(champignon) == []


# ---------------------------------------------------------------- проверка материалов
def test_broken_course_is_rejected(tmp_path):
    shutil.copytree(CONTENT_DIR / "champignon", tmp_path / "champignon")
    test_file = tmp_path / "champignon" / "test.yaml"
    text = test_file.read_text(encoding="utf-8")
    test_file.write_text(text.replace("correct: true", "correct: false", 1), encoding="utf-8")
    with pytest.raises(CourseError) as error:
        load_courses(tmp_path)
    assert "ровно один верный вариант" in str(error.value)


def test_slug_must_match_folder(tmp_path):
    shutil.copytree(CONTENT_DIR / "champignon", tmp_path / "other")
    with pytest.raises(CourseError) as error:
        load_courses(tmp_path)
    assert "не совпадает с названием папки" in str(error.value)


# ---------------------------------------------------------------- API
def test_list_and_filter_courses():
    data = client.get("/courses").json()
    assert [c["slug"] for c in data] == ["champignon"]
    assert data[0]["questions_count"] == 15 and data[0]["topic_label"] == "Грибы"
    assert client.get("/courses", params={"topic": "plants"}).json() == []
    assert len(client.get("/courses", params={"topic": "mushrooms"}).json()) == 1


def test_course_detail_has_notes_and_sources():
    data = client.get("/courses/champignon").json()
    assert data["notes"].startswith("## 1.") and data["sources"][0]["url"].startswith("https://")
    assert client.get("/courses/unknown").status_code == 404


def test_test_endpoint_does_not_leak_answers():
    response = client.get("/courses/champignon/test")
    assert response.status_code == 200
    body = response.text
    assert '"correct"' not in body and '"feedback"' not in body
    questions = response.json()["questions"]
    assert len(questions) == 15
    assert all(set(o) == {"id", "text"} for q in questions for o in q["options"])


def test_check_answer_correct_and_wrong(champignon):
    q = champignon.questions[0]
    right = next(o for o in q.options if o.correct)
    wrong = next(o for o in q.options if not o.correct)

    ok = client.post("/courses/champignon/test/check", json={"question_id": q.id, "option_id": right.id}).json()
    assert ok["correct"] is True and ok["feedback"] == right.feedback

    bad = client.post("/courses/champignon/test/check", json={"question_id": q.id, "option_id": wrong.id}).json()
    assert bad["correct"] is False and bad["feedback"] == wrong.feedback
    assert right.text not in bad["feedback"]            # верный вариант при ошибке не раскрывается


def test_check_answer_validation():
    url = "/courses/champignon/test/check"
    assert client.post(url, json={"question_id": "nope", "option_id": "a"}).status_code == 404
    assert client.post(url, json={"question_id": "q1", "option_id": "z"}).status_code == 404
    assert client.post(url, json={"question_id": "q1"}).status_code == 422
    assert client.post("/courses/unknown/test/check", json={"question_id": "q1", "option_id": "a"}).status_code == 404
