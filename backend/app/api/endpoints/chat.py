from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import chat as chat_crud
from app.crud import user_plant as user_plant_crud
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatHistoryResponse, ChatMessageOut, ChatPostRequest, ChatTurnResponse
from app.services.expert import build_context, get_knowledge, handle_turn

router = APIRouter(prefix="/me/plants/{user_plant_id}/chat", tags=["Chat"])

ANSWER_LABELS = {"yes": "Да", "no": "Нет", "unknown": "Не знаю"}


def _own_plant_or_404(db: Session, user: User, user_plant_id: int):
    plant = user_plant_crud.get_user_plant(db, user.id, user_plant_id)
    if plant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    return plant


@router.get("", response_model=ChatHistoryResponse)
def get_history(
    user_plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История чата этого растения (пустой список, если разговор ещё не начинали)."""
    plant = _own_plant_or_404(db, current_user, user_plant_id)
    session = chat_crud.get_session(db, plant)
    return {"messages": chat_crud.list_messages(db, session)}


@router.post("", response_model=ChatTurnResponse)
def post_message(
    user_plant_id: int,
    data: ChatPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сообщение пользователя (текстом или ответом-кнопкой) и ответ экспертной системы."""
    plant = _own_plant_or_404(db, current_user, user_plant_id)
    kb = get_knowledge()
    if data.answer and data.answer.symptom not in kb.symptoms:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Неизвестный код симптома «{data.answer.symptom}». В answer.symptom передают код из "
                "вопроса системы (например, wet_soil). Чтобы описать проблему словами, используйте поле text."
            ),
        )
    ctx = build_context(plant, kb.settings, today=date.today())

    session = chat_crud.get_or_create_session(db, plant)
    answer = data.answer.model_dump() if data.answer else None
    reply, new_state = handle_turn(kb, ctx, session.state or None, text=data.text, answer=answer)

    user_text = data.text or ANSWER_LABELS[data.answer.value]
    user_message = chat_crud.add_message(db, session, "user", user_text)
    assistant_message = chat_crud.add_message(db, session, "assistant", reply.text, reply.to_dict())
    session.state = new_state          # присваиваем новый словарь, чтобы SQLAlchemy заметил изменение
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return {"user_message": user_message, "assistant_message": assistant_message}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def reset_chat(
    user_plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Начать разговор заново: история и состояние диалога удаляются."""
    plant = _own_plant_or_404(db, current_user, user_plant_id)
    chat_crud.reset_session(db, plant)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
