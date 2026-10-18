from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.plant import PlantListItem


def _check_not_in_future(value: date | None) -> date | None:
    # +1 день запаса: сервер может жить в другом часовом поясе, чем пользователь
    if value is not None and value > date.today() + timedelta(days=1):
        raise ValueError("Дата посадки не может быть в будущем")
    return value


def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class UserPlantCreate(BaseModel):
    plant_id: int = Field(ge=1)
    custom_name: str | None = Field(None, max_length=100)
    planted_at: date | None = None  # если не указана, подставляется сегодняшняя дата
    watering_interval_days: int | None = Field(None, ge=1, le=365)

    _name = field_validator("custom_name")(_clean_name)
    _date = field_validator("planted_at")(_check_not_in_future)


class UserPlantUpdate(BaseModel):
    """Все поля необязательные: меняются только переданные."""

    custom_name: str | None = Field(None, max_length=100)
    planted_at: date | None = None
    watering_interval_days: int | None = Field(None, ge=1, le=365)

    _name = field_validator("custom_name")(_clean_name)
    _date = field_validator("planted_at")(_check_not_in_future)

    @field_validator("planted_at", "watering_interval_days")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("Это поле нельзя очистить")
        return value


class UserPlantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_name: str | None = None
    planted_at: date | None = None
    last_watered_at: datetime | None = None
    watering_interval_days: int | None = None
    species: PlantListItem

    @computed_field
    @property
    def display_name(self) -> str:
        return self.custom_name or self.species.name

    @computed_field
    @property
    def next_watering_date(self) -> date | None:
        if not self.watering_interval_days:
            return None
        base = self.last_watered_at.date() if self.last_watered_at else self.planted_at
        if base is None:
            return None
        return base + timedelta(days=self.watering_interval_days)

    @computed_field
    @property
    def days_until_watering(self) -> int | None:
        """Сколько дней до полива. Отрицательное число: полив просрочен."""
        nxt = self.next_watering_date
        if nxt is None:
            return None
        return (nxt - date.today()).days
