from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Literal

from skills.loader import load_skill_document, parse_bool, parse_csv
from tools import tools as registered_tools

SkillStatus = Literal["available", "planned"]

SKILL_SCHEMA_VERSION = "skill.v1"
SKILLS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class SkillSpec:
    directory: str


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    name: str
    display_name: str
    description: str
    category: str
    status: SkillStatus
    source: str
    enabled: bool
    tools: tuple[str, ...]
    instructions: str


SKILL_SPECS = (
    SkillSpec("math_problem_solver"),
    SkillSpec("knowledge_lookup"),
)


def list_skills() -> list[SkillRecord]:
    skill_records = [load_skill(spec.directory) for spec in SKILL_SPECS]
    validate_skill_records(skill_records, registered_tool_names())
    return skill_records


def get_skill(skill_id: str) -> SkillRecord | None:
    for skill in list_skills():
        if skill.skill_id == skill_id:
            return skill
    return None


def build_skill_catalog() -> dict[str, object]:
    return {
        "schemaVersion": SKILL_SCHEMA_VERSION,
        "skills": [serialize_skill_summary(skill) for skill in list_skills()],
    }


def load_skill(directory: str) -> SkillRecord:
    meta, instructions = load_skill_document(SKILLS_DIR / directory)
    status = meta["status"]
    if status not in {"available", "planned"}:
        raise ValueError(f"{directory} 的 status 不支持: {status}")

    return SkillRecord(
        skill_id=meta["id"],
        name=meta["name"],
        display_name=meta["display_name"],
        description=meta["description"],
        category=meta["category"],
        status=status,
        source=meta["source"],
        enabled=parse_bool(meta["enabled"]),
        tools=parse_csv(meta["tools"]),
        instructions=instructions,
    )


def registered_tool_names() -> set[str]:
    return {tool.name for tool in registered_tools}


def validate_skill_records(
    skills: Collection[SkillRecord],
    available_tool_names: Collection[str],
) -> None:
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    known_tools = set(available_tool_names)

    for skill in skills:
        if skill.skill_id in seen_ids:
            raise ValueError(f"duplicate skill id: {skill.skill_id}")
        seen_ids.add(skill.skill_id)

        if skill.name in seen_names:
            raise ValueError(f"duplicate skill name: {skill.name}")
        seen_names.add(skill.name)

        seen_bound_tools: set[str] = set()
        for tool_name in skill.tools:
            if tool_name in seen_bound_tools:
                raise ValueError(
                    f"duplicate bound tool in {skill.skill_id}: {tool_name}"
                )
            seen_bound_tools.add(tool_name)

            if tool_name not in known_tools:
                raise ValueError(
                    f"unknown bound tool in {skill.skill_id}: {tool_name}"
                )


def serialize_skill_summary(skill: SkillRecord) -> dict[str, object]:
    return {
        "id": skill.skill_id,
        "name": skill.name,
        "displayName": skill.display_name,
        "description": skill.description,
        "category": skill.category,
        "status": skill.status,
        "source": skill.source,
        "enabled": skill.enabled,
        "tools": list(skill.tools),
    }


def serialize_skill_detail(skill: SkillRecord) -> dict[str, object]:
    payload = serialize_skill_summary(skill)
    payload["instructions"] = skill.instructions
    return payload
