from datetime import datetime, timezone

from sqlalchemy import JSON, TIMESTAMP, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utc_now() -> datetime:
    # Колонки TIMESTAMP без часового пояса: храним UTC без tzinfo
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatSession(Base):
    """Диалог пользователя с экспертной системой об одном его растении."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    # ondelete=CASCADE: при удалении растения из профиля его чат удаляется базой данных
    user_plant_id = Column(
        Integer, ForeignKey("user_plants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    state = Column(JSON, nullable=False, default=dict)   # состояние диалога (см. services/expert/service.py)
    created_at = Column(TIMESTAMP, nullable=False, default=_utc_now)
    updated_at = Column(TIMESTAMP, nullable=False, default=_utc_now, onupdate=_utc_now)

    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String(16), nullable=False)            # "user" или "assistant"
    text = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True)                   # для ответов системы: вопрос с кнопками, диагноз и т.д.
    created_at = Column(TIMESTAMP, nullable=False, default=_utc_now)

    session = relationship("ChatSession", back_populates="messages")
