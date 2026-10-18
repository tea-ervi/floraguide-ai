from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import plant as plant_crud
from app.database import get_db
from app.schemas.plant import PlantDetail, PlantListResponse

router = APIRouter(prefix="/plants", tags=["Catalog"])


@router.get("", response_model=PlantListResponse)
def list_plants(
    q: str | None = Query(
        None,
        max_length=100,
        description="Поиск по названию, латинскому названию и описанию",
    ),
    category_id: int | None = Query(None, ge=1, description="Фильтр по категории"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Список растений с поиском, фильтром по категории и постраничной выдачей."""
    query = q.strip() if q else None
    items, total = plant_crud.get_plants(
        db, q=query or None, category_id=category_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{plant_id}", response_model=PlantDetail)
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    """Полная карточка растения."""
    plant = plant_crud.get_plant(db, plant_id)
    if plant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено"
        )
    return plant
