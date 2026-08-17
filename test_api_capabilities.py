import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from fastapi.testclient import TestClient

import api_server


class CapabilityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_server.app)

    def test_capabilities_endpoint_exposes_tools_and_skill_extension_type(self):
        response = self.client.get("/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "capability.v1")
        self.assertEqual(payload["supportedTypes"], ["tool", "skill"])

        capabilities = payload["capabilities"]
        capability_ids = [capability["id"] for capability in capabilities]
        self.assertEqual(
            capability_ids,
            ["tool.calculator", "tool.search_knowledge"],
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


if __name__ == "__main__":
    unittest.main()
