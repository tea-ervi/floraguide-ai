"""
Импорт данных ухода из Perenual (perenual.com) в вашу базу данных.

Скрипт разделён на команды, чтобы лимит бесплатного ключа (около 100 запросов в сутки) не мешал отладке:

  search   запросы к API: ищет кандидатов для каждого растения из plants_list.py.
           Ответы сохраняются в scripts/cache/, повторный запуск ничего не тратит.
  details  запросы к API: загружает карточки ухода для растений с указанным perenual_id.
  load     БЕЗ СЕТИ: читает кэш и записывает данные в БД.
  status   показывает, сколько запросов потрачено сегодня и что уже загружено.

Запуск из папки backend (с активным venv):

  python scripts/import_perenual.py search
  python scripts/import_perenual.py details
  python scripts/import_perenual.py load --dry-run
  python scripts/import_perenual.py load

Ключ берётся из backend/.env:  PERENUAL_API_KEY=...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Callable

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent
CACHE_DIR = SCRIPTS_DIR / "cache"
USAGE_FILE = CACHE_DIR / "_usage.json"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402
from plants_list import PLANTS  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

# Консоль Windows может быть в старой кодировке: не даём скрипту падать на русских буквах
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://perenual.com/api/v2"
MAX_FREE_ID = 3000            # бесплатный ключ видит только растения с id 1-3000
DEFAULT_MAX_REQUESTS = 90     # запас до лимита в 100 запросов в сутки
PAUSE_SECONDS = 1.5           # пауза между запросами к API
RETRY_PAUSE_SECONDS = 3.0
SHOWN_CANDIDATES = 10

# ---------------------------------------------------------------------------
# Допущения для значений, которых нет в API. Используются, только если поле в БД пустое.
# ---------------------------------------------------------------------------
LUX_BY_SUNLIGHT = {
    "deep shade": 500,
    "full shade": 1000,
    "part shade": 2000,
    "filtered shade": 2000,
    "part sun/part shade": 3000,
    "part sun": 3000,
    "sun-part shade": 4000,
    "full sun": 6000,
}

SOIL_RU = {
    "well-drained": "хорошо дренированный",
    "rocky": "каменистый",
    "dry": "сухой",
    "loam": "суглинистый",
    "loamy": "суглинистый",
    "sandy": "песчаный",
    "clay": "глинистый",
    "moist": "влажный",
    "acidic": "кислый",
    "alkaline": "щелочной",
    "neutral": "нейтральный",
    "peat": "торфяной",
    "humus-rich": "богатый перегноем",
    "chalky": "известковый",
}

# Поля, которые перезаписываются данными API (если API вернул значение)
API_FIELDS = [
    "external_id",
    "watering",
    "watering_min_days",
    "watering_max_days",
    "sunlight",
    "indoor",
    "poisonous_to_pets",
    "care_level",
    "image_url",
    "image_license",
]
# Поля, которые заполняются только если пусты (ручные данные не трогаем)
FILL_IF_EMPTY = ["optimal_lux", "soil_composition"]


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------
class BudgetExhausted(Exception):
    """Дневной бюджет запросов исчерпан."""


class RateLimited(Exception):
    """Сервер ответил, что лимит исчерпан (HTTP 429)."""


class AuthFailed(Exception):
    """Ключ не принят."""


class FetchFailed(Exception):
    """Не удалось получить данные для одного растения (остальные продолжаем)."""


class NetworkError(Exception):
    pass


# ---------------------------------------------------------------------------
# Работа с API и кэшем
# ---------------------------------------------------------------------------
class Budget:
    """Считает запросы за сегодня (счётчик хранится в файле и переживает перезапуск скрипта)."""

    def __init__(self, max_requests: int):
        self.max_requests = max_requests
        self.used = self._read_used()
        self._last_call = 0.0

    @staticmethod
    def _read_used() -> int:
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            return int(data.get(date.today().isoformat(), 0))
        except (OSError, ValueError):
            return 0

    def _save(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps({date.today().isoformat(): self.used}), encoding="utf-8")

    @property
    def left(self) -> int:
        return max(0, self.max_requests - self.used)

    def before_request(self) -> None:
        if self.used >= self.max_requests:
            raise BudgetExhausted
        wait = PAUSE_SECONDS - (time.monotonic() - self._last_call)
        if wait > 0 and self._last_call:
            time.sleep(wait)

    def after_request(self) -> None:
        self.used += 1
        self._last_call = time.monotonic()
        self._save()


def get_api_key() -> str:
    key = os.getenv("PERENUAL_API_KEY", "").strip()
    if not key:
        print("Нет ключа. Добавьте в backend/.env строку: PERENUAL_API_KEY=ваш_ключ")
        raise SystemExit(1)
    return key


def api_get(path: str, params: dict[str, Any], key: str) -> tuple[int, Any]:
    """GET-запрос к Perenual. Адрес с ключом никогда не печатается."""
    query = urllib.parse.urlencode({**params, "key": key})
    request = urllib.request.Request(
        f"{BASE_URL}/{path}?{query}",
        headers={"Accept": "application/json", "User-Agent": "floraguide-import/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NetworkError(str(getattr(e, "reason", e))) from None
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        data = None
    return status, data


def fetch_json(
    cache_file: Path,
    path: str,
    params: dict[str, Any],
    key: str,
    budget: Budget,
    is_valid: Callable[[Any], bool],
) -> tuple[Any, bool]:
    """Возвращает (данные, взято_из_кэша). Кэш проверяется первым: тогда запрос не тратится."""
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8")), True

    for attempt in (1, 2):
        budget.before_request()
        try:
            status, data = api_get(path, params, key)
        except NetworkError as e:
            budget.after_request()
            if attempt == 2:
                raise FetchFailed(f"нет связи с сервером ({e})") from None
            time.sleep(RETRY_PAUSE_SECONDS)
            continue
        budget.after_request()

        if status == 429:
            raise RateLimited
        if status in (401, 403):
            raise AuthFailed(status)
        if status == 404:
            raise FetchFailed("не найдено (404)")
        if status >= 500:
            if attempt == 2:
                raise FetchFailed(f"ошибка сервера ({status})")
            time.sleep(RETRY_PAUSE_SECONDS)
            continue
        if status != 200 or data is None:
            raise FetchFailed(f"неожиданный ответ (код {status})")

        if not is_valid(data):
            text = json.dumps(data, ensure_ascii=False)[:200]
            if "limit" in text.lower() or "too many" in text.lower():
                raise RateLimited
            raise FetchFailed(f"неожиданное содержимое ответа: {text}")

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data, False

    raise FetchFailed("не удалось получить ответ")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "query"


def search_cache_path(query: str) -> Path:
    return CACHE_DIR / f"search_{slugify(query)}.json"


def details_cache_path(perenual_id: int) -> Path:
    return CACHE_DIR / f"details_{perenual_id}.json"


# ---------------------------------------------------------------------------
# Разбор данных
# ---------------------------------------------------------------------------
def is_locked(value: Any) -> bool:
    """На бесплатном тарифе закрытые поля приходят текстом про апгрейд вместо значения."""
    return isinstance(value, str) and (
        "upgrade plans" in value.lower() or "subscription-api-pricing" in value.lower()
    )


def clean(value: Any) -> Any:
    return None if value is None or is_locked(value) else value


def to_bool(value: Any) -> bool | None:
    value = clean(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return None


def to_text(value: Any) -> str | None:
    value = clean(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def parse_benchmark(benchmark: Any) -> tuple[int | None, int | None]:
    """{'value': '5-7', 'unit': 'days'} -> (5, 7)."""
    benchmark = clean(benchmark)
    if not isinstance(benchmark, dict):
        return None, None
    value = clean(benchmark.get("value"))
    if value is None:
        return None, None
    numbers = [int(n) for n in re.findall(r"\d+", str(value))]
    if not numbers:
        return None, None
    low, high = numbers[0], numbers[1] if len(numbers) > 1 else numbers[0]
    if low > high:
        low, high = high, low
    unit = str(clean(benchmark.get("unit")) or "days").lower()
    factor = 7 if "week" in unit else 1
    low, high = low * factor, high * factor
    if not 1 <= low <= high <= 365:
        return None, None
    return low, high


def norm_tag(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").strip().lower())


def parse_sunlight(value: Any) -> list[str] | None:
    value = clean(value)
    if isinstance(value, list):
        tags = [norm_tag(str(x)) for x in value if clean(x) and str(x).strip()]
        return tags or None
    return None


def parse_image(image: Any) -> tuple[str | None, str | None]:
    image = clean(image)
    if not isinstance(image, dict):
        return None, None
    url = None
    for field in ("regular_url", "original_url", "medium_url", "small_url"):
        candidate = to_text(image.get(field))
        if candidate:
            url = candidate
            break
    license_name = to_text(image.get("license_name"))
    license_url = to_text(image.get("license_url"))
    if license_name and license_url:
        license_text = f"{license_name} ({license_url})"
    else:
        license_text = license_name or license_url
    return url, license_text


def norm_name(value: str) -> str:
    value = value.lower().replace(" spp.", "").replace(" spp", "")
    return re.sub(r"\s+", " ", value).strip()


def accepted_names(plant: dict) -> set[str]:
    return {norm_name(plant["scientific_name"])} | {norm_name(q) for q in plant["search"]}


def perenual_names(raw: dict) -> list[str]:
    names: list[str] = []
    for field in ("scientific_name", "other_name"):
        value = raw.get(field)
        if isinstance(value, list):
            names += [str(x) for x in value if clean(x)]
        elif isinstance(value, str) and not is_locked(value):
            names.append(value)
    common = raw.get("common_name")
    if isinstance(common, str):
        names.append(common)
    return [n for n in (norm_name(x) for x in names) if n]


def names_match(plant: dict, raw: dict) -> bool:
    """Похоже ли растение из Perenual на растение из нашего списка (защита от неверного id)."""
    accepted = accepted_names(plant)
    return any(n == a or n.startswith(a + " ") for n in perenual_names(raw) for a in accepted)


def parse_details(raw: dict) -> dict[str, Any]:
    low, high = parse_benchmark(raw.get("watering_general_benchmark"))
    image_url, image_license = parse_image(raw.get("default_image"))
    soil = clean(raw.get("soil"))
    return {
        "external_id": raw.get("id") if isinstance(raw.get("id"), int) else None,
        "watering": to_text(raw.get("watering")),
        "watering_min_days": low,
        "watering_max_days": high,
        "sunlight": parse_sunlight(raw.get("sunlight")),
        "indoor": to_bool(raw.get("indoor")),
        "poisonous_to_pets": to_bool(raw.get("poisonous_to_pets")),
        "care_level": to_text(raw.get("care_level")),
        "image_url": image_url,
        "image_license": image_license,
        "_soil": [norm_tag(str(x)) for x in soil] if isinstance(soil, list) else [],
    }


def lux_from_sunlight(tags: list[str] | None) -> int | None:
    values = [LUX_BY_SUNLIGHT[t] for t in (tags or []) if t in LUX_BY_SUNLIGHT]
    if not values:
        return None
    return int(round(sum(values) / len(values) / 500) * 500)


def soil_to_ru(tags: list[str]) -> str | None:
    translated = [SOIL_RU[t] for t in tags if t in SOIL_RU]
    if not translated:
        return None
    text = ", ".join(translated)
    return text[0].upper() + text[1:]


def empty_fields(raw: dict) -> list[str]:
    """Ключевые поля, которые пришли пустыми или закрытыми тарифом."""
    tracked = [
        "watering",
        "watering_general_benchmark",
        "sunlight",
        "soil",
        "poisonous_to_pets",
        "indoor",
        "care_level",
        "default_image",
    ]
    return [f for f in tracked if clean(raw.get(f)) in (None, "", [])]


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------
def select_plants(only: str | None) -> list[dict]:
    if not only:
        return PLANTS
    needle = only.lower()
    found = [
        p
        for p in PLANTS
        if needle in p["scientific_name"].lower()
        or needle in p["name_ru"].lower()
        or any(needle in q for q in p["search"])
    ]
    if not found:
        print(f"По фильтру «{only}» ничего не найдено в plants_list.py")
    return found


def short(value: Any, limit: int = 60) -> str:
    text = "—" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def explain_stop(error: Exception, budget: Budget) -> None:
    if isinstance(error, BudgetExhausted):
        print(f"\nДневной бюджет исчерпан ({budget.used} из {budget.max_requests}). Продолжите завтра, кэш сохранён.")
    elif isinstance(error, RateLimited):
        print("\nСервер сообщил, что лимит запросов исчерпан (429). Продолжите завтра, кэш сохранён.")
    elif isinstance(error, AuthFailed):
        print("\nКлюч не принят сервером. Проверьте PERENUAL_API_KEY в backend/.env.")


# ---------------------------------------------------------------------------
# Команда search
# ---------------------------------------------------------------------------
def candidate_line(plant: dict, cand: dict) -> str:
    sci = cand.get("scientific_name")
    sci_text = "; ".join(str(x) for x in sci) if isinstance(sci, list) else str(sci or "—")
    cid = cand.get("id")
    marks = []
    if names_match(plant, cand):
        marks.append("<-- похоже на нужное")
    if isinstance(cid, int) and cid > MAX_FREE_ID:
        marks.append(f"[id > {MAX_FREE_ID}: недоступно на бесплатном ключе]")
    return f"    {str(cid):>5}  {cand.get('common_name') or '—'} | {sci_text}  {' '.join(marks)}".rstrip()


def cmd_search(args: argparse.Namespace) -> int:
    key = get_api_key()
    budget = Budget(args.max_requests)
    plants = select_plants(args.only)
    without_candidates: list[str] = []

    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}\n")

    for index, plant in enumerate(plants, 1):
        current_id = plant["perenual_id"]
        id_note = f"perenual_id: {current_id}" if current_id else "perenual_id: не указан"
        print(f"[{index}/{len(plants)}] {plant['scientific_name']} ({plant['name_ru']})  {id_note}")

        queries = [args.query] if args.query else plant["search"]
        found_any = False
        for query in queries:
            try:
                data, cached = fetch_json(
                    search_cache_path(query),
                    "species-list",
                    {"q": query},
                    key,
                    budget,
                    lambda d: isinstance(d, dict) and isinstance(d.get("data"), list),
                )
            except FetchFailed as e:
                print(f"  запрос «{query}»: ошибка: {e}")
                continue
            except (BudgetExhausted, RateLimited, AuthFailed) as e:
                explain_stop(e, budget)
                return 1

            candidates = data["data"]
            total = data.get("total", len(candidates))
            source = "из кэша" if cached else "из API"
            print(f"  запрос «{query}»: найдено {total} ({source})")
            for cand in candidates[:SHOWN_CANDIDATES]:
                print(candidate_line(plant, cand))
            if len(candidates) > SHOWN_CANDIDATES:
                print(f"    ... и ещё {len(candidates) - SHOWN_CANDIDATES} на этой странице")

            if candidates:
                found_any = True
                if not args.all_queries:
                    break  # кандидаты есть, лишние запросы не тратим
        if not found_any:
            without_candidates.append(plant["scientific_name"])
            print("  кандидатов нет: попробуйте другой запрос (--query \"...\") или внесите данные вручную")
        print()

    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}")
    if without_candidates:
        print("Без кандидатов: " + ", ".join(without_candidates))
    print(
        "\nСледующий шаг: впишите подходящие id в поле perenual_id в scripts/plants_list.py "
        "и запустите команду details."
    )
    return 0


# ---------------------------------------------------------------------------
# Команда details
# ---------------------------------------------------------------------------
def print_preview(plant: dict, raw: dict) -> None:
    parsed = parse_details(raw)
    days = (
        f"{parsed['watering_min_days']}-{parsed['watering_max_days']} дн."
        if parsed["watering_min_days"]
        else "—"
    )
    print(
        f"      полив: {parsed['watering'] or '—'} ({days}); свет: {parsed['sunlight'] or '—'}; "
        f"ядовито для питомцев: {parsed['poisonous_to_pets'] if parsed['poisonous_to_pets'] is not None else '—'}"
    )
    missing = empty_fields(raw)
    if missing:
        print(f"      пусто или закрыто тарифом: {', '.join(missing)}")
    if not names_match(plant, raw):
        names = ", ".join(perenual_names(raw)[:3]) or "—"
        print(f"      [!] название в Perenual ({names}) не похоже на ожидаемое: проверьте perenual_id")


def cmd_details(args: argparse.Namespace) -> int:
    plants = [p for p in select_plants(args.only) if p["perenual_id"] is not None]
    if not plants:
        print("Нет растений с указанным perenual_id. Сначала выполните search и впишите id в plants_list.py.")
        return 1

    key = get_api_key()
    budget = Budget(args.max_requests)
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}\n")

    done = skipped = failed = 0
    for index, plant in enumerate(plants, 1):
        pid = plant["perenual_id"]
        label = f"[{index}/{len(plants)}] {plant['scientific_name']} (id {pid})"
        if not 1 <= pid <= MAX_FREE_ID:
            print(f"{label}: пропущено, id вне диапазона 1-{MAX_FREE_ID} бесплатного ключа")
            skipped += 1
            continue
        try:
            raw, cached = fetch_json(
                details_cache_path(pid),
                f"species/details/{pid}",
                {},
                key,
                budget,
                lambda d: isinstance(d, dict) and d.get("id") is not None,
            )
        except FetchFailed as e:
            print(f"{label}: ошибка: {e}")
            failed += 1
            continue
        except (BudgetExhausted, RateLimited, AuthFailed) as e:
            explain_stop(e, budget)
            break

        print(f"{label}: {'из кэша' if cached else 'загружено'}")
        print_preview(plant, raw)
        done += 1

    left = [p for p in plants if not details_cache_path(p["perenual_id"]).exists() and 1 <= p["perenual_id"] <= MAX_FREE_ID]
    print(f"\nГотово: {done}, пропущено: {skipped}, с ошибкой: {failed}, ещё не загружено: {len(left)}")
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}")
    if not left:
        print("Следующий шаг: python scripts/import_perenual.py load --dry-run")
    return 0 if not failed else 1


# ---------------------------------------------------------------------------
# Команда load
# ---------------------------------------------------------------------------
def cmd_load(args: argparse.Namespace) -> int:
    plants = [p for p in select_plants(args.only) if p["perenual_id"] is not None]
    if not plants:
        print("Нет растений с указанным perenual_id.")
        return 1

    # Импорты приложения здесь, чтобы search и details работали без базы данных
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.plant import PlantSpecies
    from app.models.user import User, UserPlant  # noqa: F401  (нужны для настройки связей моделей)

    missing_columns = [c for c in API_FIELDS if not hasattr(PlantSpecies, c)]
    if missing_columns:
        print("В модели PlantSpecies нет колонок: " + ", ".join(missing_columns))
        print("Сначала выполните этап 2: обновите models/plant.py и примените миграцию.")
        return 1

    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{n}".format(
        u=os.getenv("DB_USER", "postgres"),
        p=os.getenv("DB_PASSWORD", "postgres"),
        h=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5433"),
        n=os.getenv("DB_NAME", "floraguide_db"),
    )
    Session = sessionmaker(bind=create_engine(url))

    updated = unchanged = skipped = 0
    with Session() as db:
        try:
            for plant in plants:
                pid = plant["perenual_id"]
                name = plant["scientific_name"]
                cache_file = details_cache_path(pid)
                if not cache_file.exists():
                    print(f"[пропуск] {name}: нет файла кэша (выполните details)")
                    skipped += 1
                    continue

                raw = json.loads(cache_file.read_text(encoding="utf-8"))
                if not names_match(plant, raw) and not args.allow_mismatch:
                    print(f"[пропуск] {name}: название в Perenual не совпадает, проверьте perenual_id (или --allow-mismatch)")
                    skipped += 1
                    continue

                species = db.query(PlantSpecies).filter(PlantSpecies.external_id == pid).first()
                if species is None:
                    species = db.query(PlantSpecies).filter(PlantSpecies.scientific_name == name).first()
                if species is None:
                    print(f"[пропуск] {name}: растения нет в БД (добавьте его в seed.py и запустите сид)")
                    skipped += 1
                    continue
                clash = (
                    db.query(PlantSpecies)
                    .filter(PlantSpecies.external_id == pid, PlantSpecies.id != species.id)
                    .first()
                )
                if clash is not None:
                    print(f"[пропуск] {name}: id {pid} уже занят растением «{clash.scientific_name}»")
                    skipped += 1
                    continue

                parsed = parse_details(raw)
                changes: list[tuple[str, Any, Any]] = []

                for field in API_FIELDS:
                    new = parsed[field]
                    if new is None:
                        continue  # API ничего не дал: ручное значение сохраняется
                    old = getattr(species, field)
                    if old != new:
                        changes.append((field, old, new))

                fallback = {
                    "optimal_lux": lux_from_sunlight(parsed["sunlight"]),
                    "soil_composition": soil_to_ru(parsed["_soil"]),
                }
                for field in FILL_IF_EMPTY:
                    if getattr(species, field) in (None, "") and fallback[field] is not None:
                        changes.append((field, None, fallback[field]))

                if not changes:
                    print(f"[без изменений] {name}")
                    unchanged += 1
                    continue

                print(f"[обновлено] {name}: {len(changes)} полей")
                for field, old, new in changes:
                    print(f"      {field}: {short(old)} -> {short(new)}")
                    if not args.dry_run:
                        setattr(species, field, new)
                updated += 1

            if args.dry_run:
                db.rollback()
                print("\nПробный запуск: в БД ничего не записано.")
            else:
                db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"\nОбновлено: {updated}, без изменений: {unchanged}, пропущено: {skipped}")
    return 0


# ---------------------------------------------------------------------------
# Команда status
# ---------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    budget = Budget(args.max_requests)
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests} (осталось {budget.left})\n")
    with_id = 0
    for plant in PLANTS:
        pid = plant["perenual_id"]
        if pid is None:
            state = "id не указан"
        else:
            with_id += 1
            state = "карточка в кэше" if details_cache_path(pid).exists() else "карточка не загружена"
            if not 1 <= pid <= MAX_FREE_ID:
                state += f" (id вне диапазона 1-{MAX_FREE_ID})"
        print(f"  {plant['scientific_name']:<28} {str(pid or '—'):>5}  {state}")
    print(f"\nРастений: {len(PLANTS)}, с указанным id: {with_id}")
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Импорт данных ухода из Perenual")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, with_budget: bool = True) -> None:
        p.add_argument("--only", help="обработать только растения, в названии которых есть эта строка")
        if with_budget:
            p.add_argument(
                "--max-requests",
                type=int,
                default=DEFAULT_MAX_REQUESTS,
                help=f"лимит запросов за сутки (по умолчанию {DEFAULT_MAX_REQUESTS})",
            )

    p_search = sub.add_parser("search", help="найти кандидатов в Perenual (тратит запросы)")
    common(p_search)
    p_search.add_argument("--query", help="свой поисковый запрос вместо списка из plants_list.py")
    p_search.add_argument("--all-queries", action="store_true", help="выполнить все запросы, даже если кандидаты уже найдены")
    p_search.set_defaults(func=cmd_search)

    p_details = sub.add_parser("details", help="загрузить карточки ухода (тратит запросы)")
    common(p_details)
    p_details.set_defaults(func=cmd_details)

    p_load = sub.add_parser("load", help="записать данные из кэша в БД (без сети)")
    common(p_load, with_budget=False)
    p_load.add_argument("--dry-run", action="store_true", help="показать изменения, но не записывать")
    p_load.add_argument("--allow-mismatch", action="store_true", help="загружать, даже если название в Perenual не совпало")
    p_load.set_defaults(func=cmd_load)

    p_status = sub.add_parser("status", help="показать расход запросов и состояние кэша")
    common(p_status)
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
