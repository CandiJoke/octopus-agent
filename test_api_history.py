import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from fastapi.testclient import TestClient

import api_server
from history_store import HistoryStore


class HistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.tmpdir.name) / "history.db")
        self.store.initialize()
        api_server.app.dependency_overrides[api_server.get_history_store] = (
            lambda: self.store
        )
        self.client = TestClient(api_server.app)

    def tearDown(self):
        api_server.app.dependency_overrides.clear()
        self.tmpdir.cleanup()

    def test_create_and_list_sessions_for_user(self):
        created = self.client.post("/users/user-a/sessions").json()

        self.assertEqual(created["title"], "新会话")
        self.assertTrue(created["sessionId"].startswith("session_"))

        sessions = self.client.get("/users/user-a/sessions").json()
        hidden = self.client.get("/users/user-b/sessions").json()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["sessionId"], created["sessionId"])
        self.assertEqual(hidden, [])

    def test_messages_endpoint_returns_ordered_messages_with_run_id(self):
        self.store.create_session("user-a", session_id="session-a")
        self.store.save_message(
            "user-a",
            "session-a",
            "user",
            "hello",
            message_id="message-user",
        )
        self.store.save_message(
            "user-a",
            "session-a",
            "agent",
            "hi",
            message_id="message-agent",
            run_id="run-a",
        )

        response = self.client.get("/users/user-a/sessions/session-a/messages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                (message["messageId"], message["role"], message.get("runId"))
                for message in response.json()
            ],
            [
                ("message-user", "user", None),
                ("message-agent", "agent", "run-a"),
            ],
        )

    def test_run_detail_is_user_scoped(self):
        self.store.create_session("user-a", session_id="session-a")
        user_message = self.store.save_message(
            "user-a",
            "session-a",
            "user",
            "hello",
            message_id="message-user",
        )
        self.store.create_run(
            "user-a",
            "session-a",
            user_message.message_id,
            "hello",
            "model-a",
            run_id="run-a",
        )
        self.store.append_run_event(
            "user-a",
            "session-a",
            "run-a",
            "stage",
            {"type": "stage", "runId": "run-a"},
        )

        allowed = self.client.get("/users/user-a/runs/run-a")
        hidden = self.client.get("/users/user-b/runs/run-a")

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["run"]["runId"], "run-a")
        self.assertEqual(allowed.json()["events"][0]["payload"]["runId"], "run-a")
        self.assertEqual(hidden.status_code, 404)


if __name__ == "__main__":
    unittest.main()
