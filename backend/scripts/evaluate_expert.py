"""
Оценка качества экспертной системы на тестовых случаях (tests/expert_cases.yaml).

Показывает точность (главная причина совпала с ожидаемой) и список ошибок с гипотезами системы.
База данных и интернет не нужны.

Запуск из папки backend:

  python scripts/evaluate_expert.py
  python scripts/evaluate_expert.py --verbose          # результат по каждому случаю
  python scripts/evaluate_expert.py --min-accuracy 0.9 # код выхода 1, если точность ниже
  python scripts/evaluate_expert.py --cases my_cases.yaml
  python scripts/evaluate_expert.py --phrases tests/phrases.yaml            # понимание отдельных фраз
  python scripts/evaluate_expert.py --phrases tests/phrases.yaml --semantic 0.6   # то же с векторным слоем
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import yaml  # noqa: E402

from app.services.expert import KnowledgeError, load_knowledge, nlu  # noqa: E402
from app.services.expert.simulate import load_cases, run_case  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def evaluate_phrases(kb, path: Path, verbose: bool) -> int:
    """Проверяет только понимание текста: нашла ли система нужные симптомы и не добавила ли лишние."""
    items = yaml.safe_load(path.read_text(encoding="utf-8"))["phrases"]
    full = extra = 0
    misses = []
    for item in items:
        result = nlu.analyze(kb, item["text"])
        want_present, want_absent = set(item.get("present", [])), set(item.get("absent", []))
        found = want_present <= result.present and want_absent <= result.absent
        surplus = (result.present - want_present) | (result.absent - want_absent)
        full += found
        extra += bool(surplus)
        mark = "ok " if found and not surplus else "ПРОПУСК" if not found else "ЛИШНЕЕ"
        if verbose or mark != "ok ":
            how = " (векторный слой)" if result.semantic else ""
            print(f"[{mark}] «{item['text']}»: нужно {sorted(want_present | {'нет ' + a for a in want_absent})}; "
                  f"система {sorted(result.present | {'нет ' + a for a in result.absent})}{how}")
        if not found:
            misses.append(item["text"])
    print(f"\nФраз: {len(items)}. Понято полностью: {full} ({full / len(items):.0%}). Лишние симптомы в {extra} фразах.")
    if misses:
        print("Добавьте синонимы в symptoms.yaml для пропущенных фраз, затем запустите проверку снова.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Оценка экспертной системы")
    parser.add_argument("--cases", type=Path, default=BACKEND_DIR / "tests" / "expert_cases.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--phrases", type=Path, help="проверить понимание фраз из YAML-файла (tests/phrases.yaml)")
    parser.add_argument("--semantic", nargs="?", const=0.6, type=float, metavar="ПОРОГ",
                        help="включить векторный слой FastEmbed (при первом запуске скачивается модель около 220 МБ)")
    args = parser.parse_args()

    if args.semantic is not None:
        nlu.enable_fastembed(args.semantic, str(BACKEND_DIR / ".fastembed_cache"))

    try:
        kb = load_knowledge()
    except KnowledgeError as e:
        print(e)
        return 1

    if args.phrases:
        return evaluate_phrases(kb, args.phrases, args.verbose)

    results = [run_case(kb, case) for case in load_cases(args.cases)]
    total = len(results)
    passed = sum(r["ok"] for r in results)
    expecting = [r for r in results if not r["expect"].startswith("не ")]
    top1 = sum(r["top1"] for r in expecting)
    top2 = sum(r["top2"] for r in expecting)

    for r in results:
        if args.verbose or not r["ok"]:
            mark = "ok " if r["ok"] else "ОШИБКА"
            got = ", ".join(f"{c} {cf}" for c, cf in r["got"]) or "нет гипотез"
            asked = f" вопросы: {', '.join(r['questions'])}" if r["questions"] else ""
            print(f"[{mark}] {r['id']}: ожидалось {r['expect']}; система: {got}; итог: {r['final_kind']};{asked}")

    accuracy = passed / total if total else 0.0
    print(f"\nСлучаев: {total}. Прошло: {passed} ({accuracy:.0%}).")
    if expecting:
        print(f"Главная причина верна: {top1}/{len(expecting)}. Верная причина в первых двух: {top2}/{len(expecting)}.")
    questions = sum(len(r["questions"]) for r in results) / total if total else 0.0
    diagnosed = sum(r["final_kind"] == "diagnosis" for r in results)
    print(f"Среднее число уточняющих вопросов: {questions:.1f}. Диалогов, закончившихся диагнозом: {diagnosed}/{total}.")
    return 0 if accuracy >= args.min_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(main())
