from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ChatAnswer(BaseModel):
    """Ответ кнопкой на уточняющий вопрос системы."""

    symptom: str = Field(
        min_length=1, max_length=64,
        description="Код симптома из вопроса системы (поле question.symptom в её ответе), "
                    "например wet_soil. Это не текст жалобы.",
    )
    value: Literal["yes", "no", "unknown"] = Field(description="yes: да, no: нет, unknown: не знаю")


class ChatPostRequest(BaseModel):
    """Нужно передать либо text (своими словами), либо answer (ответ на вопрос системы)."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"text": "листья желтеют"}]})

    text: str | None = Field(
        None, max_length=500,
        description="Сообщение своими словами, например: «листья желтеют и земля мокрая»",
    )
    answer: ChatAnswer | None = Field(
        None, description="Только для ответа на уточняющий вопрос. Для обычного сообщения не передавайте.",
    )

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def _need_something(self):
        if not self.text and not self.answer:
            raise ValueError("Нужно передать text или answer")
        return self


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    text: str
    meta: dict[str, Any] | None = None
    created_at: datetime


class ChatTurnResponse(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]
