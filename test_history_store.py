import tempfile
import unittest
from pathlib import Path

from history_store import HistoryStore


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "history.db"
        self.store = HistoryStore(self.db_path)
        self.store.initialize()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_sessions_are_isolated_by_user_id_and_sorted_by_updated_at(self):
        older = self.store.create_session(
            "user-a",
            title="older",
            session_id="session-older",
        )
        newer = self.store.create_session(
            "user-a",
            title="newer",
            session_id="session-newer",
        )
        self.store.create_session(
            "user-b",
            title="hidden",
            session_id="session-hidden",
        )

        user_a_sessions = self.store.list_sessions("user-a")

        self.assertEqual(
            [session.session_id for session in user_a_sessions],
            ["session-newer", "session-older"],
        )
        self.assertEqual(
            [session.title for session in user_a_sessions],
            ["newer", "older"],
        )
        self.assertEqual(older.user_id, "user-a")
        self.assertEqual(newer.user_id, "user-a")

    def test_messages_are_ordered_and_session_update_time_moves_forward(self):
        self.store.create_session("user-a", title="chat", session_id="session-a")
        user_message = self.store.save_message(
            "user-a",
            "session-a",
            role="user",
            content="帮我算 2+3",
            message_id="message-user",
        )
        agent_message = self.store.save_message(
            "user-a",
            "session-a",
            role="agent",
            content="2+3 = 5",
            message_id="message-agent",
            run_id="run-a",
        )

        messages = self.store.list_messages("user-a", "session-a")

        self.assertEqual(
            [message.message_id for message in messages],
            ["message-user", "message-agent"],
        )
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[1].role, "agent")
        self.assertEqual(messages[1].run_id, "run-a")
        self.assertLessEqual(user_message.created_at, agent_message.created_at)

    def test_run_events_are_sequenced_and_user_scoped(self):
        self.store.create_session("user-a", title="chat", session_id="session-a")
        user_message = self.store.save_message(
            "user-a",
            "session-a",
            role="user",
            content="search",
            message_id="message-user",
        )
        self.store.create_run(
            "user-a",
            "session-a",
            user_message_id=user_message.message_id,
            prompt="search",
            model="model-a",
            run_id="run-a",
        )

        self.store.append_run_event(
            "user-a",
            "session-a",
            "run-a",
            "stage",
            {"type": "stage", "runId": "run-a"},
        )
        self.store.append_run_event(
            "user-a",
            "session-a",
            "run-a",
            "text",
            {"type": "text", "content": "done", "runId": "run-a"},
        )
        agent_message = self.store.save_message(
            "user-a",
            "session-a",
            role="agent",
            content="done",
            message_id="message-agent",
            run_id="run-a",
        )
        completed = self.store.complete_run(
            "user-a",
            "run-a",
            agent_message.message_id,
        )

        detail = self.store.get_run_detail("user-a", "run-a")
        hidden = self.store.get_run_detail("user-b", "run-a")

        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(detail)
        self.assertEqual(detail.run.run_id, "run-a")
        self.assertEqual([event.sequence for event in detail.events], [1, 2])
        self.assertEqual(detail.events[1].payload["content"], "done")
        self.assertIsNone(hidden)

    def test_failed_run_keeps_safe_error_message(self):
        self.store.create_session("user-a", title="chat", session_id="session-a")
        user_message = self.store.save_message(
            "user-a",
            "session-a",
            role="user",
            content="fail",
            message_id="message-user",
        )
        self.store.create_run(
            "user-a",
            "session-a",
            user_message_id=user_message.message_id,
            prompt="fail",
            model="model-a",
            run_id="run-fail",
        )

        failed = self.store.fail_run(
            "user-a",
            "run-fail",
            "Agent 运行失败，请稍后重试。",
        )
        detail = self.store.get_run_detail("user-a", "run-fail")

        self.assertIsNotNone(failed)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(detail.run.error_message, "Agent 运行失败，请稍后重试。")
        self.assertIsNotNone(detail.run.ended_at)


if __name__ == "__main__":
    unittest.main()
