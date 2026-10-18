from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_url: str


class PlantListItem(BaseModel):
    """Краткая карточка растения для списков и поиска."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scientific_name: str | None = None
    description: str | None = None
    category: CategoryResponse


class PlantDetail(PlantListItem):
    """Полная карточка растения. Поле embedding намеренно не включено."""

    optimal_lux: int | None = None
    optimal_humidity: int | None = None
    soil_composition: str | None = None
    growth_duration_days: int | None = None


class PlantListResponse(BaseModel):
    items: list[PlantListItem]
    total: int
    limit: int
    offset: int
