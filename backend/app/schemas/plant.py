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
    """Полная карточка растения со всеми параметрами ухода и условиями."""

    optimal_lux: int | None = None
    optimal_humidity: int | None = None
    soil_composition: str | None = None
    growth_duration_days: int | None = None
    external_id: int | None = None
    watering: str | None = None
    watering_min_days: int | None = None
    watering_max_days: int | None = None
    sunlight: list[str] | None = None
    indoor: bool | None = None
    poisonous_to_pets: bool | None = None
    care_level: str | None = None
    image_url: str | None = None
    image_license: str | None = None


class PlantListResponse(BaseModel):
    items: list[PlantListItem]
    total: int
    limit: int
    offset: int