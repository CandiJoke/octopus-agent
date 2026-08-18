from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from skills.registry import SkillRecord, list_skills
from tools.loader import load_tool_meta
from tools.registry import TOOL_SPECS, TOOLS_DIR, ToolSpec


CapabilityType = Literal["tool", "skill"]
CapabilityStatus = Literal["available", "planned"]

CAPABILITY_SCHEMA_VERSION = "capability.v1"
SUPPORTED_CAPABILITY_TYPES: list[CapabilityType] = ["tool", "skill"]


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    capability_type: CapabilityType
    name: str
    display_name: str
    description: str
    category: str
    status: CapabilityStatus
    source: str
    enabled: bool
    tools: tuple[str, ...] = ()


def list_agent_capabilities() -> list[CapabilityRecord]:
    return [
        *[tool_spec_to_capability(spec) for spec in TOOL_SPECS],
        *[skill_to_capability(skill) for skill in list_skills()],
    ]


def build_capability_catalog() -> dict[str, object]:
    return {
        "schemaVersion": CAPABILITY_SCHEMA_VERSION,
        "supportedTypes": SUPPORTED_CAPABILITY_TYPES,
        "capabilities": [
            serialize_capability(capability)
            for capability in list_agent_capabilities()
        ],
    }


def tool_spec_to_capability(spec: ToolSpec) -> CapabilityRecord:
    meta = load_tool_meta(TOOLS_DIR / spec.directory)
    name = meta["name"]
    return CapabilityRecord(
        capability_id=f"tool.{name}",
        capability_type="tool",
        name=name,
        display_name=display_name_from_name(name),
        description=meta["description"],
        category=meta.get("category", spec.category),
        status="available",
        source="local",
        enabled=True,
    )


def skill_to_capability(skill: SkillRecord) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=f"skill.{skill.skill_id}",
        capability_type="skill",
        name=skill.name,
        display_name=skill.display_name,
        description=skill.description,
        category=skill.category,
        status=skill.status,
        source=skill.source,
        enabled=skill.enabled,
        tools=skill.tools,
    )


def serialize_capability(record: CapabilityRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": record.capability_id,
        "type": record.capability_type,
        "name": record.name,
        "displayName": record.display_name,
        "description": record.description,
        "category": record.category,
        "status": record.status,
        "source": record.source,
        "enabled": record.enabled,
    }
    if record.tools:
        payload["tools"] = list(record.tools)
    return payload


def display_name_from_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("_"))
