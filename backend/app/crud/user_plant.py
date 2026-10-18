from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.plant import PlantSpecies
from app.models.user import UserPlant
from app.schemas.user_plant import UserPlantCreate

# Временный интервал, пока расписание не считается экспертной системой
DEFAULT_WATERING_INTERVAL_DAYS = 7


def _utc_now() -> datetime:
    # Колонка TIMESTAMP без часового пояса: храним UTC без tzinfo
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _with_species():
    return joinedload(UserPlant.species).joinedload(PlantSpecies.category)


def list_user_plants(db: Session, user_id: int) -> list[UserPlant]:
    stmt = (
        select(UserPlant)
        .options(_with_species())
        .where(UserPlant.user_id == user_id)
        .order_by(UserPlant.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_user_plant(db: Session, user_id: int, user_plant_id: int) -> UserPlant | None:
    # Фильтр по user_id обязателен: пользователь не должен получить чужое растение
    stmt = (
        select(UserPlant)
        .options(_with_species())
        .where(UserPlant.id == user_plant_id, UserPlant.user_id == user_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def create_user_plant(db: Session, user_id: int, data: UserPlantCreate) -> UserPlant:
    obj = UserPlant(
        user_id=user_id,
        plant_id=data.plant_id,
        custom_name=data.custom_name,
        planted_at=data.planted_at or date.today(),
        watering_interval_days=data.watering_interval_days or DEFAULT_WATERING_INTERVAL_DAYS,
    )
    db.add(obj)
    db.commit()
    return get_user_plant(db, user_id, obj.id)  # перечитываем вместе с видом и категорией


def update_user_plant(db: Session, obj: UserPlant, changes: dict) -> UserPlant:
    for field, value in changes.items():
        setattr(obj, field, value)
    db.commit()
    return get_user_plant(db, obj.user_id, obj.id)


def mark_watered(db: Session, obj: UserPlant) -> UserPlant:
    obj.last_watered_at = _utc_now()
    db.commit()
    return get_user_plant(db, obj.user_id, obj.id)


def delete_user_plant(db: Session, obj: UserPlant) -> None:
    db.delete(obj)
    db.commit()


def species_exists(db: Session, plant_id: int) -> bool:
    return db.get(PlantSpecies, plant_id) is not None
