from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud import plant as plant_crud
from app.database import get_db
from app.schemas.plant import CategoryResponse

router = APIRouter(prefix="/categories", tags=["Catalog"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """Список всех категорий растений."""
    return plant_crud.get_categories(db)
