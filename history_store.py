from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


MessageRole = Literal["user", "agent"]
RunStatus = Literal["running", "completed", "failed", "stopped"]


@dataclass(frozen=True)
class ChatSessionRecord:
    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ChatMessageRecord:
    message_id: str
    session_id: str
    user_id: str
    role: MessageRole
    content: str
    run_id: str | None
    created_at: str


@dataclass(frozen=True)
class AgentRunRecord:
    run_id: str
    session_id: str
    user_id: str
    user_message_id: str
    agent_message_id: str | None
    status: RunStatus
    prompt: str
    model: str
    started_at: str
    ended_at: str | None
    error_message: str | None


@dataclass(frozen=True)
class AgentRunEventRecord:
    event_id: str
    run_id: str
    session_id: str
    user_id: str
    sequence: int
    event_type: str
    payload: dict[str, object]
    created_at: str


@dataclass(frozen=True)
class RunDetailRecord:
    run: AgentRunRecord
    events: list[AgentRunEventRecord]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def title_from_message(message: str) -> str:
    compact = " ".join(message.strip().split())
    if not compact:
        return "新会话"
    return compact[:28]


class HistoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            if (
                self._needs_user_scoped_session_migration(conn)
                or self._needs_run_status_migration(conn)
            ):
                self._migrate_to_current_schema(conn)
            self._create_schema(conn)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
                ON chat_sessions(user_id, updated_at DESC, session_id DESC);

            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
                content TEXT NOT NULL,
                run_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id, session_id)
                    REFERENCES chat_sessions(user_id, session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                ON chat_messages(user_id, session_id, created_at ASC, message_id ASC);

            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_message_id TEXT NOT NULL,
                agent_message_id TEXT,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'stopped')),
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                error_message TEXT,
                FOREIGN KEY(user_id, session_id)
                    REFERENCES chat_sessions(user_id, session_id),
                FOREIGN KEY(user_message_id) REFERENCES chat_messages(message_id)
            );
            CREATE INDEX IF NOT EXISTS idx_agent_runs_user_started
                ON agent_runs(user_id, started_at DESC);

            CREATE TABLE IF NOT EXISTS agent_run_events (
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
            CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_run_events_sequence
                ON agent_run_events(run_id, sequence);
            """
        )

    def _needs_user_scoped_session_migration(self, conn: sqlite3.Connection) -> bool:
        if not self._table_exists(conn, "chat_sessions"):
            return False
        primary_key_columns = self._primary_key_columns(conn, "chat_sessions")
        return primary_key_columns != ["user_id", "session_id"]

    def _needs_run_status_migration(self, conn: sqlite3.Connection) -> bool:
        if not self._table_exists(conn, "agent_runs"):
            return False
        row = conn.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'agent_runs'
            """,
        ).fetchone()
        schema_sql = str(row["sql"] or "") if row is not None else ""
        return "'stopped'" not in schema_sql

    def _migrate_to_current_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys=OFF")
        for index_name in (
            "idx_chat_sessions_user_updated",
            "idx_chat_messages_session_created",
            "idx_agent_runs_user_started",
            "idx_agent_run_events_sequence",
        ):
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")

        legacy_tables = [
            table_name
            for table_name in (
                "agent_run_events",
                "agent_runs",
                "chat_messages",
                "chat_sessions",
            )
            if self._table_exists(conn, table_name)
        ]
        for table_name in legacy_tables:
            conn.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_legacy")

        self._create_schema(conn)

        if "chat_sessions" in legacy_tables:
            conn.execute(
                """
                INSERT INTO chat_sessions(session_id, user_id, title, created_at, updated_at)
                SELECT session_id, user_id, title, created_at, updated_at
                FROM chat_sessions_legacy
                """
            )
        if "chat_messages" in legacy_tables:
            conn.execute(
                """
                INSERT INTO chat_messages(
                    message_id, session_id, user_id, role, content, run_id, created_at
                )
                SELECT message_id, session_id, user_id, role, content, run_id, created_at
                FROM chat_messages_legacy
                """
            )
        if "agent_runs" in legacy_tables:
            conn.execute(
                """
                INSERT INTO agent_runs(
                    run_id, session_id, user_id, user_message_id, agent_message_id,
                    status, prompt, model, started_at, ended_at, error_message
                )
                SELECT
                    run_id, session_id, user_id, user_message_id, agent_message_id,
                    status, prompt, model, started_at, ended_at, error_message
                FROM agent_runs_legacy
                """
            )
        if "agent_run_events" in legacy_tables:
            conn.execute(
                """
                INSERT INTO agent_run_events(
                    event_id, run_id, session_id, user_id, sequence,
                    event_type, payload_json, created_at
                )
                SELECT
                    event_id, run_id, session_id, user_id, sequence,
                    event_type, payload_json, created_at
                FROM agent_run_events_legacy
                """
            )

        for table_name in legacy_tables:
            conn.execute(f"DROP TABLE {table_name}_legacy")
        conn.execute("PRAGMA foreign_keys=ON")

    def _migrate_to_user_scoped_sessions(self, conn: sqlite3.Connection) -> None:
        self._migrate_to_current_schema(conn)

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def _primary_key_columns(
        self,
        conn: sqlite3.Connection,
        table_name: str,
    ) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        primary_key_rows = [row for row in rows if row["pk"]]
        primary_key_rows.sort(key=lambda row: row["pk"])
        return [row["name"] for row in primary_key_rows]

    def create_session(
        self,
        user_id: str,
        title: str = "新会话",
        session_id: str | None = None,
    ) -> ChatSessionRecord:
        now = utc_now()
        record_id = session_id or new_id("session")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions(session_id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record_id, user_id, title, now, now),
            )
            conn.commit()
        return ChatSessionRecord(record_id, user_id, title, now, now)

    def ensure_session(
        self,
        user_id: str,
        session_id: str,
        title: str = "新会话",
    ) -> ChatSessionRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        if row is not None:
            return self._session_from_row(row)
        return self.create_session(user_id, title=title, session_id=session_id)

    def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[ChatSessionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC, created_at DESC, session_id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def delete_session(self, user_id: str, session_id: str) -> bool:
        with self._connect() as conn:
            session_row = conn.execute(
                "SELECT 1 FROM chat_sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
            if session_row is None:
                return False

            run_rows = conn.execute(
                """
                SELECT run_id FROM agent_runs
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            ).fetchall()
            run_ids = [row["run_id"] for row in run_rows]
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                conn.execute(
                    f"""
                    DELETE FROM agent_run_events
                    WHERE user_id = ? AND run_id IN ({placeholders})
                    """,
                    (user_id, *run_ids),
                )

            conn.execute(
                """
                DELETE FROM agent_runs
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            )
            conn.execute(
                """
                DELETE FROM chat_messages
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            )
            conn.execute(
                """
                DELETE FROM chat_sessions
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            )
            conn.commit()
        return True

    def save_message(
        self,
        user_id: str,
        session_id: str,
        role: MessageRole,
        content: str,
        message_id: str | None = None,
        run_id: str | None = None,
    ) -> ChatMessageRecord:
        now = utc_now()
        record_id = message_id or new_id("message")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages(
                    message_id, session_id, user_id, role, content, run_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, session_id, user_id, role, content, run_id, now),
            )
            conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = ?
                WHERE user_id = ? AND session_id = ?
                """,
                (now, user_id, session_id),
            )
            conn.commit()
        return ChatMessageRecord(
            record_id,
            session_id,
            user_id,
            role,
            content,
            run_id,
            now,
        )

    def list_messages(
        self,
        user_id: str,
        session_id: str,
    ) -> list[ChatMessageRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE user_id = ? AND session_id = ?
                ORDER BY created_at ASC, message_id ASC
                """,
                (user_id, session_id),
            ).fetchall()
        return [self._message_from_row(row) for row in rows]

    def create_run(
        self,
        user_id: str,
        session_id: str,
        user_message_id: str,
        prompt: str,
        model: str,
        run_id: str | None = None,
    ) -> AgentRunRecord:
        now = utc_now()
        record_id = run_id or new_id("run")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs(
                    run_id, session_id, user_id, user_message_id, agent_message_id,
                    status, prompt, model, started_at, ended_at, error_message
                )
                VALUES (?, ?, ?, ?, NULL, 'running', ?, ?, ?, NULL, NULL)
                """,
                (record_id, session_id, user_id, user_message_id, prompt, model, now),
            )
            conn.commit()
        return AgentRunRecord(
            record_id,
            session_id,
            user_id,
            user_message_id,
            None,
            "running",
            prompt,
            model,
            now,
            None,
            None,
        )

    def append_run_event(
        self,
        user_id: str,
        session_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> AgentRunEventRecord:
        now = utc_now()
        event_id = new_id("event")
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM agent_run_events
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            sequence = int(row["next_sequence"])
            conn.execute(
                """
                INSERT INTO agent_run_events(
                    event_id, run_id, session_id, user_id, sequence,
                    event_type, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    run_id,
                    session_id,
                    user_id,
                    sequence,
                    event_type,
                    payload_json,
                    now,
                ),
            )
            conn.commit()
        return AgentRunEventRecord(
            event_id,
            run_id,
            session_id,
            user_id,
            sequence,
            event_type,
            payload,
            now,
        )

    def complete_run(
        self,
        user_id: str,
        run_id: str,
        agent_message_id: str,
    ) -> AgentRunRecord | None:
        return self._finish_run(
            user_id,
            run_id,
            "completed",
            agent_message_id=agent_message_id,
            error_message=None,
        )

    def fail_run(
        self,
        user_id: str,
        run_id: str,
        error_message: str,
    ) -> AgentRunRecord | None:
        return self._finish_run(
            user_id,
            run_id,
            "failed",
            agent_message_id=None,
            error_message=error_message,
        )

    def stop_run(
        self,
        user_id: str,
        run_id: str,
        error_message: str,
        agent_message_id: str | None = None,
    ) -> AgentRunRecord | None:
        return self._finish_run(
            user_id,
            run_id,
            "stopped",
            agent_message_id=agent_message_id,
            error_message=error_message,
        )

    def list_run_statuses(
        self,
        user_id: str,
        run_ids: list[str],
    ) -> dict[str, RunStatus]:
        unique_run_ids = list(dict.fromkeys(run_ids))
        if not unique_run_ids:
            return {}

        placeholders = ",".join("?" for _ in unique_run_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT run_id, status FROM agent_runs
                WHERE user_id = ? AND run_id IN ({placeholders})
                """,
                (user_id, *unique_run_ids),
            ).fetchall()
        return {row["run_id"]: row["status"] for row in rows}

    def get_run_detail(
        self,
        user_id: str,
        run_id: str,
    ) -> RunDetailRecord | None:
        with self._connect() as conn:
            run_row = conn.execute(
                "SELECT * FROM agent_runs WHERE user_id = ? AND run_id = ?",
                (user_id, run_id),
            ).fetchone()
            if run_row is None:
                return None
            event_rows = conn.execute(
                """
                SELECT * FROM agent_run_events
                WHERE user_id = ? AND run_id = ?
                ORDER BY sequence ASC
                """,
                (user_id, run_id),
            ).fetchall()
        return RunDetailRecord(
            run=self._run_from_row(run_row),
            events=[self._event_from_row(row) for row in event_rows],
        )

    def _finish_run(
        self,
        user_id: str,
        run_id: str,
        status: RunStatus,
        agent_message_id: str | None,
        error_message: str | None,
    ) -> AgentRunRecord | None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, agent_message_id = ?, ended_at = ?, error_message = ?
                WHERE user_id = ? AND run_id = ? AND status = 'running'
                """,
                (status, agent_message_id, now, error_message, user_id, run_id),
            )
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE user_id = ? AND run_id = ?",
                (user_id, run_id),
            ).fetchone()
            conn.commit()
        return self._run_from_row(row) if row is not None else None

    def _session_from_row(self, row: sqlite3.Row) -> ChatSessionRecord:
        return ChatSessionRecord(
            row["session_id"],
            row["user_id"],
            row["title"],
            row["created_at"],
            row["updated_at"],
        )

    def _message_from_row(self, row: sqlite3.Row) -> ChatMessageRecord:
        return ChatMessageRecord(
            row["message_id"],
            row["session_id"],
            row["user_id"],
            row["role"],
            row["content"],
            row["run_id"],
            row["created_at"],
        )

    def _run_from_row(self, row: sqlite3.Row) -> AgentRunRecord:
        return AgentRunRecord(
            row["run_id"],
            row["session_id"],
            row["user_id"],
            row["user_message_id"],
            row["agent_message_id"],
            row["status"],
            row["prompt"],
            row["model"],
            row["started_at"],
            row["ended_at"],
            row["error_message"],
        )

    def _event_from_row(self, row: sqlite3.Row) -> AgentRunEventRecord:
        return AgentRunEventRecord(
            row["event_id"],
            row["run_id"],
            row["session_id"],
            row["user_id"],
            row["sequence"],
            row["event_type"],
            json.loads(row["payload_json"]),
            row["created_at"],
        )
