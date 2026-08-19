from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


CURRICULUM_DIR = Path(__file__).parent / "curriculum"


@dataclass(frozen=True)
class CurriculumAbilityRef:
    grade: str
    subject: str
    domain_id: str
    domain_title: str
    ability_id: str
    title: str
    category: str


@dataclass(frozen=True)
class CurriculumBehaviorRef:
    grade: str
    subject: str
    domain_id: str
    domain_title: str
    ability_id: str
    ability_title: str
    behavior_id: str
    behavior_title: str
    category: str


@dataclass(frozen=True)
class CurriculumBehaviorMatch:
    behavior: CurriculumBehaviorRef
    confidence: float


@lru_cache(maxsize=16)
def _load_primary_grade_curriculum(grade: str) -> dict[str, Any]:
    path = CURRICULUM_DIR / f"primary_{grade}.json"
    if not path.exists():
        raise LookupError(f"unsupported primary curriculum grade: {grade}")
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def get_primary_grade_curriculum(grade: str) -> dict[str, object]:
    return copy.deepcopy(_load_primary_grade_curriculum(grade))


def resolve_curriculum_ability(
    grade: str,
    subject: str,
    ability_id: str,
) -> CurriculumAbilityRef:
    for subject_node in _load_primary_grade_curriculum(grade)["subjects"]:
        if subject_node["subject"] != subject:
            continue
        for domain in subject_node["domains"]:
            for ability in domain["abilities"]:
                if ability["abilityId"] == ability_id:
                    return CurriculumAbilityRef(
                        grade=grade,
                        subject=subject,
                        domain_id=domain["domainId"],
                        domain_title=domain["title"],
                        ability_id=ability["abilityId"],
                        title=ability["title"],
                        category=ability["category"],
                    )
    raise LookupError(f"unknown curriculum ability: {ability_id}")


def resolve_curriculum_behavior(
    grade: str,
    subject: str,
    behavior_id: str,
) -> CurriculumBehaviorRef:
    for subject_node in _load_primary_grade_curriculum(grade)["subjects"]:
        if subject_node["subject"] != subject:
            continue
        for domain in subject_node["domains"]:
            for ability in domain["abilities"]:
                for behavior in ability["behaviors"]:
                    if behavior["behaviorId"] == behavior_id:
                        return CurriculumBehaviorRef(
                            grade=grade,
                            subject=subject,
                            domain_id=domain["domainId"],
                            domain_title=domain["title"],
                            ability_id=ability["abilityId"],
                            ability_title=ability["title"],
                            behavior_id=behavior["behaviorId"],
                            behavior_title=behavior["title"],
                            category=ability["category"],
                        )
    raise LookupError(f"unknown curriculum behavior: {behavior_id}")


def infer_curriculum_behavior(
    grade: str,
    subject: str,
    category: str,
    title: str,
    evidence: str,
) -> CurriculumBehaviorMatch | None:
    try:
        curriculum = _load_primary_grade_curriculum(grade)
    except LookupError:
        return None

    text = f"{title} {evidence}"
    compact_text = _compact_match_text(text)
    ascii_text = _compact_ascii_text(text)
    best_behavior: CurriculumBehaviorRef | None = None
    best_score = 0.0
    ambiguous_best = False

    for subject_node in curriculum["subjects"]:
        if subject_node["subject"] != subject:
            continue
        for domain in subject_node["domains"]:
            for ability in domain["abilities"]:
                if ability["category"] != category:
                    continue
                for behavior in ability["behaviors"]:
                    score = _score_behavior_match(
                        compact_text,
                        ascii_text,
                        behavior,
                    )
                    if score <= 0:
                        continue
                    behavior_ref = CurriculumBehaviorRef(
                        grade=grade,
                        subject=subject,
                        domain_id=domain["domainId"],
                        domain_title=domain["title"],
                        ability_id=ability["abilityId"],
                        ability_title=ability["title"],
                        behavior_id=behavior["behaviorId"],
                        behavior_title=behavior["title"],
                        category=ability["category"],
                    )
                    if score > best_score:
                        best_behavior = behavior_ref
                        best_score = score
                        ambiguous_best = False
                    elif score == best_score:
                        ambiguous_best = True

    if best_behavior is None or ambiguous_best:
        return None
    return CurriculumBehaviorMatch(behavior=best_behavior, confidence=best_score)


def _score_behavior_match(
    compact_text: str,
    ascii_text: str,
    behavior: dict[str, Any],
) -> float:
    candidates = [behavior["title"], *behavior.get("evidenceExamples", [])]
    for candidate in candidates:
        compact_candidate = _compact_match_text(candidate)
        if len(compact_candidate) >= 3 and compact_candidate in compact_text:
            return 0.76

    for candidate in candidates:
        signature = _compact_ascii_text(candidate)
        if len(signature) >= 2 and not signature.isdigit() and signature in ascii_text:
            return 0.76

    return 0.0


def _compact_match_text(value: str) -> str:
    return "".join(char for char in str(value).casefold() if char.isalnum())


def _compact_ascii_text(value: str) -> str:
    return "".join(
        char
        for char in str(value).casefold()
        if char.isascii() and char.isalnum()
    )
