from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.user import UserPlant


def get_session(db: Session, user_plant: UserPlant) -> ChatSession | None:
    return db.execute(
        select(ChatSession).where(ChatSession.user_plant_id == user_plant.id)
    ).scalar_one_or_none()


def get_or_create_session(db: Session, user_plant: UserPlant) -> ChatSession:
    session = get_session(db, user_plant)
    if session is None:
        session = ChatSession(user_plant_id=user_plant.id, state={})
        db.add(session)
        db.flush()
    return session


def list_messages(db: Session, session: ChatSession | None, limit: int = 200) -> list[ChatMessage]:
    if session is None:
        return []
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(db.execute(stmt).scalars().all()))


def add_message(db: Session, session: ChatSession, role: str, text: str, meta: dict | None = None) -> ChatMessage:
    message = ChatMessage(session_id=session.id, role=role, text=text, meta=meta)
    db.add(message)
    db.flush()
    return message


def reset_session(db: Session, user_plant: UserPlant) -> None:
    session = get_session(db, user_plant)
    if session is not None:
        db.delete(session)    # сообщения удаляются каскадом
        db.commit()
