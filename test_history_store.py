import sqlite3
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

    def test_same_session_id_can_be_reused_by_different_users(self):
        self.store.create_session(
            "user-a",
            title="user a shared",
            session_id="shared-session",
        )
        self.store.create_session(
            "user-b",
            title="user b shared",
            session_id="shared-session",
        )

        self.store.save_message(
            "user-a",
            "shared-session",
            role="user",
            content="from user a",
            message_id="message-user-a",
        )
        self.store.save_message(
            "user-b",
            "shared-session",
            role="user",
            content="from user b",
            message_id="message-user-b",
        )

        user_a_messages = self.store.list_messages("user-a", "shared-session")
        user_b_messages = self.store.list_messages("user-b", "shared-session")

        self.assertEqual([message.content for message in user_a_messages], ["from user a"])
        self.assertEqual([message.content for message in user_b_messages], ["from user b"])

    def test_initialize_migrates_legacy_global_session_schema(self):
        legacy_path = Path(self.tmpdir.name) / "legacy.db"
        with sqlite3.connect(legacy_path) as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys=ON;

                CREATE TABLE chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
                    content TEXT NOT NULL,
                    run_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                );
                CREATE TABLE agent_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_message_id TEXT NOT NULL,
                    agent_message_id TEXT,
                    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    error_message TEXT,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id),
                    FOREIGN KEY(user_message_id) REFERENCES chat_messages(message_id)
                );
                CREATE TABLE agent_run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
                );

                INSERT INTO chat_sessions
                    (session_id, user_id, title, created_at, updated_at)
                VALUES
                    ('shared-session', 'user-a', 'legacy', '2026-08-17T00:00:00Z', '2026-08-17T00:00:00Z');
                INSERT INTO chat_messages
                    (message_id, session_id, user_id, role, content, run_id, created_at)
                VALUES
                    ('message-user', 'shared-session', 'user-a', 'user', 'legacy hello', NULL, '2026-08-17T00:00:01Z');
                INSERT INTO agent_runs
                    (
                        run_id, session_id, user_id, user_message_id, agent_message_id,
                        status, prompt, model, started_at, ended_at, error_message
                    )
                VALUES
                    (
                        'run-legacy', 'shared-session', 'user-a', 'message-user', NULL,
                        'running', 'legacy hello', 'model-a', '2026-08-17T00:00:01Z', NULL, NULL
                    );
                INSERT INTO agent_run_events
                    (
                        event_id, run_id, session_id, user_id, sequence,
                        event_type, payload_json, created_at
                    )
                VALUES
                    (
                        'event-legacy', 'run-legacy', 'shared-session', 'user-a', 1,
                        'stage', '{"type": "stage"}', '2026-08-17T00:00:02Z'
                    );
                """
            )

        migrated_store = HistoryStore(legacy_path)
        migrated_store.initialize()
        migrated_store.create_session("user-b", session_id="shared-session")

        user_a_messages = migrated_store.list_messages("user-a", "shared-session")
        user_b_sessions = migrated_store.list_sessions("user-b")
        run_detail = migrated_store.get_run_detail("user-a", "run-legacy")

        self.assertEqual([message.content for message in user_a_messages], ["legacy hello"])
        self.assertEqual(user_b_sessions[0].session_id, "shared-session")
        self.assertEqual(run_detail.events[0].event_id, "event-legacy")

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
