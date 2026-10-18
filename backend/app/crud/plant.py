from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.plant import PlantCategory, PlantSpecies


def _escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE, чтобы '%' и '_' в запросе искались как обычные символы."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_categories(db: Session) -> list[PlantCategory]:
    stmt = select(PlantCategory).order_by(PlantCategory.name, PlantCategory.id)
    return list(db.execute(stmt).scalars().all())


def get_plants(
    db: Session,
    q: str | None = None,
    category_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[PlantSpecies], int]:
    conditions = []

    if category_id is not None:
        conditions.append(PlantSpecies.category_id == category_id)

    if q:
        pattern = f"%{_escape_like(q)}%"
        conditions.append(
            or_(
                PlantSpecies.name.ilike(pattern, escape="\\"),
                PlantSpecies.scientific_name.ilike(pattern, escape="\\"),
                PlantSpecies.description.ilike(pattern, escape="\\"),
            )
        )

    total = db.execute(
        select(func.count()).select_from(PlantSpecies).where(*conditions)
    ).scalar_one()

    stmt = (
        select(PlantSpecies)
        .options(joinedload(PlantSpecies.category))
        .where(*conditions)
        .order_by(PlantSpecies.name, PlantSpecies.id)
        .limit(limit)
        .offset(offset)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_plant(db: Session, plant_id: int) -> PlantSpecies | None:
    stmt = (
        select(PlantSpecies)
        .options(joinedload(PlantSpecies.category))
        .where(PlantSpecies.id == plant_id)
    )
    return db.execute(stmt).scalar_one_or_none()
