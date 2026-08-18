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
                "skill.math_problem_solver",
                "skill.knowledge_lookup",
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

        math_skill = capabilities[2]
        self.assertEqual(math_skill["type"], "skill")
        self.assertEqual(math_skill["name"], "math_problem_solver")
        self.assertEqual(math_skill["displayName"], "Math Problem Solver")
        self.assertEqual(math_skill["category"], "任务技能")
        self.assertEqual(math_skill["status"], "available")
        self.assertEqual(math_skill["source"], "local")
        self.assertTrue(math_skill["enabled"])
        self.assertEqual(math_skill["tools"], ["calculator"])

    def test_skills_endpoint_lists_skill_details(self):
        response = self.client.get("/skills")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "skill.v1")

        skills = payload["skills"]
        self.assertEqual(
            [skill["id"] for skill in skills],
            ["math_problem_solver", "knowledge_lookup"],
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
