"""
Ежедневное пополнение каталога растений из Perenual: новые виды, а не только обновление уже имеющихся.

Как это работает (подробности в PERENUAL.md):
  discover  постранично собирает список растений (30 штук на запрос) и запоминает их id
  pull      по списку скачивает карточки ухода (1 запрос на растение)
  add       создаёт в БД новые растения из скачанных карточек (без сети)
  daily     всё сразу: discover, pull до исчерпания лимита, add. Эту команду запускают каждый день
  names-export / names-apply   русские названия, описания и категории (файл names_ru.yaml)
  status    сколько запросов потрачено и что осталось

Общий счётчик запросов (scripts/cache/_usage.json) и кэш те же, что у import_perenual.py.

Запуск из папки backend (с активным venv):

  python scripts/perenual_bulk.py daily
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(BACKEND_DIR))

import yaml  # noqa: E402

import import_perenual as ip  # noqa: E402
from import_perenual import (  # noqa: E402
    AuthFailed, Budget, BudgetExhausted, CACHE_DIR, FetchFailed, MAX_FREE_ID, RateLimited,
    details_cache_path, explain_stop, fetch_json, get_api_key, lux_from_sunlight, parse_details,
    slugify, soil_to_ru, to_text,
)

POOL_FILE = CACHE_DIR / "candidates.json"
NAMES_FILE = SCRIPTS_DIR / "names_ru.yaml"
DEFAULT_FILTERS = {"indoor": "1"}          # только комнатные растения
STOP_AFTER_INACCESSIBLE_PAGES = 2          # сколько страниц подряд из id > 3000 считать концом доступного

CATEGORY_DEFAULT = "Комнатные растения"
CATEGORY_SUCCULENTS = "Суккуленты и кактусы"
CATEGORY_FLOWERING = "Цветущие растения"
CATEGORY_FERNS_PALMS = "Папоротники и пальмы"

# Эвристика категорий. Она грубая: неверную категорию исправляют в names_ru.yaml (поле category).
SUCCULENT_FAMILIES = {"cactaceae", "crassulaceae", "aizoaceae", "asphodelaceae"}
SUCCULENT_WORDS = ("cactus", "succulent", "aloe", "echeveria", "haworthia", "sedum", "agave", "jade plant")
FERN_FAMILIES = {"polypodiaceae", "pteridaceae", "aspleniaceae", "dryopteridaceae", "davalliaceae",
                 "blechnaceae", "nephrolepidaceae", "lomariopsidaceae", "dennstaedtiaceae"}
FLOWERING_FAMILIES = {"orchidaceae", "gesneriaceae", "begoniaceae", "geraniaceae", "primulaceae",
                      "amaryllidaceae", "bromeliaceae"}


# ---------------------------------------------------------------------------
# Список кандидатов (пул)
# ---------------------------------------------------------------------------
def load_pool() -> dict[str, Any]:
    try:
        pool = json.loads(POOL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pool = {}
    pool.setdefault("filters", {})   # прогресс по каждому набору фильтров
    pool.setdefault("plants", {})    # id -> краткие данные
    pool.setdefault("failed", {})    # id -> причина (чтобы не запрашивать повторно)
    return pool


def save_pool(pool: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    POOL_FILE.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")


def signature(filters: dict[str, str], query: str | None) -> str:
    parts = [f"{k}={v}" for k, v in sorted(filters.items())]
    if query:
        parts.append(f"q={query}")
    return "&".join(parts) or "all"


def first_name(value: Any) -> str | None:
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str) and v.strip()), None)
    return to_text(value)


def pool_entry(item: dict) -> dict[str, Any] | None:
    pid = item.get("id")
    if not isinstance(pid, int):
        return None
    return {
        "id": pid,
        "common_name": to_text(item.get("common_name")),
        "scientific_name": first_name(item.get("scientific_name")),
        "cultivar": bool(to_text(item.get("cultivar")) or to_text(item.get("variety"))),
    }


def discover(
    key: str, budget: Budget, pool: dict, filters: dict[str, str], query: str | None, max_pages: int | None,
    full_scan: bool = False,
) -> int:
    """Скачивает страницы списка, пока не кончатся страницы, бюджет или max_pages. Возвращает число страниц.

    full_scan: пройти все страницы заново, не останавливаясь на недоступных id. Уже скачанные страницы
    берутся из кэша без запросов, тратятся только ещё не скачанные.
    """
    sig = signature(filters, query)
    state = pool["filters"].setdefault(
        sig, {"next_page": 1, "last_page": None, "total": None, "done": False, "inaccessible_pages": 0}
    )
    if full_scan:
        state.update(done=False, next_page=1, inaccessible_pages=0)
    fetched = 0
    while not state["done"] and (max_pages is None or fetched < max_pages):
        page = state["next_page"]
        params: dict[str, Any] = {"page": page, **filters}
        if query:
            params["q"] = query
        cache = CACHE_DIR / f"list_{slugify(sig)}_p{page}.json"
        try:
            data, cached = fetch_json(
                cache, "species-list", params, key, budget,
                lambda d: isinstance(d, dict) and isinstance(d.get("data"), list),
            )
        except FetchFailed as e:
            print(f"  страница {page}: ошибка: {e}")
            save_pool(pool)
            break
        except (BudgetExhausted, RateLimited, AuthFailed):
            save_pool(pool)
            raise

        items = data["data"]
        usable = 0
        for item in items:
            entry = pool_entry(item)
            if entry and entry["id"] <= MAX_FREE_ID:
                pool["plants"].setdefault(str(entry["id"]), entry)
                usable += 1
        state.update(last_page=data.get("last_page"), total=data.get("total"), next_page=page + 1)
        state["inaccessible_pages"] = 0 if usable else state.get("inaccessible_pages", 0) + 1
        fetched += 1
        print(
            f"  страница {page} из {data.get('last_page', '?')}: растений {len(items)}, "
            f"доступно на бесплатном ключе {usable} ({'из кэша' if cached else 'из API'})"
        )
        if not items or (data.get("last_page") and page >= data["last_page"]):
            state["done"] = True
        elif not full_scan and state["inaccessible_pages"] >= STOP_AFTER_INACCESSIBLE_PAGES:
            state["done"] = True
            print(f"  дальше идут только растения с id больше {MAX_FREE_ID}: список собран")
        save_pool(pool)
    return fetched


def accessible_ids(pool: dict, include_cultivars: bool) -> list[int]:
    return sorted(
        int(pid) for pid, p in pool["plants"].items()
        if int(pid) <= MAX_FREE_ID and (include_cultivars or not p.get("cultivar"))
    )


def pending_ids(pool: dict, include_cultivars: bool) -> list[int]:
    return [
        pid for pid in accessible_ids(pool, include_cultivars)
        if not details_cache_path(pid).exists() and str(pid) not in pool["failed"]
    ]


def pull(key: str, budget: Budget, pool: dict, limit: int | None, include_cultivars: bool) -> int:
    pending = pending_ids(pool, include_cultivars)
    if limit is not None:
        pending = pending[:limit]
    if not pending:
        print("  все карточки из списка уже скачаны")
        return 0
    pulled = 0
    for index, pid in enumerate(pending, 1):
        entry = pool["plants"].get(str(pid), {})
        label = f"[{index}/{len(pending)}] id {pid} {entry.get('common_name') or ''}".strip()
        try:
            raw, cached = fetch_json(
                details_cache_path(pid), f"species/details/{pid}", {}, key, budget,
                lambda d: isinstance(d, dict) and d.get("id") is not None,
            )
        except FetchFailed as e:
            pool["failed"][str(pid)] = str(e)
            save_pool(pool)
            print(f"{label}: ошибка: {e}")
            continue
        except (BudgetExhausted, RateLimited, AuthFailed):
            save_pool(pool)
            raise
        pulled += 0 if cached else 1
        parsed = parse_details(raw)
        care = parsed["watering_min_days"] or parsed["sunlight"] or parsed["watering"]
        print(f"{label}: {'из кэша' if cached else 'загружено'}{'' if care else ' (данных ухода нет)'}")
    return pulled


# ---------------------------------------------------------------------------
# Русские названия
# ---------------------------------------------------------------------------
def load_names() -> dict[str, dict[str, Any]]:
    """names_ru.yaml: научное название (в нижнем регистре) -> запись."""
    try:
        data = yaml.safe_load(NAMES_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    plants = data.get("plants") or {}
    return {str(k).strip().lower(): v for k, v in plants.items() if isinstance(v, dict)}


def save_names(entries: dict[str, dict[str, Any]]) -> None:
    header = (
        "# Русские названия, описания и категории для растений из Perenual.\n"
        "# Ключ: научное название. Заполните name (обязательно для перевода), при желании category\n"
        "# (одна из: Комнатные растения, Суккуленты и кактусы, Цветущие растения, Папоротники и пальмы)\n"
        "# и description. Пустые поля игнорируются. После правки: python scripts/perenual_bulk.py names-apply\n"
    )
    body = yaml.safe_dump({"plants": entries}, allow_unicode=True, sort_keys=False, width=100)
    NAMES_FILE.write_text(header + body, encoding="utf-8")


def guess_category(raw: dict) -> str:
    family = (to_text(raw.get("family")) or "").lower()
    common = (to_text(raw.get("common_name")) or "").lower()
    if family in SUCCULENT_FAMILIES or any(w in common for w in SUCCULENT_WORDS):
        return CATEGORY_SUCCULENTS
    if family == "arecaceae" or "palm" in common or family in FERN_FAMILIES or "fern" in common:
        return CATEGORY_FERNS_PALMS
    if family in FLOWERING_FAMILIES:
        return CATEGORY_FLOWERING
    return CATEGORY_DEFAULT


def cached_raw(pid: int) -> dict | None:
    path = details_cache_path(pid)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------
def open_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{n}".format(
        u=os.getenv("DB_USER", "postgres"), p=os.getenv("DB_PASSWORD", "postgres"),
        h=os.getenv("DB_HOST", "127.0.0.1"), port=os.getenv("DB_PORT", "5433"),
        n=os.getenv("DB_NAME", "floraguide_db"),
    )
    return sessionmaker(bind=create_engine(url))()


def models():
    from app.models.plant import PlantCategory, PlantSpecies
    from app.models.user import User, UserPlant  # noqa: F401  (нужны для настройки связей моделей)

    missing = [c for c in ip.API_FIELDS if not hasattr(PlantSpecies, c)]
    if missing:
        print("В модели PlantSpecies нет колонок: " + ", ".join(missing) + ". Сначала примените миграцию.")
        raise SystemExit(1)
    return PlantCategory, PlantSpecies


def cmd_add(args: argparse.Namespace) -> int:
    PlantCategory, PlantSpecies = models()
    names = load_names()
    ids = [pid for pid in accessible_ids(load_pool(), args.include_cultivars) if details_cache_path(pid).exists()]
    if not ids:
        print("Нет скачанных карточек. Сначала выполните pull (или daily).")
        return 1

    added = 0
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    with open_session() as db:
        try:
            category_ids = {c.name: c.id for c in db.query(PlantCategory)}
            known_ext = {e for (e,) in db.query(PlantSpecies.external_id).filter(PlantSpecies.external_id.isnot(None))}
            known_sci = {s.lower() for (s,) in db.query(PlantSpecies.scientific_name).filter(PlantSpecies.scientific_name.isnot(None))}

            for pid in ids:
                raw = cached_raw(pid)
                if raw is None:
                    skip("повреждён файл кэша")
                    continue
                sci = first_name(raw.get("scientific_name"))
                if pid in known_ext or (sci and sci.lower() in known_sci):
                    skip("уже есть в базе")
                    continue
                parsed = parse_details(raw)
                if not (parsed["watering_min_days"] or parsed["sunlight"] or parsed["watering"]) and not args.allow_no_care:
                    skip("нет данных ухода (закрыты тарифом)")
                    continue
                entry = names.get((sci or "").lower(), {})
                ru_name = to_text(entry.get("name"))
                if args.only_named and not ru_name:
                    skip("нет русского названия в names_ru.yaml")
                    continue
                english = to_text(raw.get("common_name")) or sci
                if not (ru_name or english):
                    skip("нет названия")
                    continue

                category = to_text(entry.get("category")) or guess_category(raw)
                if category not in category_ids:
                    category = CATEGORY_DEFAULT
                if category not in category_ids:
                    print(f"В БД нет категории «{category}». Выполните сид (python -m app.seed).")
                    return 1

                species = PlantSpecies(
                    name=ru_name or english,
                    scientific_name=sci,
                    description=to_text(entry.get("description")),
                    optimal_lux=lux_from_sunlight(parsed["sunlight"]),
                    soil_composition=soil_to_ru(parsed["_soil"]),
                    category_id=category_ids[category],
                )
                for field in ip.API_FIELDS:
                    if parsed[field] is not None:
                        setattr(species, field, parsed[field])
                db.add(species)
                known_ext.add(pid)
                if sci:
                    known_sci.add(sci.lower())
                added += 1
                tag = "" if ru_name else "  (английское название)"
                print(f"[добавлено] {species.name} | {sci} | {category}{tag}")

            if args.dry_run:
                db.rollback()
                print("\nПробный запуск: в БД ничего не записано.")
            else:
                db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"\nДобавлено растений: {added}")
    for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"  пропущено ({reason}): {count}")
    return 0


def cmd_names_export(args: argparse.Namespace) -> int:
    # читаем файл заново, чтобы сохранить исходное написание ключей
    try:
        raw_file = yaml.safe_load(NAMES_FILE.read_text(encoding="utf-8")) or {}
        entries = dict(raw_file.get("plants") or {})
    except (OSError, yaml.YAMLError):
        entries = {}
    known = {k.strip().lower() for k in entries}
    added = 0
    for pid in accessible_ids(load_pool(), include_cultivars=True):
        raw = cached_raw(pid)
        if raw is None:
            continue
        sci = first_name(raw.get("scientific_name"))
        if not sci or sci.lower() in known:
            continue
        entries[sci] = {
            "english": to_text(raw.get("common_name")) or "",
            "name": "",
            "category": guess_category(raw),
            "description": "",
        }
        known.add(sci.lower())
        added += 1
    save_names(entries)
    empty = sum(1 for v in entries.values() if not (v or {}).get("name"))
    print(f"В {NAMES_FILE.name}: всего {len(entries)}, добавлено {added}, без русского названия {empty}.")
    return 0


def cmd_names_apply(args: argparse.Namespace) -> int:
    PlantCategory, PlantSpecies = models()
    names = {k: v for k, v in load_names().items() if to_text(v.get("name")) or to_text(v.get("description")) or to_text(v.get("category"))}
    if not names:
        print("В names_ru.yaml нет заполненных записей.")
        return 1
    changed = untouched = missing = 0
    with open_session() as db:
        try:
            category_ids = {c.name: c.id for c in db.query(PlantCategory)}
            for sci_lower, entry in names.items():
                rows = db.query(PlantSpecies).filter(PlantSpecies.scientific_name.ilike(sci_lower)).all()
                if not rows:
                    missing += 1
                    continue
                for species in rows:
                    updates: dict[str, Any] = {}
                    if to_text(entry.get("name")):
                        updates["name"] = to_text(entry["name"])
                    if to_text(entry.get("description")):
                        updates["description"] = to_text(entry["description"])
                    cat = to_text(entry.get("category"))
                    if cat in category_ids:
                        updates["category_id"] = category_ids[cat]
                    diff = {k: v for k, v in updates.items() if getattr(species, k) != v}
                    if not diff:
                        untouched += 1
                        continue
                    for k, v in diff.items():
                        setattr(species, k, v)
                    changed += 1
                    print(f"[обновлено] {species.scientific_name}: {', '.join(diff)}")
            if args.dry_run:
                db.rollback()
                print("\nПробный запуск: в БД ничего не записано.")
            else:
                db.commit()
        except Exception:
            db.rollback()
            raise
    print(f"\nОбновлено: {changed}, без изменений: {untouched}, нет в БД (пока): {missing}")
    return 0


# ---------------------------------------------------------------------------
# Команды работы с API
# ---------------------------------------------------------------------------
def parse_filters(pairs: list[str] | None, no_indoor: bool) -> dict[str, str]:
    filters = {} if no_indoor else dict(DEFAULT_FILTERS)
    for pair in pairs or []:
        if "=" not in pair:
            print(f"Фильтр должен быть вида ключ=значение, получено: {pair}")
            raise SystemExit(2)
        k, v = pair.split("=", 1)
        filters[k.strip()] = v.strip()
    return filters


def cmd_discover(args: argparse.Namespace) -> int:
    key, budget, pool = get_api_key(), Budget(args.max_requests), load_pool()
    filters = parse_filters(args.filter, args.no_indoor)
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}. Фильтры: {signature(filters, args.query)}")
    try:
        discover(key, budget, pool, filters, args.query, args.pages, full_scan=args.full_scan)
    except (BudgetExhausted, RateLimited, AuthFailed) as e:
        explain_stop(e, budget)
        return 1
    print_pool_summary(pool, args.include_cultivars)
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    pool = load_pool()
    if args.retry_failed:
        pool["failed"] = {}
    if not pool["plants"]:
        print("Список растений пуст. Сначала выполните discover (или daily).")
        return 1
    key, budget = get_api_key(), Budget(args.max_requests)
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}\n")
    try:
        pull(key, budget, pool, args.limit, args.include_cultivars)
    except (BudgetExhausted, RateLimited, AuthFailed) as e:
        explain_stop(e, budget)
    print_pool_summary(pool, args.include_cultivars)
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests}")
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    key, pool = get_api_key(), load_pool()
    budget = Budget(max(0, args.max_requests - args.reserve))
    filters = parse_filters(args.filter, args.no_indoor)
    print(f"Запросов потрачено сегодня: {budget.used}, лимит на этот запуск: {budget.max_requests}\n")

    stopped = False
    try:
        sig = signature(filters, args.query)
        if args.full_scan or not pool["filters"].get(sig, {}).get("done"):
            print("1. Список растений:")
            discover(key, budget, pool, filters, args.query, None, full_scan=args.full_scan)
        else:
            print("1. Список растений уже собран.")
        print("\n2. Карточки ухода:")
        pull(key, budget, pool, None, args.include_cultivars)
    except (BudgetExhausted, RateLimited, AuthFailed) as e:
        explain_stop(e, budget)
        stopped = True

    if not args.no_add:
        print("\n3. Запись новых растений в БД:")
        try:
            cmd_add(argparse.Namespace(
                dry_run=False, only_named=args.only_named, allow_no_care=False,
                include_cultivars=args.include_cultivars,
            ))
        except SystemExit:
            print("Запись в БД пропущена: скачанное сохранено в кэше, повторите add после исправления.")
        except Exception as e:  # база может быть недоступна, а скачанное всё равно сохранено в кэше
            print(f"Не удалось записать в БД ({e.__class__.__name__}). Данные в кэше, повторите: add")

    print()
    print_pool_summary(pool, args.include_cultivars)
    left = len(pending_ids(pool, args.include_cultivars))
    if left:
        per_day = max(1, args.max_requests - args.reserve)
        print(f"Осталось скачать карточек: {left}, это примерно {math.ceil(left / per_day)} дн. при {per_day} запросах в день.")
    elif stopped:
        print("Продолжите завтра той же командой.")
    else:
        print("Все доступные карточки скачаны. Дальше см. раздел «Что делать, когда список закончился» в PERENUAL.md.")
    print("Не забудьте пересчитать векторы: python scripts/reindex_embeddings.py")
    return 0


def print_pool_summary(pool: dict, include_cultivars: bool) -> None:
    ids = accessible_ids(pool, include_cultivars)
    cached = sum(1 for pid in ids if details_cache_path(pid).exists())
    print(f"\nВ списке доступных растений: {len(ids)}; карточек скачано: {cached}; осталось: {len(pending_ids(pool, include_cultivars))}"
          + (f"; с ошибкой: {len(pool['failed'])}" if pool["failed"] else ""))
    for sig, st in pool["filters"].items():
        progress = "собран" if st.get("done") else f"страница {st.get('next_page')} из {st.get('last_page') or '?'}"
        print(f"  фильтры [{sig}]: {progress}, всего в Perenual по этому фильтру: {st.get('total') or '?'}")


def cmd_status(args: argparse.Namespace) -> int:
    budget = Budget(args.max_requests)
    pool = load_pool()
    print(f"Запросов потрачено сегодня: {budget.used} из {budget.max_requests} (осталось {budget.left})")
    print_pool_summary(pool, args.include_cultivars)
    names = load_names()
    print(f"В names_ru.yaml записей: {len(names)}, с русским названием: {sum(1 for v in names.values() if to_text(v.get('name')))}")
    try:
        PlantCategory, PlantSpecies = models()
        with open_session() as db:
            total = db.query(PlantSpecies).count()
            from_api = db.query(PlantSpecies).filter(PlantSpecies.external_id.isnot(None)).count()
        print(f"В базе данных растений: {total}, из них из Perenual: {from_api}")
    except SystemExit:
        pass
    except Exception as e:
        print(f"База данных недоступна ({e.__class__.__name__})")
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ежедневное пополнение каталога из Perenual")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, budget: bool = True) -> None:
        p.add_argument("--include-cultivars", action="store_true", help="включать сорта (по умолчанию пропускаются)")
        if budget:
            p.add_argument("--max-requests", type=int, default=ip.DEFAULT_MAX_REQUESTS,
                           help=f"суточный лимит запросов (по умолчанию {ip.DEFAULT_MAX_REQUESTS})")

    def filters(p: argparse.ArgumentParser) -> None:
        p.add_argument("--filter", action="append", metavar="ключ=значение", help="фильтр species-list, например watering=average")
        p.add_argument("--no-indoor", action="store_true", help="не ограничиваться комнатными растениями")
        p.add_argument("--query", help="поиск по названию (параметр q)")
        p.add_argument("--full-scan", action="store_true",
                       help="пройти все страницы списка, не останавливаясь на недоступных id (скачанные страницы берутся из кэша)")

    p = sub.add_parser("discover", help="собрать список растений (тратит запросы)")
    common(p); filters(p)
    p.add_argument("--pages", type=int, help="сколько страниц скачать за этот запуск")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("pull", help="скачать карточки ухода (тратит запросы)")
    common(p)
    p.add_argument("--limit", type=int, help="сколько карточек скачать")
    p.add_argument("--retry-failed", action="store_true", help="повторить карточки, которые раньше завершились ошибкой")
    p.set_defaults(func=cmd_pull)

    p = sub.add_parser("add", help="создать новые растения в БД из скачанных карточек (без сети)")
    common(p, budget=False)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only-named", action="store_true", help="добавлять только растения с русским названием в names_ru.yaml")
    p.add_argument("--allow-no-care", action="store_true", help="добавлять и растения без данных ухода")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("daily", help="ежедневная команда: список, карточки до лимита и запись в БД")
    common(p); filters(p)
    p.add_argument("--reserve", type=int, default=0, help="сколько запросов оставить в запасе")
    p.add_argument("--no-add", action="store_true", help="только скачать, в БД не записывать")
    p.add_argument("--only-named", action="store_true", help="в БД добавлять только растения с русским названием")
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("names-export", help="добавить в names_ru.yaml заготовки для скачанных растений")
    common(p, budget=False)
    p.set_defaults(func=cmd_names_export)

    p = sub.add_parser("names-apply", help="применить names_ru.yaml к растениям в БД")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_names_apply)

    p = sub.add_parser("status", help="расход запросов и состояние")
    common(p)
    p.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
