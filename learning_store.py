from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


DEFAULT_CHILD_ID = "default"
DEFAULT_CHILD_DISPLAY_NAME = "孩子"
DEFAULT_GRADE = "first_grade"
DEFAULT_SUBJECT = "chinese"

WeaknessCategory = Literal[
    "pinyin",
    "character_recognition",
    "reading",
    "expression",
    "learning_habit",
]
WeaknessSeverity = Literal["mild", "medium", "high"]
WeaknessStatus = Literal["active", "improving", "resolved"]

VALID_CATEGORIES = {
    "pinyin",
    "character_recognition",
    "reading",
    "expression",
    "learning_habit",
}
VALID_SEVERITIES = {"mild", "medium", "high"}
VALID_STATUSES = {"active", "improving", "resolved"}


@dataclass(frozen=True)
class ChildProfileRecord:
    user_id: str
    child_id: str
    display_name: str
    grade: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningWeaknessRecord:
    weakness_id: str
    user_id: str
    child_id: str
    subject: str
    grade: str
    category: str
    title: str
    normalized_title: str
    evidence: str
    severity: str
    status: str
    source_run_id: str | None
    created_at: str
    updated_at: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def normalize_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


def validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"unsupported weakness category: {category}")


def validate_severity(severity: str) -> None:
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"unsupported weakness severity: {severity}")


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported weakness status: {status}")


class LearningStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
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

            CREATE TABLE IF NOT EXISTS child_profiles (
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                grade TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, child_id)
            );

            CREATE TABLE IF NOT EXISTS learning_weaknesses (
                weakness_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT NOT NULL,
                category TEXT NOT NULL CHECK (
                    category IN (
                        'pinyin',
                        'character_recognition',
                        'reading',
                        'expression',
                        'learning_habit'
                    )
                ),
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                evidence TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('mild', 'medium', 'high')),
                status TEXT NOT NULL CHECK (status IN ('active', 'improving', 'resolved')),
                source_run_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_weakness_active_unique
                ON learning_weaknesses(
                    user_id, child_id, subject, category, normalized_title
                )
                WHERE status = 'active';

            CREATE INDEX IF NOT EXISTS idx_learning_weaknesses_user_child_status
                ON learning_weaknesses(user_id, child_id, status, updated_at DESC);
            """
        )

    def get_or_create_default_profile(self, user_id: str) -> ChildProfileRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, child_id, display_name, grade, created_at, updated_at
                FROM child_profiles
                WHERE user_id = ? AND child_id = ?
                """,
                (user_id, DEFAULT_CHILD_ID),
            ).fetchone()
            if row is None:
                now = utc_now()
                conn.execute(
                    """
                    INSERT INTO child_profiles(
                        user_id, child_id, display_name, grade, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        DEFAULT_CHILD_ID,
                        DEFAULT_CHILD_DISPLAY_NAME,
                        DEFAULT_GRADE,
                        now,
                        now,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT user_id, child_id, display_name, grade, created_at, updated_at
                    FROM child_profiles
                    WHERE user_id = ? AND child_id = ?
                    """,
                    (user_id, DEFAULT_CHILD_ID),
                ).fetchone()
            return child_profile_from_row(row)

    def list_weaknesses(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
        status: str | None = None,
    ) -> list[LearningWeaknessRecord]:
        params: list[str] = [user_id, child_id]
        where_status = ""
        if status is not None:
            validate_status(status)
            where_status = "AND status = ?"
            params.append(status)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    weakness_id, user_id, child_id, subject, grade, category,
                    title, normalized_title, evidence, severity, status,
                    source_run_id, created_at, updated_at
                FROM learning_weaknesses
                WHERE user_id = ? AND child_id = ?
                {where_status}
                ORDER BY
                    CASE status
                        WHEN 'active' THEN 0
                        WHEN 'improving' THEN 1
                        ELSE 2
                    END ASC,
                    updated_at DESC,
                    weakness_id DESC
                """,
                params,
            ).fetchall()
            return [learning_weakness_from_row(row) for row in rows]

    def upsert_weakness(
        self,
        user_id: str,
        child_id: str,
        category: str,
        title: str,
        evidence: str,
        severity: str,
        source_run_id: str | None = None,
    ) -> tuple[LearningWeaknessRecord, bool]:
        validate_category(category)
        validate_severity(severity)
        normalized_title = normalize_title(title)
        if not normalized_title:
            raise ValueError("weakness title is required")
        if not evidence.strip():
            raise ValueError("weakness evidence is required")

        self.get_or_create_default_profile(user_id)
        now = utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT weakness_id
                FROM learning_weaknesses
                WHERE
                    user_id = ?
                    AND child_id = ?
                    AND subject = ?
                    AND category = ?
                    AND normalized_title = ?
                    AND status = 'active'
                """,
                (user_id, child_id, DEFAULT_SUBJECT, category, normalized_title),
            ).fetchone()

            if existing is not None:
                weakness_id = str(existing["weakness_id"])
                conn.execute(
                    """
                    UPDATE learning_weaknesses
                    SET
                        title = ?,
                        evidence = ?,
                        severity = ?,
                        source_run_id = ?,
                        updated_at = ?
                    WHERE user_id = ? AND weakness_id = ?
                    """,
                    (
                        " ".join(title.strip().split()),
                        evidence.strip(),
                        severity,
                        source_run_id,
                        now,
                        user_id,
                        weakness_id,
                    ),
                )
                conn.commit()
                return self._get_weakness(conn, user_id, weakness_id), False

            weakness_id = new_id("weakness")
            conn.execute(
                """
                INSERT INTO learning_weaknesses(
                    weakness_id, user_id, child_id, subject, grade, category,
                    title, normalized_title, evidence, severity, status,
                    source_run_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    weakness_id,
                    user_id,
                    child_id,
                    DEFAULT_SUBJECT,
                    DEFAULT_GRADE,
                    category,
                    " ".join(title.strip().split()),
                    normalized_title,
                    evidence.strip(),
                    severity,
                    "active",
                    source_run_id,
                    now,
                    now,
                ),
            )
            conn.commit()
            return self._get_weakness(conn, user_id, weakness_id), True

    def update_weakness_status(
        self,
        user_id: str,
        weakness_id: str,
        status: str,
    ) -> LearningWeaknessRecord:
        validate_status(status)
        now = utc_now()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE learning_weaknesses
                SET status = ?, updated_at = ?
                WHERE user_id = ? AND weakness_id = ?
                """,
                (status, now, user_id, weakness_id),
            ).rowcount
            if updated == 0:
                raise LookupError(f"weakness not found: {weakness_id}")
            conn.commit()
            return self._get_weakness(conn, user_id, weakness_id)

    def _get_weakness(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        weakness_id: str,
    ) -> LearningWeaknessRecord:
        row = conn.execute(
            """
            SELECT
                weakness_id, user_id, child_id, subject, grade, category,
                title, normalized_title, evidence, severity, status,
                source_run_id, created_at, updated_at
            FROM learning_weaknesses
            WHERE user_id = ? AND weakness_id = ?
            """,
            (user_id, weakness_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"weakness not found: {weakness_id}")
        return learning_weakness_from_row(row)


def child_profile_from_row(row: sqlite3.Row) -> ChildProfileRecord:
    return ChildProfileRecord(
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        display_name=str(row["display_name"]),
        grade=str(row["grade"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def learning_weakness_from_row(row: sqlite3.Row) -> LearningWeaknessRecord:
    source_run_id = row["source_run_id"]
    return LearningWeaknessRecord(
        weakness_id=str(row["weakness_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        subject=str(row["subject"]),
        grade=str(row["grade"]),
        category=str(row["category"]),
        title=str(row["title"]),
        normalized_title=str(row["normalized_title"]),
        evidence=str(row["evidence"]),
        severity=str(row["severity"]),
        status=str(row["status"]),
        source_run_id=str(source_run_id) if source_run_id is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def serialize_child_profile(record: ChildProfileRecord) -> dict[str, object]:
    return {
        "userId": record.user_id,
        "childId": record.child_id,
        "displayName": record.display_name,
        "grade": record.grade,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def serialize_learning_weakness(record: LearningWeaknessRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "weaknessId": record.weakness_id,
        "userId": record.user_id,
        "childId": record.child_id,
        "subject": record.subject,
        "grade": record.grade,
        "category": record.category,
        "title": record.title,
        "evidence": record.evidence,
        "severity": record.severity,
        "status": record.status,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }
    if record.source_run_id is not None:
        payload["sourceRunId"] = record.source_run_id
    return payload
