"""Контекст растения: факты, которые система знает о нём без вопросов пользователю."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .schedule import compute_schedule, season_of

# Факты, на которые можно ссылаться в правилах как ctx:<имя>
FACT_NAMES: dict[str, str] = {
    "recently_watered": "полив был недавно",
    "watering_due": "пора поливать",
    "watering_overdue": "полив просрочен",
    "watering_on_time": "полив идёт по графику",
    "interval_below_recommended": "поливают чаще, чем рекомендуется для вида",
    "winter": "зима",
    "summer": "лето",
    "growing_season": "сезон активного роста",
    "heating_season": "отопительный сезон",
    "species_low_light": "вид любит тень",
    "species_bright_light": "вид любит яркий свет",
    "species_humid": "вид любит влажный воздух",
    "is_succulent": "суккулент или кактус",
    "recently_planted": "растение посажено недавно",
}

SEASON_RU = {"winter": "зима", "spring": "весна", "summer": "лето", "autumn": "осень"}
SHADE_TAGS = {"full shade", "part shade", "filtered shade", "deep shade"}


@dataclass
class PlantContext:
    plant: str                                       # название для показа
    facts: dict[str, bool | None] = field(default_factory=dict)   # None: неизвестно
    values: dict[str, Any] = field(default_factory=dict)          # значения для подстановки в объяснения


def _to_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def make_context(
    settings: dict[str, Any],
    *,
    plant_name: str,
    category_name: str | None = None,
    interval_days: int | None = None,
    min_days: int | None = None,
    max_days: int | None = None,
    optimal_lux: int | None = None,
    optimal_humidity: int | None = None,
    sunlight: list[str] | None = None,
    last_watered: date | datetime | None = None,
    planted_at: date | datetime | None = None,
    today: date | None = None,
) -> PlantContext:
    today = today or date.today()
    th = settings["thresholds"]
    last_watered = _to_date(last_watered)
    planted_at = _to_date(planted_at)

    category = (category_name or "").lower()
    is_succulent = "суккул" in category or "кактус" in category

    sched = compute_schedule(
        settings,
        interval_days=interval_days,
        min_days=min_days,
        max_days=max_days,
        is_succulent=is_succulent,
        last_watered=last_watered,
        planted_at=planted_at,
        today=today,
    )
    season = sched.season
    ds, iv = sched.days_since, sched.interval

    facts: dict[str, bool | None] = {name: None for name in FACT_NAMES}
    if ds is not None:
        facts["recently_watered"] = ds <= th["recently_watered"] * iv
        facts["watering_due"] = ds >= th["watering_due"] * iv
        facts["watering_overdue"] = ds >= th["watering_overdue"] * iv
        facts["watering_on_time"] = th["on_time_min"] * iv < ds < th["on_time_max"] * iv
    if min_days:
        facts["interval_below_recommended"] = sched.base_interval < min_days

    facts["winter"] = season == "winter"
    facts["summer"] = season == "summer"
    facts["growing_season"] = today.month in settings["growing_months"]
    facts["heating_season"] = today.month in settings["heating_months"]
    facts["is_succulent"] = is_succulent

    tags = {t.strip().lower().replace("_", " ") for t in (sunlight or [])}
    if tags:
        facts["species_low_light"] = tags <= SHADE_TAGS
        facts["species_bright_light"] = "full sun" in tags
    elif optimal_lux is not None:
        facts["species_low_light"] = optimal_lux <= th["low_light_lux"]
        facts["species_bright_light"] = optimal_lux >= th["bright_light_lux"]
    if optimal_humidity is not None:
        facts["species_humid"] = optimal_humidity >= th["humid_species_percent"]
    if planted_at is not None:
        facts["recently_planted"] = (today - planted_at).days <= th["recently_planted_days"]

    if min_days and max_days and min_days != max_days:
        recommended = f"{min_days}–{max_days} дн."
    elif min_days or max_days:
        recommended = f"{min_days or max_days} дн."
    else:
        recommended = "нет данных"

    values = {
        "plant": plant_name,
        "days_since": ds if ds is not None else "—",
        "interval": iv,
        "base_interval": sched.base_interval,
        "season": SEASON_RU[season],
        "recommended": recommended,
        "next_date": sched.next_date,
        "days_until": sched.days_until,
    }
    return PlantContext(plant=plant_name, facts=facts, values=values)


def build_context(user_plant: Any, settings: dict[str, Any], today: date | None = None) -> PlantContext:
    """Контекст из объекта UserPlant (вид и категория должны быть загружены)."""
    species = user_plant.species
    category = getattr(getattr(species, "category", None), "name", None)
    return make_context(
        settings,
        plant_name=getattr(user_plant, "custom_name", None) or species.name,
        category_name=category,
        interval_days=user_plant.watering_interval_days,
        min_days=getattr(species, "watering_min_days", None),
        max_days=getattr(species, "watering_max_days", None),
        optimal_lux=getattr(species, "optimal_lux", None),
        optimal_humidity=getattr(species, "optimal_humidity", None),
        sunlight=getattr(species, "sunlight", None),
        last_watered=user_plant.last_watered_at,
        planted_at=user_plant.planted_at,
        today=today,
    )
