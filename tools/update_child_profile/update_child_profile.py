from __future__ import annotations

from pathlib import Path

from learning_context import current_learning_context
from learning_store import LearningGradeInput, LearningStore
from pydantic import BaseModel, Field


DB_PATH = Path(__file__).resolve().parents[2] / "agent_hub.db"
learning_store = LearningStore(DB_PATH)
learning_store.initialize()

GRADE_LABELS = {
    "grade_1": "一年级",
    "grade_2": "二年级",
    "grade_3": "三年级",
    "grade_4": "四年级",
    "grade_5": "五年级",
    "grade_6": "六年级",
}


class UpdateChildProfileInput(BaseModel):
    grade: LearningGradeInput = Field(
        description=(
            "孩子当前小学年级。可用值：grade_1/一年级，grade_2/二年级，"
            "grade_3/三年级，grade_4/四年级，grade_5/五年级，grade_6/六年级。"
        )
    )


def run(grade: LearningGradeInput) -> str:
    context = current_learning_context()
    if context is None:
        return "暂时无法更新学习画像：缺少当前用户上下文。"

    try:
        profile = learning_store.update_default_profile_grade(context.user_id, grade)
    except ValueError:
        return "暂时无法更新学习画像：年级只支持小学一年级到六年级。"
    except Exception:
        return "暂时无法更新学习画像，请稍后重试。"

    return f"已更新学习画像：当前年级为{GRADE_LABELS.get(profile.grade, profile.grade)}。"
