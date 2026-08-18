from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from tools.calculator.calculator import run as calculator_run
from tools.loader import load_tool_meta
from tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness import (
    RecordChineseLiteracyWeaknessInput,
    run as record_chinese_literacy_weakness_run,
)
from tools.record_learning_weakness.record_learning_weakness import (
    RecordLearningWeaknessInput,
    run as record_learning_weakness_run,
)
from tools.search_knowledge.search_knowledge import run as search_knowledge_run

TOOLS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class ToolSpec:
    directory: str
    run_fn: Callable[..., str]
    category: str
    args_schema: type[BaseModel] | None = None


TOOL_SPECS = (
    ToolSpec("calculator", calculator_run, "基础工具"),
    ToolSpec("search_knowledge", search_knowledge_run, "知识检索"),
    ToolSpec(
        "record_chinese_literacy_weakness",
        record_chinese_literacy_weakness_run,
        "学习记录",
        RecordChineseLiteracyWeaknessInput,
    ),
    ToolSpec(
        "record_learning_weakness",
        record_learning_weakness_run,
        "学习记录",
        RecordLearningWeaknessInput,
    ),
)


def _make_tool(spec: ToolSpec) -> StructuredTool:
    meta = load_tool_meta(TOOLS_DIR / spec.directory)
    return StructuredTool.from_function(
        func=spec.run_fn,
        name=meta["name"],
        description=meta["description"],
        args_schema=spec.args_schema,
    )


tools = [_make_tool(spec) for spec in TOOL_SPECS]
