import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from fastapi.testclient import TestClient

import api_server


class CapabilityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_server.app)

    def test_capabilities_endpoint_exposes_tools_and_skills(self):
        response = self.client.get("/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "capability.v1")
        self.assertEqual(payload["supportedTypes"], ["tool", "skill"])

        capabilities = payload["capabilities"]
        capability_ids = [capability["id"] for capability in capabilities]
        self.assertEqual(
            capability_ids,
            [
                "tool.calculator",
                "tool.search_knowledge",
                "tool.update_child_profile",
                "tool.record_chinese_literacy_weakness",
                "tool.record_learning_weakness",
                "skill.math_problem_solver",
                "skill.knowledge_lookup",
                "skill.chinese_literacy_support",
                "skill.primary_learning_support",
            ],
        )

        calculator = capabilities[0]
        self.assertEqual(calculator["type"], "tool")
        self.assertEqual(calculator["name"], "calculator")
        self.assertEqual(calculator["displayName"], "Calculator")
        self.assertEqual(calculator["category"], "基础工具")
        self.assertEqual(calculator["status"], "available")
        self.assertEqual(calculator["source"], "local")
        self.assertTrue(calculator["enabled"])
        self.assertIn("数学计算", calculator["description"])

        update_profile_tool = capabilities[2]
        self.assertEqual(update_profile_tool["type"], "tool")
        self.assertEqual(update_profile_tool["name"], "update_child_profile")
        self.assertEqual(update_profile_tool["category"], "学习画像")

        record_tool = capabilities[3]
        self.assertEqual(record_tool["type"], "tool")
        self.assertEqual(record_tool["name"], "record_chinese_literacy_weakness")
        self.assertEqual(record_tool["category"], "学习记录")

        general_record_tool = capabilities[4]
        self.assertEqual(general_record_tool["type"], "tool")
        self.assertEqual(general_record_tool["name"], "record_learning_weakness")
        self.assertEqual(general_record_tool["category"], "学习记录")

        math_skill = capabilities[5]
        self.assertEqual(math_skill["type"], "skill")
        self.assertEqual(math_skill["name"], "math_problem_solver")
        self.assertEqual(math_skill["displayName"], "Math Problem Solver")
        self.assertEqual(math_skill["category"], "任务技能")
        self.assertEqual(math_skill["status"], "available")
        self.assertEqual(math_skill["source"], "local")
        self.assertTrue(math_skill["enabled"])
        self.assertEqual(math_skill["tools"], ["calculator"])

        chinese_skill = capabilities[7]
        self.assertEqual(chinese_skill["type"], "skill")
        self.assertEqual(chinese_skill["name"], "chinese_literacy_support")
        self.assertEqual(
            chinese_skill["tools"],
            ["record_chinese_literacy_weakness"],
        )

        primary_skill = capabilities[8]
        self.assertEqual(primary_skill["type"], "skill")
        self.assertEqual(primary_skill["name"], "primary_learning_support")
        self.assertEqual(
            primary_skill["tools"],
            ["update_child_profile", "record_learning_weakness"],
        )

    def test_skills_endpoint_lists_skill_details(self):
        response = self.client.get("/skills")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "skill.v1")

        skills = payload["skills"]
        self.assertEqual(
            [skill["id"] for skill in skills],
            [
                "math_problem_solver",
                "knowledge_lookup",
                "chinese_literacy_support",
                "primary_learning_support",
            ],
        )

        math_skill = skills[0]
        self.assertEqual(math_skill["displayName"], "Math Problem Solver")
        self.assertEqual(math_skill["tools"], ["calculator"])
        self.assertIn("数学", math_skill["description"])
        self.assertNotIn("instructions", math_skill)

    def test_skill_detail_endpoint_returns_instructions(self):
        response = self.client.get("/skills/math_problem_solver")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "math_problem_solver")
        self.assertEqual(payload["tools"], ["calculator"])
        self.assertIn("calculator", payload["instructions"])

    def test_skill_detail_endpoint_returns_404_for_unknown_skill(self):
        response = self.client.get("/skills/not_exist")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
