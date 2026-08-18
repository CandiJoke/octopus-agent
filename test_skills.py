import unittest

from skills.registry import SkillRecord, validate_skill_records


def make_skill(
    skill_id: str,
    name: str | None = None,
    tools: tuple[str, ...] = ("calculator",),
) -> SkillRecord:
    return SkillRecord(
        skill_id=skill_id,
        name=name or skill_id,
        display_name="Test Skill",
        description="测试技能",
        category="任务技能",
        status="available",
        source="local",
        enabled=True,
        tools=tools,
        instructions="Use tools.",
    )


class SkillRegistryTests(unittest.TestCase):
    def test_validate_skill_records_rejects_duplicate_ids(self):
        skills = [make_skill("duplicate"), make_skill("duplicate", name="other")]

        with self.assertRaisesRegex(ValueError, "duplicate skill id"):
            validate_skill_records(skills, {"calculator"})

    def test_validate_skill_records_rejects_duplicate_names(self):
        skills = [make_skill("one", name="same"), make_skill("two", name="same")]

        with self.assertRaisesRegex(ValueError, "duplicate skill name"):
            validate_skill_records(skills, {"calculator"})

    def test_validate_skill_records_rejects_unknown_bound_tools(self):
        skills = [make_skill("bad_tool", tools=("missing_tool",))]

        with self.assertRaisesRegex(ValueError, "unknown bound tool"):
            validate_skill_records(skills, {"calculator"})


if __name__ == "__main__":
    unittest.main()
