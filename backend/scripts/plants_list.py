"""
Список растений для импорта данных ухода из Perenual.

Это словарь, который ведёте вы сами:
  - scientific_name: ключ. Должен ТОЧНО совпадать с plant_species.scientific_name в вашей БД
                     (так импорт дополняет существующие растения, а не создаёт дубликаты).
  - name_ru:         русское название (из Perenual не берётся, там названия английские).
  - category:        название категории, как в seed.py.
  - perenual_id:     id растения в Perenual. Пока None: его вы впишете после шага «search»,
                     когда сверите кандидатов. Бесплатный ключ видит только id от 1 до 3000.
  - search:          английские и латинские запросы для поиска в Perenual. У Perenual
                     научные названия бывают другими (например, Sansevieria вместо Dracaena),
                     поэтому запросов несколько.

Проверка списка:  python scripts/plants_list.py   (из папки backend)
"""

KNOWN_CATEGORIES = {
    "Комнатные растения",
    "Суккуленты и кактусы",
    "Цветущие растения",
    "Папоротники и пальмы",
}

PLANTS: list[dict] = [
    # --- Комнатные растения ---
    # {"scientific_name": "Monstera deliciosa", "name_ru": "Монстера Делициоза", "category": "Комнатные растения", "perenual_id": None, "search": ["monstera deliciosa"]},
    # {"scientific_name": "Zamioculcas zamiifolia", "name_ru": "Замиокулькас", "category": "Комнатные растения", "perenual_id": None, "search": ["zamioculcas zamiifolia", "zz plant"]},
    {"scientific_name": "Epipremnum aureum", "name_ru": "Эпипремнум золотистый", "category": "Комнатные растения", "perenual_id": 2773, "search": ["epipremnum aureum", "pothos"]},
    {"scientific_name": "Ficus benjamina", "name_ru": "Фикус Бенджамина", "category": "Комнатные растения", "perenual_id": 2954, "search": ["ficus benjamina", "weeping fig"]},
    {"scientific_name": "Ficus elastica", "name_ru": "Фикус эластика", "category": "Комнатные растения", "perenual_id": 2961, "search": ["ficus elastica", "rubber plant"]},
    {"scientific_name": "Chlorophytum comosum", "name_ru": "Хлорофитум хохлатый", "category": "Комнатные растения", "perenual_id": 1847, "search": ["chlorophytum comosum", "spider plant"]},
    # --- Суккуленты и кактусы ---
    # {"scientific_name": "Echeveria agavoides", "name_ru": "Эхеверия Агавоидес", "category": "Суккуленты и кактусы", "perenual_id": None, "search": ["echeveria agavoides"]},
    {"scientific_name": "Aloe vera", "name_ru": "Алоэ вера", "category": "Суккуленты и кактусы", "perenual_id": 728, "search": ["aloe vera"]},
    # {"scientific_name": "Dracaena trifasciata", "name_ru": "Сансевиерия трёхполосная", "category": "Суккуленты и кактусы", "perenual_id": None, "search": ["dracaena trifasciata", "sansevieria trifasciata", "snake plant"]},
    # {"scientific_name": "Haworthiopsis fasciata", "name_ru": "Хавортия полосатая", "category": "Суккуленты и кактусы", "perenual_id": None, "search": ["haworthiopsis fasciata", "haworthia fasciata"]},
    {"scientific_name": "Crassula ovata", "name_ru": "Крассула овальная", "category": "Суккуленты и кактусы", "perenual_id": 2193, "search": ["crassula ovata", "jade plant"]},
    # {"scientific_name": "Opuntia microdasys", "name_ru": "Опунция мелковолосистая", "category": "Суккуленты и кактусы", "perenual_id": None, "search": ["opuntia microdasys", "bunny ears cactus"]},
    # --- Цветущие растения ---
    # {"scientific_name": "Spathiphyllum wallisii", "name_ru": "Спатифиллум", "category": "Цветущие растения", "perenual_id": None, "search": ["spathiphyllum wallisii", "peace lily"]},
    # {"scientific_name": "Streptocarpus ionanthus", "name_ru": "Узамбарская фиалка", "category": "Цветущие растения", "perenual_id": None, "search": ["streptocarpus ionanthus", "saintpaulia ionantha", "african violet"]},
    # {"scientific_name": "Phalaenopsis spp.", "name_ru": "Орхидея фаленопсис", "category": "Цветущие растения", "perenual_id": None, "search": ["phalaenopsis", "moth orchid"]},
    # {"scientific_name": "Hibiscus rosa-sinensis", "name_ru": "Гибискус китайский", "category": "Цветущие растения", "perenual_id": None, "search": ["hibiscus rosa-sinensis", "chinese hibiscus"]},
    # --- Папоротники и пальмы ---
    # {"scientific_name": "Nephrolepis exaltata", "name_ru": "Нефролепис возвышенный", "category": "Папоротники и пальмы", "perenual_id": None, "search": ["nephrolepis exaltata", "boston fern"]},
    {"scientific_name": "Chamaedorea elegans", "name_ru": "Хамедорея изящная", "category": "Папоротники и пальмы", "perenual_id": 1820, "search": ["chamaedorea elegans", "parlor palm"]},
]


def validate() -> list[str]:
    """Возвращает список проблем в списке растений (пустой список: всё в порядке)."""
    problems: list[str] = []
    seen: set[str] = set()
    seen_ids: set[int] = set()

    for p in PLANTS:
        name = p["scientific_name"]
        if name in seen:
            problems.append(f"Повтор научного названия: {name}")
        seen.add(name)

        if p["category"] not in KNOWN_CATEGORIES:
            problems.append(f"{name}: неизвестная категория «{p['category']}»")
        if not p["name_ru"].strip():
            problems.append(f"{name}: пустое русское название")
        if not p["search"]:
            problems.append(f"{name}: нет поисковых запросов")

        pid = p["perenual_id"]
        if pid is not None:
            if not 1 <= pid <= 3000:
                problems.append(f"{name}: perenual_id={pid} вне диапазона 1-3000 бесплатного ключа")
            if pid in seen_ids:
                problems.append(f"{name}: perenual_id={pid} уже указан у другого растения")
            seen_ids.add(pid)

    return problems


if __name__ == "__main__":
    issues = validate()
    filled = sum(1 for p in PLANTS if p["perenual_id"] is not None)
    print(f"Растений в списке: {len(PLANTS)}")
    print(f"Указан perenual_id: {filled} из {len(PLANTS)}")
    if issues:
        print("\nПроблемы:")
        for line in issues:
            print(" -", line)
        raise SystemExit(1)
    print("Проверка пройдена.")