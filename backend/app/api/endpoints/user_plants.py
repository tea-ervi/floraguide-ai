from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import user_plant as crud
from app.database import get_db
from app.models.user import User
from app.schemas.user_plant import UserPlantCreate, UserPlantResponse, UserPlantUpdate

router = APIRouter(prefix="/me/plants", tags=["My plants"])


def _get_own_or_404(db: Session, user: User, user_plant_id: int):
    obj = crud.get_user_plant(db, user.id, user_plant_id)
    if obj is None:
        # Один и тот же ответ для «нет такого» и «чужое»: не раскрываем существование чужих записей
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    return obj


@router.get("", response_model=list[UserPlantResponse])
def list_my_plants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Мои растения. Сначала те, которые нужно полить раньше всего."""
    plants = [
        UserPlantResponse.model_validate(p)
        for p in crud.list_user_plants(db, current_user.id)
    ]
    plants.sort(key=lambda p: (p.next_watering_date is None, p.next_watering_date))
    return plants


@router.post("", response_model=UserPlantResponse, status_code=status.HTTP_201_CREATED)
def add_my_plant(
    data: UserPlantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавить растение из каталога в свой профиль."""
    if not crud.species_exists(db, data.plant_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Растение каталога не найдено")
    return crud.create_user_plant(db, current_user.id, data)


@router.get("/{user_plant_id}", response_model=UserPlantResponse)
def get_my_plant(
    user_plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_own_or_404(db, current_user, user_plant_id)


@router.patch("/{user_plant_id}", response_model=UserPlantResponse)
def update_my_plant(
    user_plant_id: int,
    data: UserPlantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Изменить название, дату посадки или интервал полива."""
    obj = _get_own_or_404(db, current_user, user_plant_id)
    return crud.update_user_plant(db, obj, data.model_dump(exclude_unset=True))


@router.post("/{user_plant_id}/water", response_model=UserPlantResponse)
def water_my_plant(
    user_plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отметить, что растение полито сейчас."""
    obj = _get_own_or_404(db, current_user, user_plant_id)
    return crud.mark_watered(db, obj)


@router.delete("/{user_plant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_plant(
    user_plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = _get_own_or_404(db, current_user, user_plant_id)
    crud.delete_user_plant(db, obj)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
