"""从 TOOL.md 读取工具元数据（name、description）。"""

from pathlib import Path


def load_tool_meta(tool_dir: Path) -> dict[str, str]:
    """解析 TOOL.md 的 YAML frontmatter。"""
    tool_md = tool_dir / "TOOL.md"
    text = tool_md.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"{tool_md} 缺少 YAML frontmatter")

    _, frontmatter, _ = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()

    for required in ("name", "description"):
        if required not in meta:
            raise ValueError(f"{tool_md} 缺少必填字段: {required}")

    return meta
