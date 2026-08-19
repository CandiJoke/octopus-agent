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
