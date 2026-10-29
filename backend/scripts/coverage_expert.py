"""
Покрытие знаний тестовыми случаями: какие правила, причины и симптомы ни разу не проверялись.

Правило, которое не сработало ни в одном случае, никем не проверено: оно может содержать опечатку
или противоречить соседним. Этот отчёт подсказывает, какие тестовые случаи написать следующими.

Запуск из папки backend:

  python scripts/coverage_expert.py
  python scripts/coverage_expert.py --cases tests/expert_cases.yaml
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.expert import KnowledgeError, load_knowledge  # noqa: E402
from app.services.expert.engine import absent_closure, holds, present_closure  # noqa: E402
from app.services.expert.simulate import context_from_case, load_cases, simulate  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Покрытие знаний тестовыми случаями")
    parser.add_argument("--cases", type=Path, default=BACKEND_DIR / "tests" / "expert_cases.yaml")
    args = parser.parse_args()

    try:
        kb = load_knowledge()
    except KnowledgeError as e:
        print(e)
        return 1

    cases = load_cases(args.cases)
    fired_rules: set[str] = set()
    seen_symptoms: set[str] = set()
    expected_causes: Counter[str] = Counter()
    for case in cases:
        ctx = context_from_case(kb, case.get("plant", {}))
        result = simulate(kb, ctx, case["text"], case.get("answers"))
        # Считаем все сработавшие правила, в том числе «против»: они вычёркивают гипотезы и в рейтинге не видны
        present = present_closure(kb, set(result.state["present"]))
        absent = absent_closure(kb, set(result.state["absent"]))
        fired_rules.update(r.id for r in kb.rules if all(holds(t, ctx, present, absent) for t in r.all))
        seen_symptoms.update(result.state["present"])
        seen_symptoms.update(result.state["absent"])
        if case.get("expect"):
            expected_causes[case["expect"]] += 1

    rules_total = len(kb.rules)
    print(f"Случаев: {len(cases)}")
    print(f"Правил проверено хотя бы раз: {len(fired_rules)} из {rules_total} ({len(fired_rules) / rules_total:.0%})")

    untested = [r for r in kb.rules if r.id not in fired_rules]
    if untested:
        print("\nПравила, которые не сработали ни в одном случае:")
        for rule in untested:
            print(f"  {rule.id:<24} {kb.causes[rule.cause].name[:34]:<34} условия: {', '.join(rule.all)}")

    print("\nСлучаев на каждую причину (хотя бы 2-3 желательно):")
    for cause_id, cause in kb.causes.items():
        count = expected_causes.get(cause_id, 0)
        flag = "  <- нет случаев" if count == 0 else "  <- мало" if count == 1 else ""
        print(f"  {cause_id:<22} {count:>2}{flag}")

    unused = [sid for sid in kb.symptoms if sid not in seen_symptoms]
    if unused:
        print("\nСимптомы, которые ни разу не встретились в случаях: " + ", ".join(unused))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
