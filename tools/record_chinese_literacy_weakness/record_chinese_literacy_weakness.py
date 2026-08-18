from __future__ import annotations

from pathlib import Path

from learning_context import current_learning_context
from learning_store import (
    ChineseWeaknessCategoryInput,
    LearningStore,
    WeaknessSeverityInput,
)
from pydantic import BaseModel, Field


DB_PATH = Path(__file__).resolve().parents[2] / "agent_hub.db"
learning_store = LearningStore(DB_PATH)
learning_store.initialize()


class RecordChineseLiteracyWeaknessInput(BaseModel):
    category: ChineseWeaknessCategoryInput = Field(
        description=(
            "薄弱点分类。可用值：pinyin/拼音，character_recognition/识字，"
            "reading/朗读，expression/表达，learning_habit/学习习惯。"
        )
    )
    title: str = Field(description="短标题，只描述学习薄弱点，不写真实姓名、学校或诊断标签。")
    evidence: str = Field(description="家长描述中的具体依据，需隐藏真实姓名、学校、住址、电话和诊断标签。")
    severity: WeaknessSeverityInput = Field(
        description="严重程度。可用值：mild/轻微，medium/中等，high/明显。"
    )


def run(
    category: ChineseWeaknessCategoryInput,
    title: str,
    evidence: str,
    severity: WeaknessSeverityInput,
) -> str:
    context = current_learning_context()
    if context is None:
        return "暂时无法记录薄弱点：缺少当前用户上下文。"

    try:
        record, created = learning_store.upsert_weakness(
            context.user_id,
            context.child_id,
            category=category,
            title=title,
            evidence=evidence,
            severity=severity,
            source_run_id=context.source_run_id,
        )
    except Exception:
        return "暂时无法记录薄弱点，请稍后重试。"

    action = "已记录薄弱点" if created else "已更新薄弱点"
    return f"{action}：{record.title}"
