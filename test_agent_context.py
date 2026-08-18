import unittest

from agent_context import build_agent_system_prompt
from skills.registry import list_skills


class AgentContextTests(unittest.TestCase):
    def test_system_prompt_includes_registered_skills_and_tool_bindings(self):
        prompt = build_agent_system_prompt(list_skills())

        self.assertIn("Agent Hub", prompt)
        self.assertIn("Math Problem Solver", prompt)
        self.assertIn("calculator", prompt)
        self.assertIn("Knowledge Lookup", prompt)
        self.assertIn("search_knowledge", prompt)
        self.assertNotIn("# Math Problem Solver", prompt)

    def test_system_prompt_respects_explicit_empty_skill_list(self):
        prompt = build_agent_system_prompt([])

        self.assertIn("Available Skills:", prompt)
        self.assertNotIn("Math Problem Solver", prompt)
        self.assertNotIn("Knowledge Lookup", prompt)


if __name__ == "__main__":
    unittest.main()
