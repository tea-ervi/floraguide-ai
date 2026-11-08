"""
Показывает, какие синонимы сработали на фразу: удобно искать, откуда взялся лишний или пропущенный симптом.

Запуск из папки backend:

  python scripts/explain_nlu.py "листья блёкнут"
  python scripts/explain_nlu.py "концы листьев сильно желтеют" "на листьях паутинка"

Для каждой фразы печатаются все сработавшие синонимы (по симптомам) и итог разбора. Если симптом попал
в итог из-за синонима, которого там быть не должно, удалите или удлините этот синоним в symptoms.yaml.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.expert import KnowledgeError, load_knowledge, nlu  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def explain(kb, text: str) -> None:
    words = nlu._content_words(text)
    keys = [nlu.word_key(w) for w in words]
    pos_by_key: dict[str, list[int]] = {}
    for i, key in enumerate(keys):
        pos_by_key.setdefault(key, []).append(i)

    print(f"\n«{text}»")
    print(f"  ключи слов: {' '.join(keys) or '—'}")
    any_hit = False
    for sid, symptom in kb.symptoms.items():
        hits = []
        for phrase in symptom.synonyms:
            syn_keys = tuple(nlu.word_key(w) for w in nlu._content_words(phrase))
            if syn_keys and nlu._find_positions(syn_keys, pos_by_key) is not None:
                hits.append(f"«{phrase}» ({len(set(syn_keys))} сл.)")
        if hits:
            any_hit = True
            print(f"  {sid}: " + "; ".join(hits))
    if not any_hit:
        print("  ни один синоним не сработал")

    result = nlu.analyze(kb, text)
    print(f"  итог: есть {sorted(result.present) or '—'}; нет {sorted(result.absent) or '—'}")
    dropped = sorted({m.symptom for m in result.matches} ^ (result.present | result.absent))
    if dropped:
        print(f"  (расхождение с итогом: {dropped})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Какие синонимы сработали на фразу")
    parser.add_argument("phrases", nargs="+", help="фразы в кавычках")
    args = parser.parse_args()
    try:
        kb = load_knowledge()
    except KnowledgeError as e:
        print(e)
        return 1
    for phrase in args.phrases:
        explain(kb, phrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
