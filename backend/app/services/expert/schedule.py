"""Расчёт расписания полива с учётом сезона."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

FALLBACK_INTERVAL_DAYS = 7


def suggested_interval(min_days: int | None, max_days: int | None) -> int:
    """Базовый интервал: середина диапазона вида; одна граница даёт её саму; данных нет, значит 7."""
    values = [v for v in (min_days, max_days) if v]
    if not values:
        return FALLBACK_INTERVAL_DAYS
    return max(1, min(365, sum(values) // len(values)))


def season_of(settings: dict[str, Any], today: date) -> str:
    for season, months in settings["seasons"].items():
        if today.month in months:
            return season
    return "summer"


@dataclass
class Schedule:
    base_interval: int           # интервал без учёта сезона
    factor: float                # сезонный коэффициент
    interval: int                # итоговый интервал с учётом сезона
    season: str
    last_date: date | None       # дата последнего полива (или посадки, если не поливали)
    next_date: date | None
    days_since: int | None
    days_until: int | None       # отрицательное число: полив просрочен


def compute_schedule(
    settings: dict[str, Any],
    *,
    interval_days: int | None,
    min_days: int | None,
    max_days: int | None,
    is_succulent: bool,
    last_watered: date | None,
    planted_at: date | None,
    today: date,
) -> Schedule:
    base = interval_days or suggested_interval(min_days, max_days)
    season = season_of(settings, today)
    factors = settings["interval_factors"][season]
    factor = float(factors["succulent" if is_succulent else "default"])
    interval = max(1, round(base * factor))

    last = last_watered or planted_at
    if last is None:
        return Schedule(base, factor, interval, season, None, None, None, None)
    next_date = last + timedelta(days=interval)
    return Schedule(
        base_interval=base,
        factor=factor,
        interval=interval,
        season=season,
        last_date=last,
        next_date=next_date,
        days_since=(today - last).days,
        days_until=(next_date - today).days,
    )
