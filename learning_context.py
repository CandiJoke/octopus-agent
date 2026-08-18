from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class LearningContext:
    user_id: str
    child_id: str
    source_run_id: str | None


_learning_context: ContextVar[LearningContext | None] = ContextVar(
    "learning_context",
    default=None,
)


def current_learning_context() -> LearningContext | None:
    return _learning_context.get()


@contextmanager
def learning_run_context(
    user_id: str,
    child_id: str,
    source_run_id: str | None,
) -> Iterator[None]:
    token = _learning_context.set(
        LearningContext(
            user_id=user_id,
            child_id=child_id,
            source_run_id=source_run_id,
        )
    )
    try:
        yield
    finally:
        _learning_context.reset(token)
