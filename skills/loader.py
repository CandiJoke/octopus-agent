"""Load local skill metadata from SKILL.md files."""

from pathlib import Path


def load_skill_document(skill_dir: Path) -> tuple[dict[str, str], str]:
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"{skill_md} 缺少 YAML frontmatter")

    _, frontmatter, body = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()

    for required in (
        "id",
        "name",
        "display_name",
        "description",
        "category",
        "status",
        "source",
        "enabled",
        "tools",
    ):
        if required not in meta:
            raise ValueError(f"{skill_md} 缺少必填字段: {required}")

    return meta, body.strip()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())
