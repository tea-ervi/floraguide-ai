"""
Пересчёт эмбеддингов (векторов) через FastEmbed.

Зачем: в сиде у всех растений стоял один и тот же вектор-заглушка [0.05] * 384, поэтому
векторный поиск не мог отличить одно растение от другого. Этот скрипт заменяет заглушки
настоящими векторами, посчитанными по тексту (название + научное название + описание).

Что обновляется:
  plants   plant_species.embedding   по названию, научному названию и описанию
  issues   visual_issues.embedding   по названию симптома (нужно для будущего чата)

По умолчанию пересчитываются только строки, где вектор пустой или является заглушкой
(все числа одинаковые). Ключ --force пересчитывает всё.

Запуск из папки backend (с активным venv):

  python scripts/reindex_embeddings.py              # растения и симптомы
  python scripts/reindex_embeddings.py --table plants
  python scripts/reindex_embeddings.py --force

Первый запуск скачивает модель (около 220 МБ) в backend/.fastembed_cache.
Добавьте .fastembed_cache/ в .gitignore.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Модель на 384 измерения, понимает русский язык. Размерность должна совпадать с Vector(384) в моделях.
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
BATCH_SIZE = 16

_model = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Возвращает по одному вектору на каждый текст."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding  # импорт здесь: модель грузится только когда нужна

        cache_dir = str(BACKEND_DIR / ".fastembed_cache")
        print(f"Загрузка модели {MODEL_NAME} (при первом запуске скачивается около 220 МБ)...")
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir)
    return [vector.tolist() for vector in _model.embed(texts)]


def is_stale(vector: Any) -> bool:
    """Пусто или заглушка: все числа в векторе одинаковые."""
    if vector is None:
        return True
    return max(vector) == min(vector)


def plant_text(plant: Any) -> str:
    parts = [plant.name, plant.scientific_name, plant.description]
    return ". ".join(p.strip() for p in parts if p and p.strip())


def issue_text(issue: Any) -> str:
    return issue.symptom_title.strip()


def reindex_rows(db: Any, rows: list, text_of, force: bool, label: str) -> int:
    targets = [r for r in rows if force or is_stale(r.embedding)]
    print(f"{label}: всего {len(rows)}, к пересчёту {len(targets)}")
    done = 0
    for start in range(0, len(targets), BATCH_SIZE):
        batch = targets[start : start + BATCH_SIZE]
        vectors = embed_texts([text_of(r) for r in batch])
        for row, vector in zip(batch, vectors):
            if len(vector) != DIMENSIONS:
                raise RuntimeError(f"Модель вернула {len(vector)} чисел, в базе ожидается {DIMENSIONS}")
            row.embedding = vector
            done += 1
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Пересчёт эмбеддингов через FastEmbed")
    parser.add_argument("--table", choices=["plants", "issues", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="пересчитать все векторы, а не только заглушки")
    args = parser.parse_args()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.plant import PlantSpecies, VisualIssue
    from app.models.user import User, UserPlant  # noqa: F401  (нужны для настройки связей моделей)

    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{n}".format(
        u=os.getenv("DB_USER", "postgres"),
        p=os.getenv("DB_PASSWORD", "postgres"),
        h=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5433"),
        n=os.getenv("DB_NAME", "floraguide_db"),
    )
    Session = sessionmaker(bind=create_engine(url))

    total = 0
    with Session() as db:
        try:
            if args.table in ("plants", "all"):
                plants = db.query(PlantSpecies).order_by(PlantSpecies.id).all()
                total += reindex_rows(db, plants, plant_text, args.force, "Растения")
            if args.table in ("issues", "all"):
                issues = db.query(VisualIssue).order_by(VisualIssue.id).all()
                total += reindex_rows(db, issues, issue_text, args.force, "Симптомы")
            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"\nПересчитано векторов: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
