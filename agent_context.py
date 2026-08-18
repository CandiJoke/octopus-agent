from __future__ import annotations

from collections.abc import Sequence

from skills.registry import SkillRecord, list_skills


def build_agent_system_prompt(skills: Sequence[SkillRecord] | None = None) -> str:
    candidate_skills = list_skills() if skills is None else skills
    active_skills = [
        skill
        for skill in candidate_skills
        if skill.enabled and skill.status == "available"
    ]

    lines = [
        "你是 Agent Hub 的单 Agent 执行器。",
        "你可以根据用户问题选择合适的工具完成任务，并把工具结果整合成自然回答。",
        "平台 Skill 是任务能力说明，不是可直接调用的工具；当 Skill 绑定了工具时，按说明选择对应工具。",
        "",
        "Available Skills:",
    ]
    for skill in active_skills:
        tools = ", ".join(skill.tools) if skill.tools else "none"
        lines.extend(
            [
                f"- Skill: {skill.display_name} (`{skill.name}`)",
                f"  Description: {skill.description}",
                f"  Bound tools: {tools}",
                f"  Instructions: {compact_instructions(skill.instructions)}",
            ]
        )

    return "\n".join(lines)


def compact_instructions(instructions: str) -> str:
    return " ".join(
        line.strip()
        for line in instructions.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


AGENT_SYSTEM_PROMPT = build_agent_system_prompt()
