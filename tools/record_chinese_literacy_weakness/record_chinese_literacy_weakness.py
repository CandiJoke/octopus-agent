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
    ability_id: str | None = Field(
        default=None,
        description=(
            "可选。匹配到的一年级语文课标能力点 ID，例如 "
            "chinese_g1_pinyin_initials 或 chinese_g1_pinyin_finals。"
            "不确定时不要填写。"
        ),
    )
    behavior_id: str | None = Field(
        default=None,
        description=(
            "可选。匹配到的一年级语文可观察表现 ID，例如 "
            "chinese_g1_pinyin_initials_distinguish_bpdq 或 "
            "chinese_g1_pinyin_finals_distinguish_ui_iu。不确定时不要填写。"
        ),
    )
    match_confidence: float | None = Field(
        default=None,
        description="可选。能力表现匹配置信度，0 到 1；不确定时不要填写。",
    )


def run(
    category: ChineseWeaknessCategoryInput,
    title: str,
    evidence: str,
    severity: WeaknessSeverityInput,
    ability_id: str | None = None,
    behavior_id: str | None = None,
    match_confidence: float | None = None,
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
            ability_id=ability_id,
            behavior_id=behavior_id,
            match_confidence=match_confidence,
        )
    except Exception:
        return "暂时无法记录薄弱点，请稍后重试。"

    action = "已记录薄弱点" if created else "已更新薄弱点"
    return f"{action}：{record.title}"
