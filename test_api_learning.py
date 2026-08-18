import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from fastapi.testclient import TestClient

import api_server
from learning_store import LearningStore


def make_temp_learning_store(test_case: unittest.TestCase) -> LearningStore:
    temp_dir = tempfile.TemporaryDirectory()
    test_case.addCleanup(temp_dir.cleanup)
    store = LearningStore(Path(temp_dir.name) / "learning.db")
    store.initialize()
    return store


class LearningApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_server.app)
        self.store = make_temp_learning_store(self)
        self.app_override = api_server.app.dependency_overrides
        self.app_override[api_server.get_learning_store] = lambda: self.store

    def tearDown(self):
        self.app_override.clear()

    def test_profile_endpoint_creates_default_profile(self):
        response = self.client.get("/users/user-a/children/default/profile")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["userId"], "user-a")
        self.assertEqual(payload["childId"], "default")
        self.assertEqual(payload["displayName"], "孩子")
        self.assertEqual(payload["grade"], "first_grade")

    def test_create_and_list_weaknesses(self):
        create_response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "b/p/d/q 混淆",
                "evidence": "孩子拼读时经常混淆。",
                "severity": "medium",
                "sourceRunId": "run-a",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertEqual(created["category"], "pinyin")
        self.assertEqual(created["subject"], "chinese")
        self.assertEqual(created["grade"], "first_grade")
        self.assertEqual(created["status"], "active")
        self.assertEqual(created["sourceRunId"], "run-a")

        list_response = self.client.get("/users/user-a/children/default/weaknesses")
        self.assertEqual(list_response.status_code, 200)
        listed = list_response.json()
        self.assertEqual([item["weaknessId"] for item in listed], [created["weaknessId"]])

    def test_create_weakness_accepts_chinese_enum_aliases(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "拼音",
                "title": "声母容易混",
                "evidence": "拼读声母时反复混淆。",
                "severity": "中等",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["category"], "pinyin")
        self.assertEqual(payload["severity"], "medium")

    def test_weaknesses_are_isolated_by_user(self):
        self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "reading",
                "title": "朗读漏字",
                "evidence": "朗读时经常漏字。",
                "severity": "medium",
            },
        )

        response = self.client.get("/users/user-b/children/default/weaknesses")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_invalid_category_returns_422(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "math",
                "title": "计算慢",
                "evidence": "计算慢。",
                "severity": "medium",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
