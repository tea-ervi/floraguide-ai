import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME", "floraguide_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Импортируем ВСЕ модели, чтобы связи (relationship) корректно настроились
from app.models.plant import PlantCategory, PlantSpecies, PlantPart, VisualIssue
from app.models.user import User, UserPlant

# Заглушка вместо настоящих эмбеддингов. Заменяется векторами FastEmbed позже.
DUMMY_EMBEDDING = [0.05] * 384

# Временная картинка для новых категорий: замените на реальные фото.
PLACEHOLDER_IMAGE = "https://placehold.co/600x400/c9dabd/1f3d2b?text=FloraGuide"

CATEGORIES = [
    {
        "name": "Комнатные растения",
        "image_url": "https://images.unsplash.com/photo-1485955900006-10f4d324d411",
    },
    {
        "name": "Суккуленты и кактусы",
        "image_url": "https://images.unsplash.com/photo-1509423350716-97f9360b4e09",
    },
    {"name": "Цветущие растения", "image_url": PLACEHOLDER_IMAGE},
    {"name": "Папоротники и пальмы", "image_url": PLACEHOLDER_IMAGE},
]

# Значения освещённости, влажности и сроков приблизительные.
# Перед использованием в экспертной системе сверьте их с надёжными источниками.
PLANTS = [
    # --- Комнатные растения ---
    {
        "category": "Комнатные растения",
        "name": "Монстера Делициоза",
        "scientific_name": "Monstera deliciosa",
        "description": "Популярное комнатное растение с крупными резными листьями.",
        "optimal_lux": 1500,
        "optimal_humidity": 60,
        "soil_composition": "Легкий плодородный грунт с добавлением перлита и торфа",
        "growth_duration_days": 365,
    },
    {
        "category": "Комнатные растения",
        "name": "Замиокулькас",
        "scientific_name": "Zamioculcas zamiifolia",
        "description": "Неприхотливое растение с глянцевыми листьями. Запасает воду в клубнях и переносит редкий полив и тень.",
        "optimal_lux": 1000,
        "optimal_humidity": 40,
        "soil_composition": "Рыхлый дренированный грунт: универсальный субстрат с добавлением перлита или песка",
        "growth_duration_days": 730,
    },
    {
        "category": "Комнатные растения",
        "name": "Эпипремнум золотистый",
        "scientific_name": "Epipremnum aureum",
        "description": "Быстрорастущая лиана с сердцевидными листьями. Подходит для подвесных кашпо и опор.",
        "optimal_lux": 1500,
        "optimal_humidity": 50,
        "soil_composition": "Лёгкий универсальный грунт с добавлением перлита",
        "growth_duration_days": 180,
    },
    {
        "category": "Комнатные растения",
        "name": "Фикус Бенджамина",
        "scientific_name": "Ficus benjamina",
        "description": "Деревце с мелкими глянцевыми листьями. Не любит перестановок и сквозняков, может сбрасывать листья при смене условий.",
        "optimal_lux": 3000,
        "optimal_humidity": 55,
        "soil_composition": "Питательный нейтральный грунт с дренажем",
        "growth_duration_days": 730,
    },
    {
        "category": "Комнатные растения",
        "name": "Фикус эластика",
        "scientific_name": "Ficus elastica",
        "description": "Фикус с крупными плотными кожистыми листьями. Хорошо растёт при ярком рассеянном свете.",
        "optimal_lux": 3000,
        "optimal_humidity": 50,
        "soil_composition": "Рыхлый питательный грунт с перлитом, хороший дренаж обязателен",
        "growth_duration_days": 540,
    },
    {
        "category": "Комнатные растения",
        "name": "Хлорофитум хохлатый",
        "scientific_name": "Chlorophytum comosum",
        "description": "Нетребовательное растение с полосатыми листьями, образует «детки» на длинных побегах.",
        "optimal_lux": 2500,
        "optimal_humidity": 50,
        "soil_composition": "Универсальный грунт с добавлением песка или перлита",
        "growth_duration_days": 120,
    },
    # --- Суккуленты и кактусы ---
    {
        "category": "Суккуленты и кактусы",
        "name": "Эхеверия Агавоидес",
        "scientific_name": "Echeveria agavoides",
        "description": "Эффектный суккулент, образующий плотную розетку мясистых листьев.",
        "optimal_lux": 5000,
        "optimal_humidity": 30,
        "soil_composition": "Специальный грунт для суккулентов с большим количеством дренажа",
        "growth_duration_days": 180,
    },
    {
        "category": "Суккуленты и кактусы",
        "name": "Алоэ вера",
        "scientific_name": "Aloe vera",
        "description": "Суккулент с мясистыми сочными листьями. Любит яркий свет и редкий, но обильный полив.",
        "optimal_lux": 5000,
        "optimal_humidity": 30,
        "soil_composition": "Грунт для кактусов и суккулентов с добавлением песка и перлита",
        "growth_duration_days": 730,
    },
    {
        "category": "Суккуленты и кактусы",
        "name": "Сансевиерия трёхполосная",
        "scientific_name": "Dracaena trifasciata",
        "description": "Известна как «щучий хвост» или «тёщин язык». Очень выносливое растение с прямыми жёсткими листьями.",
        "optimal_lux": 1500,
        "optimal_humidity": 40,
        "soil_composition": "Лёгкий песчаный грунт с хорошим дренажем",
        "growth_duration_days": 540,
    },
    {
        "category": "Суккуленты и кактусы",
        "name": "Хавортия полосатая",
        "scientific_name": "Haworthiopsis fasciata",
        "description": "Компактный суккулент с розеткой тёмных листьев в белую полоску. Подходит для окон с мягким светом.",
        "optimal_lux": 3000,
        "optimal_humidity": 30,
        "soil_composition": "Минеральный дренированный грунт для суккулентов",
        "growth_duration_days": 730,
    },
    {
        "category": "Суккуленты и кактусы",
        "name": "Крассула овальная",
        "scientific_name": "Crassula ovata",
        "description": "«Денежное дерево» с толстыми блестящими листьями и древовидным стволом.",
        "optimal_lux": 5000,
        "optimal_humidity": 30,
        "soil_composition": "Грунт для суккулентов с добавлением песка и мелкого гравия",
        "growth_duration_days": 730,
    },
    {
        "category": "Суккуленты и кактусы",
        "name": "Опунция мелковолосистая",
        "scientific_name": "Opuntia microdasys",
        "description": "Кактус с плоскими сегментами, покрытыми мелкими колючками-глохидиями. Требует много света.",
        "optimal_lux": 7000,
        "optimal_humidity": 25,
        "soil_composition": "Бедный песчаный грунт для кактусов с крупным дренажем",
        "growth_duration_days": 730,
    },
    # --- Цветущие растения ---
    {
        "category": "Цветущие растения",
        "name": "Спатифиллум",
        "scientific_name": "Spathiphyllum wallisii",
        "description": "Растение с тёмно-зелёными листьями и белыми соцветиями-покрывалами. Любит влажный воздух.",
        "optimal_lux": 1500,
        "optimal_humidity": 60,
        "soil_composition": "Рыхлый влагоёмкий грунт с добавлением перлита и коры",
        "growth_duration_days": 240,
    },
    {
        "category": "Цветущие растения",
        "name": "Узамбарская фиалка",
        "scientific_name": "Streptocarpus ionanthus",
        "description": "Компактное растение с бархатистыми листьями и небольшими цветками. Известно как сенполия.",
        "optimal_lux": 2500,
        "optimal_humidity": 55,
        "soil_composition": "Лёгкий рыхлый грунт для фиалок с добавлением вермикулита",
        "growth_duration_days": 270,
    },
    {
        "category": "Цветущие растения",
        "name": "Орхидея фаленопсис",
        "scientific_name": "Phalaenopsis spp.",
        "description": "Эпифитная орхидея с длительным цветением. Корни нуждаются в воздухе и свете, поэтому её сажают в прозрачный горшок.",
        "optimal_lux": 3000,
        "optimal_humidity": 60,
        "soil_composition": "Крупная кора сосны с добавлением сфагнума, обычный грунт не подходит",
        "growth_duration_days": 730,
    },
    {
        "category": "Цветущие растения",
        "name": "Гибискус китайский",
        "scientific_name": "Hibiscus rosa-sinensis",
        "description": "Кустарник с крупными яркими цветками. Много цветёт при ярком свете и регулярной подкормке.",
        "optimal_lux": 5000,
        "optimal_humidity": 55,
        "soil_composition": "Питательный слабокислый грунт с хорошим дренажем",
        "growth_duration_days": 365,
    },
    # --- Папоротники и пальмы ---
    {
        "category": "Папоротники и пальмы",
        "name": "Нефролепис возвышенный",
        "scientific_name": "Nephrolepis exaltata",
        "description": "Папоротник с длинными пушистыми вайями. Не переносит пересушенной почвы и сухого воздуха.",
        "optimal_lux": 2000,
        "optimal_humidity": 70,
        "soil_composition": "Рыхлый кислый влагоёмкий грунт с торфом",
        "growth_duration_days": 270,
    },
    {
        "category": "Папоротники и пальмы",
        "name": "Хамедорея изящная",
        "scientific_name": "Chamaedorea elegans",
        "description": "Небольшая пальма, хорошо растёт в полутени и подходит для комнат с рассеянным светом.",
        "optimal_lux": 1500,
        "optimal_humidity": 55,
        "soil_composition": "Лёгкий дренированный грунт для пальм",
        "growth_duration_days": 730,
    },
]


def get_or_create_category(db, data: dict) -> tuple[PlantCategory, bool]:
    category = db.query(PlantCategory).filter(PlantCategory.name == data["name"]).first()
    if category:
        return category, False
    category = PlantCategory(name=data["name"], image_url=data["image_url"])
    db.add(category)
    return category, True


def seed_database():
    db = SessionLocal()
    try:
        print("🌱 Заполняем базу данных...")

        # 1. Категории: создаются только отсутствующие
        categories: dict[str, PlantCategory] = {}
        new_categories = 0
        for data in CATEGORIES:
            category, created = get_or_create_category(db, data)
            categories[data["name"]] = category
            new_categories += int(created)
        db.flush()  # получаем id новых категорий без коммита

        # 2. Растения: пропускаем те, у кого научное название уже есть в базе
        existing = {
            name for (name,) in db.query(PlantSpecies.scientific_name).all()
        }
        new_species = 0
        for data in PLANTS:
            if data["scientific_name"] in existing:
                continue
            db.add(
                PlantSpecies(
                    name=data["name"],
                    scientific_name=data["scientific_name"],
                    description=data["description"],
                    optimal_lux=data["optimal_lux"],
                    optimal_humidity=data["optimal_humidity"],
                    soil_composition=data["soil_composition"],
                    growth_duration_days=data["growth_duration_days"],
                    embedding=DUMMY_EMBEDDING,
                    category_id=categories[data["category"]].id,
                )
            )
            new_species += 1

        db.commit()
        print(
            f"✅ Готово. Добавлено категорий: {new_categories}, растений: {new_species}. "
            f"Всего в каталоге: {len(existing) + new_species}."
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при заполнении базы: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()