from __future__ import annotations

import re

from curriculum_catalog import resolve_curriculum_behavior
from learning_store import LearningWeaknessRecord


def generate_practice_set(record: LearningWeaknessRecord) -> dict[str, object]:
    if record.behavior_id is None:
        raise ValueError("practice requires observable behavior")

    try:
        behavior = resolve_curriculum_behavior(
            record.grade,
            record.subject,
            record.behavior_id,
        )
    except LookupError as exc:
        raise ValueError(str(exc)) from exc

    items = contrast_items_from_title(behavior.behavior_title)
    questions = (
        contrast_questions(items)
        if len(items) >= 2
        else generic_behavior_questions(behavior.behavior_title)
    )

    return {
        "practiceSetId": f"practice_{record.weakness_id}",
        "weaknessId": record.weakness_id,
        "subject": record.subject,
        "category": record.category,
        "abilityId": behavior.ability_id,
        "abilityTitle": behavior.ability_title,
        "behaviorId": behavior.behavior_id,
        "behaviorTitle": behavior.behavior_title,
        "title": f"专项训练：{behavior.behavior_title}",
        "passingScore": 3,
        "passingCriteria": "连续答对 3 题，且最后一题能稳定完成后，可手动标注通过。",
        "questions": questions,
    }


def contrast_items_from_title(title: str) -> list[str]:
    items: list[str] = []
    for item in re.findall(r"[A-Za-z]+", title):
        normalized = item.lower()
        if normalized not in items:
            items.append(normalized)
    return items


def contrast_questions(items: list[str]) -> list[dict[str, object]]:
    first = items[0]
    second = items[1]
    last = items[-1]
    options = items[:]
    return [
        {
            "questionId": "q1",
            "prompt": f"听到或看到「{first}」时，让孩子从选项中指出正确项。",
            "options": options,
            "answer": first,
            "explanation": f"观察孩子是否能把「{first}」和「{second}」区分开。",
        },
        {
            "questionId": "q2",
            "prompt": f"听到或看到「{second}」时，让孩子从选项中指出正确项。",
            "options": options,
            "answer": second,
            "explanation": f"如果孩子犹豫，先回到「{first}/{second}」对比练习。",
        },
        {
            "questionId": "q3",
            "prompt": f"按顺序读给孩子听：{first}、{second}、{first}，让孩子依次指出。",
            "options": options,
            "answer": f"{first}、{second}、{first}",
            "explanation": "连续辨认能看出是否只是猜对一次。",
        },
        {
            "questionId": "q4",
            "prompt": f"随机指读：{last}、{first}、{second}，让孩子读出并说出差别。",
            "options": options,
            "answer": f"能读出 {last}、{first}、{second}，并说出差别",
            "explanation": "能说出差别时，再考虑标注通过。",
        },
    ]


def generic_behavior_questions(behavior_title: str) -> list[dict[str, object]]:
    return [
        {
            "questionId": "q1",
            "prompt": f"让孩子完成一次：{behavior_title}",
            "answer": "能独立完成",
            "explanation": "先观察是否能独立完成，不急于提示。",
        },
        {
            "questionId": "q2",
            "prompt": f"换一个材料，再完成一次：{behavior_title}",
            "answer": "换材料后仍能完成",
            "explanation": "换材料可以减少背答案的影响。",
        },
        {
            "questionId": "q3",
            "prompt": f"隔 3 分钟后复测：{behavior_title}",
            "answer": "延迟后仍能稳定完成",
            "explanation": "延迟复测更接近日常学习表现。",
        },
    ]
