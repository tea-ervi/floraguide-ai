"""
Проверка базы знаний: ошибки, предупреждения и статистика.

Запуск из папки backend:  python scripts/validate_knowledge.py
Код выхода 1, если найдены ошибки. Запускайте после каждой правки YAML-файлов.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.expert import KnowledgeError, lint, load_knowledge  # noqa: E402
from app.services.expert.knowledge_base import split_token  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        kb = load_knowledge()
    except KnowledgeError as e:
        print(e)
        return 1

    rules_per_cause = Counter(r.cause for r in kb.rules)
    print(f"Симптомов и условий: {len(kb.symptoms)}")
    print(f"Причин: {len(kb.causes)}")
    print(f"Правил: {len(kb.rules)} (против причины: {sum(1 for r in kb.rules if r.cf < 0)})")
    print(f"Источников: {len(kb.sources)}\n")

    print("Правила по причинам:")
    for cause_id, cause in kb.causes.items():
        print(f"  {cause_id:<22} {rules_per_cause.get(cause_id, 0):>3}  {cause.name}")

    ctx_use = Counter(split_token(t)[2] for r in kb.rules for t in r.all if split_token(t)[1])
    print("\nФакты о растении в правилах: " + ", ".join(f"{k} ({v})" for k, v in ctx_use.most_common()))

    warnings = lint(kb)
    if warnings:
        print("\nПредупреждения:")
        for w in warnings:
            print(" -", w)
    else:
        print("\nПредупреждений нет.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
