"""Загрузка и проверка базы знаний из YAML-файлов."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .context import FACT_NAMES

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"


class KnowledgeError(Exception):
    """В базе знаний найдены ошибки."""


@dataclass(frozen=True)
class Symptom:
    id: str
    name: str
    kind: str
    synonyms: tuple[str, ...]
    question: str
    implies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Cause:
    id: str
    name: str
    urgency: str
    summary: str
    steps: tuple[str, ...]
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    id: str
    cause: str
    all: tuple[str, ...]
    cf: float
    explain: str


@dataclass
class Knowledge:
    symptoms: dict[str, Symptom]
    causes: dict[str, Cause]
    rules: list[Rule]
    sources: dict[str, dict[str, str]]
    settings: dict[str, Any]
    cache: dict[str, Any] = field(default_factory=dict)   # индексы, которые строят другие модули


def _read(directory: Path, name: str) -> dict:
    try:
        with open(directory / name, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise KnowledgeError(f"{name}: не удалось прочитать файл ({e})") from None
    if not isinstance(data, dict):
        raise KnowledgeError(f"{name}: ожидается словарь верхнего уровня")
    return data


def split_token(token: str) -> tuple[bool, bool, str]:
    """'!ctx:winter' -> (отрицание, это контекст, 'winter')."""
    negated = token.startswith("!")
    body = token[1:] if negated else token
    if body.startswith("ctx:"):
        return negated, True, body[4:]
    return negated, False, body


def load_knowledge(directory: Path | None = None) -> Knowledge:
    directory = directory or KNOWLEDGE_DIR
    errors: list[str] = []

    sym_raw = _read(directory, "symptoms.yaml").get("symptoms", {})
    cause_file = _read(directory, "causes.yaml")
    rules_raw = _read(directory, "rules.yaml").get("rules", [])
    settings = _read(directory, "settings.yaml")

    symptoms: dict[str, Symptom] = {}
    for sid, d in sym_raw.items():
        syn = tuple(d.get("synonyms") or ())
        if d.get("kind") not in ("symptom", "condition"):
            errors.append(f"симптом {sid}: kind должен быть symptom или condition")
        if not syn:
            errors.append(f"симптом {sid}: нет синонимов")
        if not d.get("question"):
            errors.append(f"симптом {sid}: нет вопроса (question)")
        if not d.get("name"):
            errors.append(f"симптом {sid}: нет названия (name)")
        symptoms[sid] = Symptom(
            id=sid,
            name=d.get("name", sid),
            kind=d.get("kind", "symptom"),
            synonyms=syn,
            question=d.get("question", ""),
            implies=tuple(d.get("implies") or ()),
        )
    for s in symptoms.values():
        for target in s.implies:
            if target not in symptoms:
                errors.append(f"симптом {s.id}: implies ссылается на неизвестный {target}")
            if target == s.id:
                errors.append(f"симптом {s.id}: implies ссылается на самого себя")

    sources = cause_file.get("sources", {}) or {}
    causes: dict[str, Cause] = {}
    for cid, d in (cause_file.get("causes", {}) or {}).items():
        if d.get("urgency") not in ("low", "medium", "high"):
            errors.append(f"причина {cid}: urgency должен быть low, medium или high")
        if not d.get("steps"):
            errors.append(f"причина {cid}: нет шагов (steps)")
        for src in d.get("sources") or ():
            if src not in sources:
                errors.append(f"причина {cid}: неизвестный источник {src}")
        causes[cid] = Cause(
            id=cid,
            name=d.get("name", cid),
            urgency=d.get("urgency", "low"),
            summary=d.get("summary", ""),
            steps=tuple(d.get("steps") or ()),
            sources=tuple(d.get("sources") or ()),
        )

    rules: list[Rule] = []
    seen: set[str] = set()
    for r in rules_raw:
        rid = r.get("id", "?")
        if rid in seen:
            errors.append(f"правило {rid}: повторяющийся id")
        seen.add(rid)
        if r.get("cause") not in causes:
            errors.append(f"правило {rid}: неизвестная причина {r.get('cause')}")
        cf = r.get("cf")
        if not isinstance(cf, (int, float)) or cf == 0 or not -1 <= cf <= 1:
            errors.append(f"правило {rid}: cf должен быть числом от -1 до 1 и не равен 0")
        conditions = tuple(r.get("all") or ())
        if not conditions:
            errors.append(f"правило {rid}: нет условий (all)")
        for token in conditions:
            _, is_ctx, name = split_token(str(token))
            if is_ctx and name not in FACT_NAMES:
                errors.append(f"правило {rid}: неизвестный факт ctx:{name}")
            if not is_ctx and name not in symptoms:
                errors.append(f"правило {rid}: неизвестный симптом {name}")
        if not r.get("explain"):
            errors.append(f"правило {rid}: нет объяснения (explain)")
        rules.append(
            Rule(id=rid, cause=r.get("cause", ""), all=tuple(str(t) for t in conditions),
                 cf=float(cf or 0), explain=r.get("explain", ""))
        )

    for key in ("seasons", "growing_months", "heating_months", "interval_factors", "thresholds", "dialog"):
        if key not in settings:
            errors.append(f"settings.yaml: нет раздела {key}")

    if errors:
        raise KnowledgeError("База знаний содержит ошибки:\n  - " + "\n  - ".join(errors))
    return Knowledge(symptoms, causes, rules, sources, settings)


def lint(kb: Knowledge) -> list[str]:
    """Предупреждения (не ошибки): что в базе знаний выглядит недоработанным."""
    warnings: list[str] = []
    used_symptoms: set[str] = set()
    positive_causes: set[str] = set()
    for r in kb.rules:
        for token in r.all:
            _, is_ctx, name = split_token(token)
            if not is_ctx:
                used_symptoms.add(name)
        if r.cf > 0:
            positive_causes.add(r.cause)
    for sid in kb.symptoms:
        if sid not in used_symptoms:
            implied_by_used = any(sid in kb.symptoms[u].implies for u in used_symptoms)
            if not implied_by_used:
                warnings.append(f"симптом {sid} не используется ни в одном правиле")
    for cid in kb.causes:
        if cid not in positive_causes:
            warnings.append(f"у причины {cid} нет подтверждающих правил")
        if not kb.causes[cid].sources:
            warnings.append(f"у причины {cid} не указаны источники")
    return warnings


@lru_cache(maxsize=1)
def get_knowledge() -> Knowledge:
    """База знаний, загруженная один раз на процесс."""
    return load_knowledge()
