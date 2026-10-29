"""Понимание текста: из фразы пользователя в симптомы базы знаний.

Основа: словарь синонимов из symptoms.yaml плюс нормализация слов (стемминг Snowball).
Необязательный слой: векторное сравнение (FastEmbed), если словарь ничего не нашёл.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable

import snowballstemmer

from .knowledge_base import Knowledge

_STEMMER = snowballstemmer.stemmer("russian")

STOP_WORDS = {
    "на", "в", "во", "по", "у", "с", "со", "к", "ко", "и", "а", "но", "же", "ли", "бы", "от", "за", "из",
    "о", "об", "при", "для", "как", "что", "это", "то", "уже", "очень", "тоже", "вот", "мне", "меня",
    "мой", "моя", "мои", "моё", "мое", "она", "он", "оно", "они", "себя", "вдруг",
}
NEGATORS = {"не", "нет", "без", "ни", "нету"}
VERB_PREFIXES = ("пере", "при", "по", "за", "вы", "об", "на", "у")

YES_WORDS = {"да", "ага", "угу", "есть", "верно", "точно", "конечно", "именно", "пожалуй"}
NO_WORDS = {"нет", "неа", "нету"}
UNKNOWN_FIRST = {"незнаю", "затрудняюсь"}
UNKNOWN_PAIRS = {("не", "знаю"), ("не", "уверена"), ("не", "уверен"), ("не", "помню")}
NO_PAIRS = {("не", "замечала"), ("не", "замечал"), ("не", "видела"), ("не", "видел")}

SCHEDULE_TRIGGERS = {"когда", "часто", "сколько", "график", "расписание", "следующий", "следующая"}
HELP_WORDS = {"привет", "здравствуйте", "здравствуй", "помощь", "помоги", "умеешь", "можешь"}

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", text.lower().replace("ё", "е"))


def word_key(word: str) -> str:
    """Ключ слова: основа без приставки, обрезанная до 4 букв (желтеют, желтые, пожелтели дают «желт»)."""
    stem = _STEMMER.stemWord(word)
    if len(stem) >= 6:
        for prefix in VERB_PREFIXES:
            if stem.startswith(prefix) and len(stem) - len(prefix) >= 4:
                stem = stem[len(prefix):]
                break
    return stem[:4]


NEG_KEYS = {word_key(w) for w in NEGATORS} | NEGATORS


def _content_words(text: str) -> list[str]:
    return [w for w in normalize(text) if w not in STOP_WORDS]


@dataclass
class Match:
    symptom: str
    positions: tuple[int, ...]
    keys: frozenset[str]
    negated: bool = False


@dataclass
class NLUResult:
    present: set[str] = field(default_factory=set)
    absent: set[str] = field(default_factory=set)
    matches: list[Match] = field(default_factory=list)
    answer: str | None = None       # yes / no / unknown: ответ на заданный вопрос
    intent: str | None = None       # schedule / help
    semantic: bool = False          # симптом найден векторным поиском


def _index(kb: Knowledge) -> dict[str, list[tuple[str, ...]]]:
    index = kb.cache.get("nlu_index")
    if index is None:
        index = {}
        for sid, sym in kb.symptoms.items():
            variants: list[tuple[str, ...]] = []
            for phrase in sym.synonyms:
                keys = tuple(word_key(w) for w in _content_words(phrase))
                if keys and keys not in variants:
                    variants.append(keys)
            index[sid] = variants
        kb.cache["nlu_index"] = index
    return index


def _find_positions(syn_keys: tuple[str, ...], pos_by_key: dict[str, list[int]]) -> list[int] | None:
    """Позиции слов синонима в сообщении (слова должны стоять недалеко друг от друга)."""
    if any(k not in pos_by_key for k in syn_keys):
        return None
    best: tuple[int, list[int]] | None = None
    for anchor in pos_by_key[syn_keys[0]]:
        chosen, used, ok = [anchor], {anchor}, True
        for key in syn_keys[1:]:
            candidates = [p for p in pos_by_key[key] if p not in used]
            if not candidates:
                ok = False
                break
            pos = min(candidates, key=lambda p: abs(p - anchor))
            chosen.append(pos)
            used.add(pos)
        if ok:
            span = max(chosen) - min(chosen)
            if best is None or span < best[0]:
                best = (span, sorted(chosen))
    if best is None or best[0] > len(syn_keys) + 3:
        return None
    return best[1]


def _is_negated(positions: tuple[int, ...], keys: list[str], ignore: set[int]) -> bool:
    """Перед признаком или между его словами стоит отрицание («листья не желтеют», «нет паутины»)."""
    lo, hi = max(0, min(positions) - 1), max(positions)
    pos_set = set(positions)
    return any(
        i not in pos_set and i not in ignore and keys[i] in NEG_KEYS
        for i in range(lo, hi + 1)
    )


def _lead_answer(words: list[str]) -> tuple[str, int] | None:
    """Ответ «да»/«нет»/«не знаю» в начале сообщения: (ответ, сколько слов он занимает)."""
    if not words:
        return None
    first = words[0]
    if first in UNKNOWN_FIRST:
        return "unknown", 1
    if len(words) >= 2 and (first, words[1]) in UNKNOWN_PAIRS:
        return "unknown", 2
    if len(words) >= 2 and (first, words[1]) in NO_PAIRS:
        return "no", 2
    if first in YES_WORDS:
        return "yes", 1
    if first in NO_WORDS:
        return "no", 1
    return None


def _detect_intent(words: list[str]) -> str | None:
    if any(w.startswith(("полив", "полит", "полью", "поливат")) for w in words):
        if any(w in SCHEDULE_TRIGGERS for w in words):
            return "schedule"
    if any(w in HELP_WORDS for w in words):
        return "help"
    return None


# ---------------------------------------------------------------- векторный слой (необязательный)
_semantic: dict[str, object] = {"embed": None, "threshold": 0.6}


def set_semantic(embed_fn: Callable[[list[str]], list[list[float]]] | None, threshold: float = 0.6) -> None:
    """Включает векторное сравнение. embed_fn получает список фраз и возвращает список векторов."""
    _semantic["embed"] = embed_fn
    _semantic["threshold"] = threshold


def enable_fastembed(threshold: float = 0.6, cache_dir: str | None = None) -> None:
    """Подключает FastEmbed. Порог нужно подобрать на своих примерах (scripts/evaluate_expert.py --semantic)."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir)
    set_semantic(lambda texts: [v.tolist() for v in model.embed(texts)], threshold)


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _semantic_symptom(kb: Knowledge, text: str) -> str | None:
    embed = _semantic["embed"]
    if embed is None:
        return None
    try:
        phrases = kb.cache.get("semantic_phrases")
        if phrases is None:
            labels = [(sid, p) for sid, s in kb.symptoms.items() for p in s.synonyms]
            vectors = [_unit(v) for v in embed([p for _, p in labels])]
            phrases = list(zip([sid for sid, _ in labels], vectors))
            kb.cache["semantic_phrases"] = phrases
        query = _unit(embed([text])[0])
    except Exception:
        return None
    best_id, best_sim = None, 0.0
    for sid, vec in phrases:
        sim = sum(a * b for a, b in zip(query, vec))
        if sim > best_sim:
            best_id, best_sim = sid, sim
    return best_id if best_sim >= float(_semantic["threshold"]) else None


# ---------------------------------------------------------------- главная функция
def analyze(kb: Knowledge, text: str, pending: str | None = None) -> NLUResult:
    index = _index(kb)
    # Слова по смысловым частям (запятые, точки и т.д.): совпадение внутри одной части надёжнее,
    # чем «склеенное» из двух («листья желтеют, кончики не сохнут» не равно «кончики листьев желтеют»)
    words: list[str] = []
    clause_of: list[int] = []
    for clause_no, clause in enumerate(re.split(r"[,.;:!?\n()]+", text)):
        for word in _content_words(clause):
            words.append(word)
            clause_of.append(clause_no)
    keys = [word_key(w) for w in words]
    pos_by_key: dict[str, list[int]] = {}
    for i, k in enumerate(keys):
        pos_by_key.setdefault(k, []).append(i)

    # 1. лучший вариант синонима для каждого симптома
    found: dict[str, Match] = {}
    for sid, variants in index.items():
        best: tuple[tuple[bool, int, int], Match] | None = None
        for syn_keys in variants:
            positions = _find_positions(syn_keys, pos_by_key)
            if positions is None:
                continue
            span = max(positions) - min(positions)
            same_clause = len({clause_of[p] for p in positions}) == 1
            rank = (same_clause, len(set(syn_keys)), -span)
            if best is None or rank > best[0]:
                best = (rank, Match(sid, tuple(positions), frozenset(syn_keys)))
        if best:
            found[sid] = best[1]

    # 2. более полное совпадение вытесняет вложенное («нижние листья желтеют» вместо «листья желтеют»)
    matches = [
        m for m in found.values()
        if not any(
            o is not m and m.keys < o.keys and set(m.positions) & set(o.positions)
            for o in found.values()
        )
    ]

    # 3. ответ на заданный вопрос в начале сообщения
    result = NLUResult(matches=matches)
    ignore: set[int] = set()
    if pending:
        lead = _lead_answer(words)
        if lead:
            answer, n = lead
            covered = {p for m in matches for p in m.positions}
            if not covered & set(range(n)):   # слово «нет» не входит в синоним («нет дырок в горшке»)
                result.answer = answer
                ignore = set(range(n))

    # 4. отрицание: «нет паутины», «земля не сухая»
    for m in matches:
        m.negated = _is_negated(m.positions, keys, ignore)
        (result.absent if m.negated else result.present).add(m.symptom)

    if not matches and result.answer is None:
        sid = _semantic_symptom(kb, text)
        if sid:
            result.present.add(sid)
            result.semantic = True

    if not result.present and not result.absent and result.answer is None:
        result.intent = _detect_intent(words)
    return result
