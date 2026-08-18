from __future__ import annotations

from pathlib import Path

from learning_context import current_learning_context
from learning_store import LearningStore


DB_PATH = Path(__file__).resolve().parents[2] / "agent_hub.db"
learning_store = LearningStore(DB_PATH)
learning_store.initialize()


def run(category: str, title: str, evidence: str, severity: str) -> str:
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
