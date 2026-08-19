import json
import unittest

from tools import tools
from tools.loader import load_tool_meta


class ToolsLoaderTests(unittest.TestCase):
    def test_load_tool_meta_reads_description(self):
        meta = load_tool_meta(__import__("tools").registry.TOOLS_DIR / "calculator")

        self.assertEqual(meta["name"], "calculator")
        self.assertIn("数学表达式", meta["description"])

    def test_tools_list_has_expected_names(self):
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "calculator",
                "search_knowledge",
                "update_child_profile",
                "record_chinese_literacy_weakness",
                "record_learning_weakness",
            },
        )

    def test_calculator_tool_runs(self):
        calculator = next(tool for tool in tools if tool.name == "calculator")
        self.assertEqual(calculator.invoke({"expression": "2+3"}), "2+3 = 5")

    def test_search_knowledge_tool_runs(self):
        search = next(tool for tool in tools if tool.name == "search_knowledge")
        result = search.invoke({"query": "什么是 langchain"})
        self.assertIn("LangChain", result)

    def test_learning_record_tool_schema_explains_enum_values(self):
        record_tool = next(
            tool for tool in tools if tool.name == "record_chinese_literacy_weakness"
        )

        schema_text = json.dumps(
            record_tool.args_schema.model_json_schema(), ensure_ascii=False
        )

        self.assertIn("pinyin", schema_text)
        self.assertIn("拼音", schema_text)
        self.assertIn("medium", schema_text)
        self.assertIn("中等", schema_text)
        self.assertNotIn("calculation", schema_text)
        self.assertNotIn("计算", schema_text)

    def test_general_learning_tool_schema_explains_subject_and_category_values(self):
        record_tool = next(tool for tool in tools if tool.name == "record_learning_weakness")

        schema_text = json.dumps(
            record_tool.args_schema.model_json_schema(), ensure_ascii=False
        )

        self.assertIn("english", schema_text)
        self.assertIn("英语", schema_text)
        self.assertIn("calculation", schema_text)
        self.assertIn("计算", schema_text)

    def test_update_child_profile_tool_schema_explains_primary_grades(self):
        update_tool = next(tool for tool in tools if tool.name == "update_child_profile")

        schema_text = json.dumps(
            update_tool.args_schema.model_json_schema(), ensure_ascii=False
        )

        self.assertIn("grade_2", schema_text)
        self.assertIn("二年级", schema_text)

    def test_learning_tool_metadata_uses_primary_stage_language(self):
        meta = load_tool_meta(
            __import__("tools").registry.TOOLS_DIR / "record_learning_weakness"
        )

        self.assertIn("小学阶段", meta["description"])
        self.assertNotIn("一年级", meta["description"])


if __name__ == "__main__":
    unittest.main()
