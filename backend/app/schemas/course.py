from pydantic import BaseModel, Field


class CourseSummary(BaseModel):
    slug: str
    title: str
    description: str
    topic: str
    topic_label: str
    level: str
    duration_minutes: int
    questions_count: int


class SourceOut(BaseModel):
    title: str
    url: str


class CourseDetail(CourseSummary):
    notes: str
    sources: list[SourceOut]


class OptionOut(BaseModel):
    """Вариант ответа без признака верности и пояснения."""

    id: str
    text: str


class QuestionOut(BaseModel):
    id: str
    topic: str
    situation: str
    question: str
    options: list[OptionOut]


class TestOut(BaseModel):
    course: str
    title: str
    questions: list[QuestionOut]


class CheckRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    option_id: str = Field(min_length=1, max_length=64)


class CheckResponse(BaseModel):
    correct: bool
    feedback: str
