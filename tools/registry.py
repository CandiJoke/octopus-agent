from pathlib import Path

from langchain_core.tools import StructuredTool

from tools.calculator.calculator import run as calculator_run
from tools.loader import load_tool_meta
from tools.search_knowledge.search_knowledge import run as search_knowledge_run

TOOLS_DIR = Path(__file__).parent


def _make_tool(tool_dir: str, run_fn) -> StructuredTool:
    meta = load_tool_meta(TOOLS_DIR / tool_dir)
    return StructuredTool.from_function(
        func=run_fn,
        name=meta["name"],
        description=meta["description"],
    )


tools = [
    _make_tool("calculator", calculator_run),
    _make_tool("search_knowledge", search_knowledge_run),
]
