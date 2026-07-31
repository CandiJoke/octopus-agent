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
        self.assertEqual(names, {"calculator", "search_knowledge"})

    def test_calculator_tool_runs(self):
        calculator = next(tool for tool in tools if tool.name == "calculator")
        self.assertEqual(calculator.invoke({"expression": "2+3"}), "2+3 = 5")

    def test_search_knowledge_tool_runs(self):
        search = next(tool for tool in tools if tool.name == "search_knowledge")
        result = search.invoke({"query": "什么是 langchain"})
        self.assertIn("LangChain", result)


if __name__ == "__main__":
    unittest.main()
