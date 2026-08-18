# First Grade Chinese Literacy Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build V1 of a first-grade Chinese literacy support assistant that records Chinese learning weak spots from natural chat and shows a lightweight learning profile.

**Architecture:** Add a separate learning-domain store beside chat history, expose profile and weakness APIs from FastAPI, add a request-scoped Agent tool for recording weaknesses, then surface the records in the frontend right rail. Keep learning records out of chat history while linking records back to Agent runs with `sourceRunId`.

**Tech Stack:** Python 3.11, FastAPI, SQLite, LangChain `StructuredTool`, LangChain Agent `system_prompt`, React 19, TypeScript, Vite, oxlint, contract tests.

## Global Constraints

- API JSON uses camelCase: `userId`, `childId`, `weaknessId`, `createdAt`, `updatedAt`.
- Python and SQLite use snake_case: `user_id`, `child_id`, `weakness_id`, `created_at`, `updated_at`.
- V1 uses `childId = default`.
- V1 profile display name defaults to `孩子`.
- Do not require or store a real child name in V1.
- `userId` continues to be the product identity boundary.
- `childId` belongs to the learning domain, not the auth domain.
- V1 subject is always `chinese`; grade is always `first_grade`.
- Do not ask for or store sensitive family, medical, or school identity data.
- Avoid diagnosis-like labels such as `障碍` or `疾病`.
- Weekly plans, mistake notebook, exercise bank, multiple children, and textbook import are out of V1 implementation scope.
- Backend commits are pushed to `origin/main`; frontend commits remain local unless explicitly requested.
- Frontend commands use Node 20.20.0 via `source ~/.nvm/nvm.sh && nvm use 20.20.0`.

---

## File Structure

Backend files:

- Create `learning_store.py`: SQLite repository for child profiles and Chinese weakness records.
- Create `test_learning_store.py`: unit tests for schema, lazy profile creation, upsert behavior, validation, sorting, and user isolation.
- Create `learning_context.py`: request-scoped context for Agent tools to read `user_id`, `child_id`, and `source_run_id` without exposing them to the model.
- Create `test_learning_context.py`: tests for setting, reading, resetting, and missing context.
- Create `tools/record_chinese_literacy_weakness/TOOL.md`: model-visible metadata for the recording tool.
- Create `tools/record_chinese_literacy_weakness/record_chinese_literacy_weakness.py`: tool implementation that reads injected context and writes through `LearningStore`.
- Modify `tools/registry.py`: register the recording tool as a `StructuredTool`.
- Modify `skills/registry.py`: add `chinese_literacy_support`.
- Create `skills/chinese_literacy_support/SKILL.md`: Agent guidance for first-grade Chinese literacy support.
- Modify `agent_context.py`: include the new skill in the system prompt through the existing registry.
- Modify `api_server.py`: instantiate `LearningStore`, expose learning APIs, and set request context around Agent execution.
- Modify `test_api_capabilities.py`: assert the new skill appears in `/skills` and `/capabilities`.
- Modify `test_api_stream_events.py`: assert stream runs set learning context before tool-capable Agent execution.
- Create `test_api_learning.py`: API tests for profile and weakness endpoints.
- Modify `.env.example` only if a new runtime config is introduced; V1 should avoid new config.

Frontend files:

- Create `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`: API client and DTOs for profile and weaknesses.
- Create `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningProfilePanel.tsx`: right-rail learning profile component.
- Create `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`: API path and render contracts.
- Modify `/Users/caisufang/projects/agent-hub-frontend/package.json`: include the learning contract in `test:contracts`.
- Modify `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`: load learning profile and refresh after recording or chat completion.
- Modify `/Users/caisufang/projects/agent-hub-frontend/src/App.css`: add learning panel styles and compose it with the existing capability panel.

---

### Task 1: Backend Learning Store

**Files:**
- Create: `learning_store.py`
- Create: `test_learning_store.py`

**Interfaces:**
- Produces: `LearningStore(db_path: str | Path)`
- Produces: `LearningStore.initialize() -> None`
- Produces: `LearningStore.get_or_create_default_profile(user_id: str) -> ChildProfileRecord`
- Produces: `LearningStore.list_weaknesses(user_id: str, child_id: str = "default", status: str | None = None) -> list[LearningWeaknessRecord]`
- Produces: `LearningStore.upsert_weakness(user_id: str, child_id: str, category: str, title: str, evidence: str, severity: str, source_run_id: str | None = None) -> tuple[LearningWeaknessRecord, bool]`
- Produces: `serialize_child_profile(record: ChildProfileRecord) -> dict[str, object]`
- Produces: `serialize_learning_weakness(record: LearningWeaknessRecord) -> dict[str, object]`
- Consumes: `new_id(prefix: str)` pattern from `history_store.py`.

- [ ] **Step 1: Write failing store tests**

Create `test_learning_store.py`:

```python
import tempfile
import unittest
from pathlib import Path

from learning_store import (
    DEFAULT_CHILD_ID,
    DEFAULT_GRADE,
    DEFAULT_SUBJECT,
    LearningStore,
    serialize_child_profile,
    serialize_learning_weakness,
)


class LearningStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "learning.db"
        self.store = LearningStore(self.db_path)
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_profile_is_created_lazily(self):
        profile = self.store.get_or_create_default_profile("user-a")

        self.assertEqual(profile.user_id, "user-a")
        self.assertEqual(profile.child_id, DEFAULT_CHILD_ID)
        self.assertEqual(profile.display_name, "孩子")
        self.assertEqual(profile.grade, DEFAULT_GRADE)

        same_profile = self.store.get_or_create_default_profile("user-a")
        self.assertEqual(same_profile.created_at, profile.created_at)

    def test_profile_serializes_to_camel_case(self):
        profile = self.store.get_or_create_default_profile("user-a")

        payload = serialize_child_profile(profile)

        self.assertEqual(payload["userId"], "user-a")
        self.assertEqual(payload["childId"], DEFAULT_CHILD_ID)
        self.assertEqual(payload["displayName"], "孩子")
        self.assertEqual(payload["grade"], DEFAULT_GRADE)
        self.assertIn("createdAt", payload)
        self.assertIn("updatedAt", payload)

    def test_upsert_weakness_creates_active_chinese_record(self):
        record, created = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title="b/p/d/q 混淆",
            evidence="孩子拼读时经常把 b、p、d、q 搞混。",
            severity="medium",
            source_run_id="run-a",
        )

        self.assertTrue(created)
        self.assertEqual(record.subject, DEFAULT_SUBJECT)
        self.assertEqual(record.grade, DEFAULT_GRADE)
        self.assertEqual(record.status, "active")
        self.assertEqual(record.source_run_id, "run-a")

        listed = self.store.list_weaknesses("user-a")
        self.assertEqual([item.weakness_id for item in listed], [record.weakness_id])

    def test_duplicate_active_weakness_updates_existing_record(self):
        first, created_first = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title=" b/p/d/q   混淆 ",
            evidence="第一次反馈。",
            severity="mild",
        )
        second, created_second = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title="b/p/d/q 混淆",
            evidence="第二次反馈，拼读仍然慢。",
            severity="high",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(second.weakness_id, first.weakness_id)
        self.assertEqual(second.evidence, "第二次反馈，拼读仍然慢。")
        self.assertEqual(second.severity, "high")
        self.assertEqual(len(self.store.list_weaknesses("user-a")), 1)

    def test_weaknesses_are_isolated_by_user(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="reading",
            title="朗读漏字",
            evidence="朗读短句时漏字。",
            severity="medium",
        )

        self.assertEqual(len(self.store.list_weaknesses("user-b")), 0)

    def test_invalid_enum_values_are_rejected(self):
        invalid_cases = [
            {"category": "math", "severity": "medium"},
            {"category": "pinyin", "severity": "urgent"},
        ]

        for case in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.store.upsert_weakness(
                        "user-a",
                        DEFAULT_CHILD_ID,
                        category=case["category"],
                        title="测试",
                        evidence="测试",
                        severity=case["severity"],
                    )

    def test_resolved_records_can_be_filtered_out(self):
        record, _ = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="character_recognition",
            title="识字慢",
            evidence="见过几次的字仍然容易忘。",
            severity="medium",
        )
        self.store.update_weakness_status("user-a", record.weakness_id, "resolved")

        self.assertEqual(len(self.store.list_weaknesses("user-a")), 1)
        self.assertEqual(len(self.store.list_weaknesses("user-a", status="active")), 0)

    def test_weakness_serializes_to_camel_case(self):
        record, _ = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="expression",
            title="表达不完整",
            evidence="讲图片内容时句子不完整。",
            severity="mild",
            source_run_id="run-a",
        )

        payload = serialize_learning_weakness(record)

        self.assertEqual(payload["weaknessId"], record.weakness_id)
        self.assertEqual(payload["userId"], "user-a")
        self.assertEqual(payload["childId"], DEFAULT_CHILD_ID)
        self.assertEqual(payload["subject"], DEFAULT_SUBJECT)
        self.assertEqual(payload["grade"], DEFAULT_GRADE)
        self.assertEqual(payload["sourceRunId"], "run-a")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the store tests to verify failure**

Run:

```bash
.venv/bin/python -m unittest test_learning_store.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'learning_store'`.

- [ ] **Step 3: Implement `learning_store.py`**

Create `learning_store.py` with:

```python
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
                ON learning_weaknesses(user_id, child_id, subject, category, normalized_title)
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
```

- [ ] **Step 4: Run the store tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest test_learning_store.py
```

Expected: PASS, all store tests green.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add learning_store.py test_learning_store.py
git commit -m "feat: add learning weakness store"
```

Expected: commit created.

---

### Task 2: Backend Learning APIs

**Files:**
- Create: `test_api_learning.py`
- Modify: `api_server.py`

**Interfaces:**
- Consumes: `LearningStore`, `serialize_child_profile`, `serialize_learning_weakness`.
- Produces: `learning_store = LearningStore(DB_PATH)`.
- Produces: `get_learning_store() -> LearningStore`.
- Produces: `LearningWeaknessRequest(BaseModel)`.
- Produces: `GET /users/{user_id}/children/default/profile`.
- Produces: `GET /users/{user_id}/children/default/weaknesses`.
- Produces: `POST /users/{user_id}/children/default/weaknesses`.

- [ ] **Step 1: Write failing API tests**

Create `test_api_learning.py`:

```python
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
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
.venv/bin/python -m unittest test_api_learning.py
```

Expected: FAIL because `api_server.get_learning_store` or learning routes do not exist.

- [ ] **Step 3: Modify `api_server.py` imports and store setup**

Add imports near the existing `history_store` imports:

```python
from learning_store import (
    DEFAULT_CHILD_ID,
    VALID_CATEGORIES,
    VALID_SEVERITIES,
    LearningStore,
    serialize_child_profile,
    serialize_learning_weakness,
)
```

After `history_store.initialize()` add:

```python
learning_store = LearningStore(DB_PATH)
learning_store.initialize()
```

After `get_history_store()` add:

```python
def get_learning_store() -> LearningStore:
    return learning_store
```

- [ ] **Step 4: Add the request model**

In `api_server.py`, after `ChatResponse` add:

```python
class LearningWeaknessRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: str
    title: str
    evidence: str
    severity: str
    source_run_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceRunId", "source_run_id"),
    )
```

- [ ] **Step 5: Add learning routes**

Add routes after `/skills/{skill_id}` and before session routes:

```python
@app.get("/users/{user_id}/children/default/profile")
def get_default_child_profile(
    user_id: str,
    store: LearningStore = Depends(get_learning_store),
):
    return serialize_child_profile(store.get_or_create_default_profile(user_id))


@app.get("/users/{user_id}/children/default/weaknesses")
def list_default_child_weaknesses(
    user_id: str,
    status: str | None = None,
    store: LearningStore = Depends(get_learning_store),
):
    try:
        records = store.list_weaknesses(user_id, DEFAULT_CHILD_ID, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [serialize_learning_weakness(record) for record in records]


@app.post("/users/{user_id}/children/default/weaknesses")
def record_default_child_weakness(
    user_id: str,
    req: LearningWeaknessRequest,
    store: LearningStore = Depends(get_learning_store),
):
    if req.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail="Unsupported weakness category")
    if req.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail="Unsupported weakness severity")

    try:
        record, _ = store.upsert_weakness(
            user_id,
            DEFAULT_CHILD_ID,
            category=req.category,
            title=req.title,
            evidence=req.evidence,
            severity=req.severity,
            source_run_id=req.source_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_learning_weakness(record)
```

- [ ] **Step 6: Run API tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest test_api_learning.py test_learning_store.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add api_server.py test_api_learning.py
git commit -m "feat: expose learning profile APIs"
```

Expected: commit created.

---

### Task 3: Agent Recording Tool And Chinese Literacy Skill

**Files:**
- Create: `learning_context.py`
- Create: `test_learning_context.py`
- Create: `tools/record_chinese_literacy_weakness/TOOL.md`
- Create: `tools/record_chinese_literacy_weakness/record_chinese_literacy_weakness.py`
- Modify: `tools/registry.py`
- Create: `skills/chinese_literacy_support/SKILL.md`
- Modify: `skills/registry.py`
- Modify: `api_server.py`
- Modify: `test_api_capabilities.py`
- Modify: `test_api_stream_events.py`
- Create: `test_learning_tool.py`

**Interfaces:**
- Consumes: `LearningStore.upsert_weakness(...)`.
- Produces: `LearningContext(user_id: str, child_id: str, source_run_id: str | None)`.
- Produces: `learning_run_context(user_id: str, child_id: str, source_run_id: str | None)`.
- Produces: `current_learning_context() -> LearningContext | None`.
- Produces: tool function `run(category: str, title: str, evidence: str, severity: str) -> str`.
- Produces: API runtime sets context around `agent.invoke` and `active_agent.astream_events`.

- [ ] **Step 1: Write failing context tests**

Create `test_learning_context.py`:

```python
import unittest

from learning_context import current_learning_context, learning_run_context


class LearningContextTests(unittest.TestCase):
    def test_context_is_available_inside_scope_and_reset_after(self):
        self.assertIsNone(current_learning_context())

        with learning_run_context("user-a", "default", "run-a"):
            context = current_learning_context()
            self.assertIsNotNone(context)
            self.assertEqual(context.user_id, "user-a")
            self.assertEqual(context.child_id, "default")
            self.assertEqual(context.source_run_id, "run-a")

        self.assertIsNone(current_learning_context())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write failing tool tests**

Create `test_learning_tool.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_context import learning_run_context
from learning_store import LearningStore
from tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness import run


class LearningToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = LearningStore(Path(self.temp_dir.name) / "learning.db")
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tool_records_weakness_from_injected_context(self):
        with (
            patch(
                "tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-a"),
        ):
            result = run(
                category="pinyin",
                title="b/p/d/q 混淆",
                evidence="孩子拼音拼读时经常混淆。",
                severity="medium",
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_run_id, "run-a")

    def test_tool_refuses_to_record_without_context(self):
        with patch(
            "tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness.learning_store",
            self.store,
        ):
            result = run(
                category="pinyin",
                title="b/p/d/q 混淆",
                evidence="孩子拼音拼读时经常混淆。",
                severity="medium",
            )

        self.assertIn("暂时无法记录", result)
        self.assertEqual(self.store.list_weaknesses("user-a"), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Update capability tests to expect the new tool and skill**

Modify `test_api_capabilities.py` expected capability IDs to:

```python
[
    "tool.calculator",
    "tool.search_knowledge",
    "tool.record_chinese_literacy_weakness",
    "skill.math_problem_solver",
    "skill.knowledge_lookup",
    "skill.chinese_literacy_support",
]
```

Add assertions:

```python
record_tool = capabilities[2]
self.assertEqual(record_tool["type"], "tool")
self.assertEqual(record_tool["name"], "record_chinese_literacy_weakness")
self.assertEqual(record_tool["category"], "学习记录")

chinese_skill = capabilities[5]
self.assertEqual(chinese_skill["type"], "skill")
self.assertEqual(chinese_skill["name"], "chinese_literacy_support")
self.assertEqual(chinese_skill["tools"], ["record_chinese_literacy_weakness"])
```

Modify the `/skills` expected IDs to:

```python
["math_problem_solver", "knowledge_lookup", "chinese_literacy_support"]
```

- [ ] **Step 4: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m unittest test_learning_context.py test_learning_tool.py test_api_capabilities.py
```

Expected: FAIL because context, tool package, registry entries, and skill do not exist.

- [ ] **Step 5: Implement `learning_context.py`**

Create `learning_context.py`:

```python
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class LearningContext:
    user_id: str
    child_id: str
    source_run_id: str | None


_learning_context: ContextVar[LearningContext | None] = ContextVar(
    "learning_context",
    default=None,
)


def current_learning_context() -> LearningContext | None:
    return _learning_context.get()


@contextmanager
def learning_run_context(
    user_id: str,
    child_id: str,
    source_run_id: str | None,
) -> Iterator[None]:
    token = _learning_context.set(
        LearningContext(
            user_id=user_id,
            child_id=child_id,
            source_run_id=source_run_id,
        )
    )
    try:
        yield
    finally:
        _learning_context.reset(token)
```

- [ ] **Step 6: Implement tool metadata and run function**

Create `tools/record_chinese_literacy_weakness/TOOL.md`:

```markdown
---
name: record_chinese_literacy_weakness
description: 记录一年级语文学习薄弱点。仅当家长明确描述孩子在拼音、识字、朗读、表达或学习习惯上的具体问题时使用。输入分类、标题、依据和严重程度。
---

# Record Chinese Literacy Weakness

- **输入**：category、title、evidence、severity
- **输出**：记录或更新结果
- **限制**：不接收 userId、childId 或数据库 ID，这些由后端运行上下文注入
```

Create `tools/record_chinese_literacy_weakness/record_chinese_literacy_weakness.py`:

```python
from __future__ import annotations

from agent_console import DB_PATH
from learning_context import current_learning_context
from learning_store import LearningStore


learning_store = LearningStore(DB_PATH)
learning_store.initialize()


def run(category: str, title: str, evidence: str, severity: str) -> str:
    context = current_learning_context()
    if context is None:
        return "暂时无法记录薄弱点：缺少当前用户上下文。"

    try:
        record, created = learning_store.upsert_weakness(
            context.user_id,
            context.child_id,
            category=category,
            title=title,
            evidence=evidence,
            severity=severity,
            source_run_id=context.source_run_id,
        )
    except Exception:
        return "暂时无法记录薄弱点，请稍后重试。"

    action = "已记录薄弱点" if created else "已更新薄弱点"
    return f"{action}：{record.title}"
```

- [ ] **Step 7: Register the tool**

Modify `tools/registry.py` imports:

```python
from tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness import (
    run as record_chinese_literacy_weakness_run,
)
```

Modify `TOOL_SPECS`:

```python
TOOL_SPECS = (
    ToolSpec("calculator", calculator_run, "基础工具"),
    ToolSpec("search_knowledge", search_knowledge_run, "知识检索"),
    ToolSpec(
        "record_chinese_literacy_weakness",
        record_chinese_literacy_weakness_run,
        "学习记录",
    ),
)
```

- [ ] **Step 8: Add the Chinese literacy skill**

Create `skills/chinese_literacy_support/SKILL.md`:

```markdown
---
id: chinese_literacy_support
name: chinese_literacy_support
display_name: Chinese Literacy Support
description: 面向一年级语文薄弱点识别和家庭练习建议的技能，会在家长明确描述问题时记录拼音、识字、朗读、表达或学习习惯薄弱点。
category: 学习支持
status: available
source: local
enabled: true
tools: record_chinese_literacy_weakness
---

# Chinese Literacy Support

- 当用户描述孩子在拼音、识字、朗读、表达或学习习惯上的具体问题时，先提取一个清晰薄弱点。
- 如果描述足够具体，调用 `record_chinese_literacy_weakness` 保存记录。
- 不做医学、心理或特殊教育诊断，不使用吓人的标签。
- 回答要温和、短、可执行，适合家长在家陪练。
- 建议练习通常控制在 10-15 分钟。
- 如果问题描述太泛，先问一个简短澄清问题，不要保存低质量记录。
```

Modify `skills/registry.py`:

```python
SKILL_SPECS = (
    SkillSpec("math_problem_solver"),
    SkillSpec("knowledge_lookup"),
    SkillSpec("chinese_literacy_support"),
)
```

- [ ] **Step 9: Set context around Agent execution**

Modify `api_server.py` imports:

```python
from learning_context import learning_run_context
```

In `chat(req: ChatRequest)`, wrap `agent.invoke`:

```python
with learning_run_context(req.user_id, DEFAULT_CHILD_ID, None):
    result = agent.invoke(
        {"messages": [("user", req.message)]},
        config=config,
    )
```

In `stream_chat_events`, wrap the `active_agent.astream_events` loop:

```python
with learning_run_context(req.user_id, DEFAULT_CHILD_ID, run_id):
    async for event in active_agent.astream_events(
        {"messages": [("user", req.message)]},
        config=config,
        version="v2",
    ):
        kind = event.get("event", "")
        # keep the existing event handling block inside this loop
```

Do not change the SSE payload shape in this task.

- [ ] **Step 10: Update stream test for context use**

In `test_api_stream_events.py`, add a test:

```python
async def test_stream_chat_events_sets_learning_context_for_agent_tools(self):
    class ContextCapturingAgent(FakeStreamAgent):
        async def astream_events(self, payload, config=None, version=None):
            import api_server
            context = api_server.current_learning_context()
            self.context_seen = context
            if False:
                yield {}

    store = make_temp_store(self)
    agent = ContextCapturingAgent([])
    req = api_server.ChatRequest(
        message="孩子拼音混淆",
        user_id="user-learning",
        session_id="session-learning",
    )

    chunks = await collect_stream_with_store(req, agent, store)

    self.assertEqual(chunks[-1], api_server.done_event())
    self.assertIsNotNone(agent.context_seen)
    self.assertEqual(agent.context_seen.user_id, "user-learning")
    self.assertEqual(agent.context_seen.child_id, api_server.DEFAULT_CHILD_ID)
```

Also import `current_learning_context` in `api_server.py` if this exact test accesses it through the module:

```python
from learning_context import current_learning_context, learning_run_context
```

- [ ] **Step 11: Run task tests to verify pass**

Run:

```bash
.venv/bin/python -m unittest test_learning_context.py test_learning_tool.py test_api_capabilities.py test_api_stream_events.py
```

Expected: PASS.

- [ ] **Step 12: Run backend full tests**

Run:

```bash
.venv/bin/python -m unittest
```

Expected: all tests pass.

- [ ] **Step 13: Commit Task 3**

Run:

```bash
git add \
  api_server.py \
  agent_context.py \
  skills/registry.py \
  skills/chinese_literacy_support/SKILL.md \
  tools/registry.py \
  tools/record_chinese_literacy_weakness \
  learning_context.py \
  test_learning_context.py \
  test_learning_tool.py \
  test_api_capabilities.py \
  test_api_stream_events.py
git commit -m "feat: record literacy weaknesses from agent"
```

Expected: commit created.

---

### Task 4: Frontend Learning API And Panel

**Files:**
- Create: `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`
- Create: `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningProfilePanel.tsx`
- Create: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/package.json`

**Interfaces:**
- Produces: `ChildProfileDto`
- Produces: `LearningWeaknessDto`
- Produces: `getDefaultChildProfile(userId: string) -> Promise<ChildProfileDto>`
- Produces: `listDefaultChildWeaknesses(userId: string) -> Promise<LearningWeaknessDto[]>`
- Produces: `LearningProfilePanel(props)`.

- [ ] **Step 1: Write failing frontend contract**

Create `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`:

```tsx
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  getDefaultChildProfile,
  listDefaultChildWeaknesses,
  type ChildProfileDto,
  type LearningWeaknessDto,
} from "../src/api/learning.js";
import { LearningProfilePanel } from "../src/chat/LearningProfilePanel.js";

const originalFetch = globalThis.fetch;

const profile: ChildProfileDto = {
  userId: "user-a",
  childId: "default",
  displayName: "孩子",
  grade: "first_grade",
  createdAt: "2026-08-18T00:00:00Z",
  updatedAt: "2026-08-18T00:00:00Z",
};

const weaknesses: LearningWeaknessDto[] = [
  {
    weaknessId: "weakness-a",
    userId: "user-a",
    childId: "default",
    subject: "chinese",
    grade: "first_grade",
    category: "pinyin",
    title: "b/p/d/q 混淆",
    evidence: "拼读时经常混淆。",
    severity: "medium",
    status: "active",
    sourceRunId: "run-a",
    createdAt: "2026-08-18T00:00:00Z",
    updatedAt: "2026-08-18T00:00:00Z",
  },
  {
    weaknessId: "weakness-b",
    userId: "user-a",
    childId: "default",
    subject: "chinese",
    grade: "first_grade",
    category: "reading",
    title: "朗读漏字",
    evidence: "朗读时漏字。",
    severity: "mild",
    status: "resolved",
    createdAt: "2026-08-17T00:00:00Z",
    updatedAt: "2026-08-17T00:00:00Z",
  },
];

try {
  const paths: string[] = [];
  globalThis.fetch = async (input) => {
    const path = String(input);
    paths.push(path);
    if (path.endsWith("/profile")) {
      return new Response(JSON.stringify(profile), { status: 200 });
    }
    return new Response(JSON.stringify(weaknesses), { status: 200 });
  };

  const loadedProfile = await getDefaultChildProfile("user-a");
  const loadedWeaknesses = await listDefaultChildWeaknesses("user-a");

  assert.equal(loadedProfile.childId, "default");
  assert.equal(loadedWeaknesses.length, 2);
  assert.match(paths[0], /\/users\/user-a\/children\/default\/profile$/);
  assert.match(paths[1], /\/users\/user-a\/children\/default\/weaknesses$/);
} finally {
  globalThis.fetch = originalFetch;
}

const html = renderToStaticMarkup(
  createElement(LearningProfilePanel, {
    profile,
    weaknesses,
    loading: false,
    onRetry: () => undefined,
  }),
);

assert.match(html, /学习画像/);
assert.match(html, /一年级/);
assert.match(html, /1<\/strong><span>进行中/);
assert.match(html, /b\/p\/d\/q 混淆/);
assert.match(html, /拼音/);
assert.match(html, /中等/);
assert.doesNotMatch(html, /2<\/strong><span>进行中/);

const emptyHtml = renderToStaticMarkup(
  createElement(LearningProfilePanel, {
    profile,
    weaknesses: [],
    loading: false,
    onRetry: () => undefined,
  }),
);
assert.match(emptyHtml, /暂无薄弱点记录/);

const loadingHtml = renderToStaticMarkup(
  createElement(LearningProfilePanel, {
    loading: true,
    onRetry: () => undefined,
  }),
);
assert.match(loadingHtml, /加载中/);

const errorHtml = renderToStaticMarkup(
  createElement(LearningProfilePanel, {
    loading: false,
    error: "学习画像加载失败",
    onRetry: () => undefined,
  }),
);
assert.match(errorHtml, /学习画像加载失败/);
assert.match(errorHtml, /重试/);

console.log("learning contracts passed");
```

- [ ] **Step 2: Add contract script entry and verify failure**

Modify `/Users/caisufang/projects/agent-hub-frontend/package.json` `test:contracts` script by appending:

```json
" && node node_modules/.tmp/contracts/contracts/learning.contract.js"
```

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: FAIL because `src/api/learning.ts` and `LearningProfilePanel.tsx` do not exist.

- [ ] **Step 3: Implement learning API client**

Create `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`:

```ts
import { requestJson } from "../request/http.js";

export type LearningSubject = "chinese";
export type LearningGrade = "first_grade";
export type WeaknessCategory =
  | "pinyin"
  | "character_recognition"
  | "reading"
  | "expression"
  | "learning_habit";
export type WeaknessSeverity = "mild" | "medium" | "high";
export type WeaknessStatus = "active" | "improving" | "resolved";

export interface ChildProfileDto {
  userId: string;
  childId: string;
  displayName: string;
  grade: LearningGrade;
  createdAt: string;
  updatedAt: string;
}

export interface LearningWeaknessDto {
  weaknessId: string;
  userId: string;
  childId: string;
  subject: LearningSubject;
  grade: LearningGrade;
  category: WeaknessCategory;
  title: string;
  evidence: string;
  severity: WeaknessSeverity;
  status: WeaknessStatus;
  sourceRunId?: string;
  createdAt: string;
  updatedAt: string;
}

export function getDefaultChildProfile(userId: string): Promise<ChildProfileDto> {
  return requestJson<ChildProfileDto>(
    `/users/${encodeURIComponent(userId)}/children/default/profile`,
  );
}

export function listDefaultChildWeaknesses(
  userId: string,
): Promise<LearningWeaknessDto[]> {
  return requestJson<LearningWeaknessDto[]>(
    `/users/${encodeURIComponent(userId)}/children/default/weaknesses`,
  );
}
```

- [ ] **Step 4: Implement learning panel component**

Create `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningProfilePanel.tsx`:

```tsx
import type {
  ChildProfileDto,
  LearningWeaknessDto,
  WeaknessCategory,
  WeaknessSeverity,
  WeaknessStatus,
} from "../api/learning.js";

interface LearningProfilePanelProps {
  profile?: ChildProfileDto;
  weaknesses?: LearningWeaknessDto[];
  loading: boolean;
  error?: string;
  onRetry: () => void;
}

const categoryLabels: Record<WeaknessCategory, string> = {
  pinyin: "拼音",
  character_recognition: "识字",
  reading: "朗读",
  expression: "表达",
  learning_habit: "习惯",
};

const severityLabels: Record<WeaknessSeverity, string> = {
  mild: "轻微",
  medium: "中等",
  high: "明显",
};

const statusLabels: Record<WeaknessStatus, string> = {
  active: "进行中",
  improving: "改善中",
  resolved: "已解决",
};

function gradeLabel(grade?: string): string {
  if (grade === "first_grade") return "一年级";
  return "一年级";
}

function activeWeaknessCount(weaknesses: LearningWeaknessDto[]): number {
  return weaknesses.filter((item) => item.status !== "resolved").length;
}

export function LearningProfilePanel({
  profile,
  weaknesses = [],
  loading,
  error,
  onRetry,
}: LearningProfilePanelProps) {
  const activeCount = activeWeaknessCount(weaknesses);

  return (
    <section className="learning-profile-panel" aria-label="学习画像">
      <div className="learning-profile-header">
        <span>学习画像</span>
        <span>{gradeLabel(profile?.grade)}</span>
      </div>

      {error && (
        <div className="learning-profile-error">
          <span>{error}</span>
          <button type="button" onClick={onRetry}>
            重试
          </button>
        </div>
      )}

      {loading && <div className="learning-profile-loading">加载中...</div>}

      {!loading && !error && (
        <>
          <div className="learning-profile-metrics">
            <div>
              <strong>{activeCount}</strong>
              <span>进行中</span>
            </div>
            <div>
              <strong>{weaknesses.length}</strong>
              <span>累计记录</span>
            </div>
          </div>

          {weaknesses.length === 0 && (
            <div className="learning-profile-empty">暂无薄弱点记录</div>
          )}

          {weaknesses.length > 0 && (
            <ol className="learning-weakness-list">
              {weaknesses.map((weakness) => (
                <li className="learning-weakness-row" key={weakness.weaknessId}>
                  <div className="learning-weakness-main">
                    <span>{weakness.title}</span>
                    <p>{weakness.evidence}</p>
                  </div>
                  <div className="learning-weakness-meta">
                    <span>{categoryLabels[weakness.category]}</span>
                    <span>{severityLabels[weakness.severity]}</span>
                    <span>{statusLabels[weakness.status]}</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Run contract test to verify pass**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: PASS including `learning contracts passed`.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add package.json src/api/learning.ts src/chat/LearningProfilePanel.tsx contracts/learning.contract.tsx
git commit -m "feat: add learning profile panel"
```

Expected: local frontend commit created.

---

### Task 5: Frontend App Integration And Refresh Flow

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.css`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx` if an App-level helper is extracted.

**Interfaces:**
- Consumes: `getDefaultChildProfile`, `listDefaultChildWeaknesses`, `LearningProfilePanel`.
- Produces: App state for `childProfile`, `learningWeaknesses`, `learningLoading`, `learningError`.
- Produces: `loadLearningProfile()` refresh function.
- Produces: refresh after `record_chinese_literacy_weakness` `tool_end` and after stream completion.

- [ ] **Step 1: Inspect current App stream handlers**

Run:

```bash
nl -ba src/App.tsx | sed -n '1,620p'
```

Expected: identify existing `loadCapabilityCatalog`, `handleStreamEvent`, and `onDone` areas.

- [ ] **Step 2: Add imports and learning state**

In `src/App.tsx`, add imports:

```ts
import {
  getDefaultChildProfile,
  listDefaultChildWeaknesses,
  type ChildProfileDto,
  type LearningWeaknessDto,
} from "./api/learning";
import { LearningProfilePanel } from "./chat/LearningProfilePanel";
```

Add state beside capability state:

```ts
const [childProfile, setChildProfile] = useState<ChildProfileDto>();
const [learningWeaknesses, setLearningWeaknesses] = useState<LearningWeaknessDto[]>([]);
const [learningLoading, setLearningLoading] = useState(true);
const [learningError, setLearningError] = useState<string>();
const learningRequestIdRef = useRef(0);
```

- [ ] **Step 3: Add `loadLearningProfile`**

Add this callback near `loadCapabilityCatalog`:

```ts
const loadLearningProfile = useCallback(async () => {
  const requestId = ++learningRequestIdRef.current;
  setLearningLoading(true);
  setLearningError(undefined);
  try {
    const [profile, weaknesses] = await Promise.all([
      getDefaultChildProfile(userId),
      listDefaultChildWeaknesses(userId),
    ]);
    if (learningRequestIdRef.current === requestId) {
      setChildProfile(profile);
      setLearningWeaknesses(weaknesses);
    }
  } catch {
    if (learningRequestIdRef.current === requestId) {
      setLearningError("学习画像加载失败");
    }
  } finally {
    if (learningRequestIdRef.current === requestId) {
      setLearningLoading(false);
    }
  }
}, [userId]);
```

Add effect:

```ts
useEffect(() => {
  void loadLearningProfile();
}, [loadLearningProfile]);
```

- [ ] **Step 4: Refresh learning panel after recording**

In the stream event handler where `ChatStreamEvent` is received, after appending timeline state, add:

```ts
if (
  event.type === "tool_end" &&
  event.tool === "record_chinese_literacy_weakness"
) {
  void loadLearningProfile();
}
```

In the stream `onDone` handler, after refreshing sessions, add:

```ts
void loadLearningProfile();
```

This intentionally refreshes twice for successful record runs: once immediately after the recording tool returns, and once after final answer completion.

- [ ] **Step 5: Render learning panel above capabilities**

Replace the standalone `CapabilityPanel` right-rail render with:

```tsx
<aside className="right-insight-rail" aria-label="学习和能力面板">
  <LearningProfilePanel
    profile={childProfile}
    weaknesses={learningWeaknesses}
    loading={learningLoading}
    error={learningError}
    onRetry={() => void loadLearningProfile()}
  />
  <CapabilityPanel
    catalog={capabilityCatalog}
    loading={capabilityLoading}
    error={capabilityError}
    onRetry={() => void loadCapabilityCatalog()}
  />
</aside>
```

Keep the grid column count unchanged by placing the new rail where `CapabilityPanel` currently sits.

- [ ] **Step 6: Add CSS for the learning rail**

In `src/App.css`, add or adjust:

```css
.right-insight-rail {
  display: grid;
  align-content: start;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}

.learning-profile-panel {
  display: grid;
  min-width: 0;
  overflow: hidden;
  border: 1px solid #d9e2ef;
  border-radius: 10px;
  background: #ffffff;
}

.learning-profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #e5ebf3;
  padding: 12px 14px;
  color: #263348;
  font-size: 13px;
  font-weight: 700;
}

.learning-profile-header span:last-child {
  color: #7a879a;
  font-size: 12px;
  font-weight: 500;
}

.learning-profile-error,
.learning-profile-loading,
.learning-profile-empty {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  color: #6b7890;
  font-size: 13px;
  line-height: 1.4;
}

.learning-profile-error {
  color: #991b1b;
  background: #fff7f7;
}

.learning-profile-error button {
  justify-self: start;
}

.learning-profile-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #e5ebf3;
  background: #fbfcfe;
}

.learning-profile-metrics div {
  display: grid;
  gap: 2px;
  min-width: 0;
  border: 1px solid #e1e7f0;
  border-radius: 8px;
  padding: 8px;
  background: #ffffff;
}

.learning-profile-metrics strong {
  color: #263348;
  font-size: 18px;
  line-height: 1.2;
  font-weight: 750;
}

.learning-profile-metrics span {
  color: #728096;
  font-size: 11px;
}

.learning-weakness-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 10px;
  list-style: none;
}

.learning-weakness-row {
  display: grid;
  gap: 8px;
  min-width: 0;
  border: 1px solid #e1e7f0;
  border-radius: 8px;
  padding: 10px;
  background: #ffffff;
}

.learning-weakness-main {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.learning-weakness-main span {
  color: #263348;
  font-size: 13px;
  font-weight: 700;
}

.learning-weakness-main p {
  margin: 0;
  color: #607089;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.learning-weakness-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.learning-weakness-meta span {
  border-radius: 999px;
  padding: 3px 7px;
  color: #475569;
  background: #f1f5f9;
  font-size: 11px;
  line-height: 1.2;
}
```

In existing responsive sections where `.capability-panel` spans full width, update selectors to target `.right-insight-rail` as the grid child.

- [ ] **Step 7: Run frontend checks**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
```

Expected: all pass.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add src/App.tsx src/App.css contracts/learning.contract.tsx
git commit -m "feat: integrate learning profile"
```

Expected: local frontend commit created.

---

### Task 6: End-To-End Verification And Final Commits

**Files:**
- Modify only if verification reveals a bug in files touched by earlier tasks.
- No new planned files in this task.

**Interfaces:**
- Consumes: all backend and frontend interfaces from Tasks 1-5.
- Produces: pushed backend commits and local frontend commits.

- [ ] **Step 1: Run backend verification**

Run:

```bash
.venv/bin/python -m unittest
.venv/bin/python -m py_compile api_server.py agent_console.py agent_context.py capabilities.py history_store.py learning_context.py learning_store.py skills/__init__.py skills/loader.py skills/registry.py tools/registry.py tools/record_chinese_literacy_weakness/record_chinese_literacy_weakness.py
git diff --check
```

Expected:

- `Ran ... tests` with `OK`.
- `py_compile` exits `0`.
- `git diff --check` exits `0`.

- [ ] **Step 2: Run frontend verification**

Run in `/Users/caisufang/projects/agent-hub-frontend`:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
git diff --check
```

Expected:

- contracts pass, including `learning contracts passed`.
- lint exits `0`.
- build exits `0`.
- `git diff --check` exits `0`.

- [ ] **Step 3: Smoke backend APIs**

If backend dev server is running on `127.0.0.1:8003`, run:

```bash
curl -s http://127.0.0.1:8003/users/smoke_user/children/default/profile
curl -s -X POST http://127.0.0.1:8003/users/smoke_user/children/default/weaknesses \
  -H "Content-Type: application/json" \
  -d '{"category":"pinyin","title":"b/p/d/q 混淆","evidence":"孩子拼读时经常混淆。","severity":"medium","sourceRunId":"run-smoke"}'
curl -s http://127.0.0.1:8003/users/smoke_user/children/default/weaknesses
curl -s http://127.0.0.1:8003/capabilities
```

Expected:

- Profile response has `childId: "default"` and `grade: "first_grade"`.
- POST response has `category: "pinyin"` and `status: "active"`.
- Weakness list includes `b/p/d/q 混淆`.
- Capabilities include `tool.record_chinese_literacy_weakness` and `skill.chinese_literacy_support`.

- [ ] **Step 4: Smoke Agent recording path**

If backend has a working model/API key, run one chat stream request:

```bash
curl -N -X POST http://127.0.0.1:8003/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"userId":"smoke_agent_user","sessionId":"smoke_literacy_session","message":"孩子 b p d q 经常混，拼音拼读慢，帮我记录一下。"}'
```

Expected:

- SSE emits stage events.
- A tool event for `record_chinese_literacy_weakness` appears when the model chooses correctly.
- Final answer is gentle and practical.

If the model does not call the tool, do not hide it. Record the observed behavior in the final response and treat prompt/tool description tuning as follow-up.

- [ ] **Step 5: Push backend commits**

Run in `/Users/caisufang/projects/agent-hub`:

```bash
git status --short --branch
git push origin main
```

Expected:

- Backend branch is `main`.
- Backend push succeeds.

- [ ] **Step 6: Leave frontend commits local**

Run in `/Users/caisufang/projects/agent-hub-frontend`:

```bash
git status --short --branch
git log --oneline -3
```

Expected:

- Frontend is ahead of `origin/main`.
- No uncommitted frontend changes remain.

---

## Self-Review

Spec coverage:

- Default child profile is covered by Tasks 1, 2, 4, and 5.
- Chinese literacy weakness records are covered by Tasks 1, 2, 3, 4, and 5.
- `chinese_literacy_support` skill is covered by Task 3.
- `record_chinese_literacy_weakness` tool is covered by Task 3.
- Backend APIs are covered by Task 2.
- Frontend learning profile panel is covered by Tasks 4 and 5.
- Agent-assisted recording is covered by Task 3 and Task 6 smoke.
- Safety and privacy are covered in the skill instructions and V1 data model.
- Future backlog is intentionally not implemented in this plan.

Placeholder scan:

- Forbidden placeholder markers are absent from the implementation tasks.
- Every task has exact files, interfaces, commands, and expected outcomes.

Type consistency:

- API DTO names use camelCase in TypeScript and JSON.
- Python and SQLite names use snake_case.
- `sourceRunId` maps to `source_run_id`.
- `childId = default`, `subject = chinese`, and `grade = first_grade` are consistent across backend, frontend, tool, and tests.
