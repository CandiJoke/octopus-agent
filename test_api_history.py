import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        agent_message = self.store.save_message(
            "user-a",
            "session-a",
            "agent",
            "hi",
            message_id="message-agent",
            run_id="run-a",
        )
        self.store.complete_run("user-a", "run-a", agent_message.message_id)

        response = self.client.get("/users/user-a/sessions/session-a/messages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                (
                    message["messageId"],
                    message["role"],
                    message.get("runId"),
                    message.get("runStatus"),
                )
                for message in response.json()
            ],
            [
                ("message-user", "user", None, None),
                ("message-agent", "agent", "run-a", "completed"),
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

    def test_delete_session_removes_only_requested_users_session(self):
        self.store.create_session("user-a", session_id="shared-session")
        self.store.create_session("user-b", session_id="shared-session")
        user_a_message = self.store.save_message(
            "user-a",
            "shared-session",
            "user",
            "from user a",
            message_id="message-user-a",
        )
        user_b_message = self.store.save_message(
            "user-b",
            "shared-session",
            "user",
            "from user b",
            message_id="message-user-b",
        )
        self.store.create_run(
            "user-a",
            "shared-session",
            user_a_message.message_id,
            "from user a",
            "model-a",
            run_id="run-user-a",
        )
        self.store.create_run(
            "user-b",
            "shared-session",
            user_b_message.message_id,
            "from user b",
            "model-a",
            run_id="run-user-b",
        )
        self.store.append_run_event(
            "user-a",
            "shared-session",
            "run-user-a",
            "stage",
            {"type": "stage", "runId": "run-user-a"},
        )
        self.store.append_run_event(
            "user-b",
            "shared-session",
            "run-user-b",
            "stage",
            {"type": "stage", "runId": "run-user-b"},
        )

        deleted = self.client.delete("/users/user-a/sessions/shared-session")
        missing = self.client.delete("/users/user-a/sessions/shared-session")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            self.client.get("/users/user-a/sessions/shared-session/messages").json(),
            [],
        )
        self.assertEqual(self.client.get("/users/user-a/runs/run-user-a").status_code, 404)
        user_b_messages = self.client.get(
            "/users/user-b/sessions/shared-session/messages"
        ).json()
        self.assertEqual(user_b_messages[0]["content"], "from user b")
        self.assertEqual(self.client.get("/users/user-b/runs/run-user-b").status_code, 200)

    def test_stream_route_uses_history_store_dependency(self):
        captured = {}

        async def fake_stream_chat_events(req, stream_agent=None, store=None):
            captured["store"] = store
            yield api_server.done_event()

        with mock.patch.object(
            api_server,
            "stream_chat_events",
            fake_stream_chat_events,
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "userId": "user-a",
                    "sessionId": "session-a",
                    "message": "hello",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIs(captured["store"], self.store)


if __name__ == "__main__":
    unittest.main()
