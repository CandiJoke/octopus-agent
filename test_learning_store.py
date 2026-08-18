import tempfile
import unittest
from pathlib import Path
import sqlite3
from unittest.mock import patch

from learning_store import (
    DEFAULT_CHILD_ID,
    DEFAULT_GRADE,
    DEFAULT_SUBJECT,
    LearningStore,
    normalize_title,
    serialize_child_profile,
    serialize_learning_weakness,
    utc_now,
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

    def test_chinese_enum_aliases_are_normalized(self):
        record, created = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="拼音",
            title="声母容易混",
            evidence="拼读声母时反复混淆。",
            severity="中等",
        )

        self.assertTrue(created)
        self.assertEqual(record.category, "pinyin")
        self.assertEqual(record.severity, "medium")

    def test_upsert_weakness_accepts_english_and_math_subjects(self):
        english, english_created = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="english",
            category="phonics",
            title="b/d 字母认反",
            evidence="家长反馈孩子经常把 b 和 d 看反。",
            severity="medium",
        )
        math, math_created = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="math",
            category="calculation",
            title="20 以内加减法慢",
            evidence="做 20 以内加减法常要数手指。",
            severity="high",
        )

        self.assertTrue(english_created)
        self.assertTrue(math_created)
        self.assertEqual(english.subject, "english")
        self.assertEqual(english.category, "phonics")
        self.assertEqual(math.subject, "math")
        self.assertEqual(math.category, "calculation")

    def test_list_weaknesses_filters_by_subject(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="english",
            category="vocabulary",
            title="单词容易忘",
            evidence="学过的单词隔天就忘。",
            severity="medium",
        )
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="math",
            category="number_sense",
            title="数感弱",
            evidence="数量比较要数很久。",
            severity="mild",
        )

        english_records = self.store.list_weaknesses("user-a", subject="english")
        math_records = self.store.list_weaknesses("user-a", subject="math")

        self.assertEqual([item.subject for item in english_records], ["english"])
        self.assertEqual([item.subject for item in math_records], ["math"])

    def test_category_must_match_subject(self):
        with self.assertRaises(ValueError):
            self.store.upsert_weakness(
                "user-a",
                DEFAULT_CHILD_ID,
                subject="math",
                category="pinyin",
                title="拼音不属于数学",
                evidence="分类错配。",
                severity="medium",
            )

    def test_subject_and_category_aliases_are_normalized(self):
        record, created = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="数学",
            category="计算",
            title="口算慢",
            evidence="口算 10 以内加法也会停很久。",
            severity="明显",
        )

        self.assertTrue(created)
        self.assertEqual(record.subject, "math")
        self.assertEqual(record.category, "calculation")
        self.assertEqual(record.severity, "high")

    def test_old_chinese_only_schema_is_migrated_for_new_subjects(self):
        old_db_path = Path(self.temp_dir.name) / "old-learning.db"
        old_created_at = "2026-08-18T00:00:00+00:00"
        with sqlite3.connect(str(old_db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE child_profiles (
                    user_id TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, child_id)
                );

                CREATE TABLE learning_weaknesses (
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
                """
            )
            conn.execute(
                """
                INSERT INTO child_profiles(
                    user_id, child_id, display_name, grade, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "user-a",
                    DEFAULT_CHILD_ID,
                    "孩子",
                    DEFAULT_GRADE,
                    old_created_at,
                    old_created_at,
                ),
            )
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
                    "weakness_old",
                    "user-a",
                    DEFAULT_CHILD_ID,
                    DEFAULT_SUBJECT,
                    DEFAULT_GRADE,
                    "pinyin",
                    "旧拼音记录",
                    normalize_title("旧拼音记录"),
                    "旧表里的拼音记录。",
                    "mild",
                    "active",
                    "run-old",
                    old_created_at,
                    old_created_at,
                ),
            )
            conn.commit()

        migrated_store = LearningStore(old_db_path)
        migrated_store.initialize()

        record, created = migrated_store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="english",
            category="phonics",
            title="b/d 字母认反",
            evidence="经常把 b 和 d 看反。",
            severity="medium",
        )

        self.assertTrue(created)
        self.assertEqual(record.subject, "english")
        self.assertEqual(record.category, "phonics")
        records = migrated_store.list_weaknesses("user-a")
        self.assertEqual(
            {item.weakness_id for item in records},
            {"weakness_old", record.weakness_id},
        )

    def test_sensitive_learning_text_is_redacted_before_storage(self):
        record, _ = self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title="孩子名字是王小明，阳光小学拼音混淆",
            evidence=(
                "孩子叫王小明，妈妈叫李红，住在上海市浦东新区，"
                "医生说ADHD，电话13812345678。"
            ),
            severity="medium",
        )

        combined = f"{record.title}\n{record.evidence}"
        for sensitive_text in [
            "王小明",
            "阳光小学",
            "李红",
            "浦东新区",
            "ADHD",
            "13812345678",
        ]:
            self.assertNotIn(sensitive_text, combined)
        self.assertIn("已隐藏", combined)

    def test_integrity_race_updates_existing_active_record(self):
        real_connect = self.store._connect
        inserted_race_record = False

        def insert_race_record_once():
            nonlocal inserted_race_record
            if inserted_race_record:
                return
            inserted_race_record = True
            now = utc_now()
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
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
                        "weakness_race",
                        "user-a",
                        DEFAULT_CHILD_ID,
                        DEFAULT_SUBJECT,
                        DEFAULT_GRADE,
                        "pinyin",
                        "b/p/d/q 混淆",
                        normalize_title("b/p/d/q 混淆"),
                        "并发请求先写入。",
                        "mild",
                        "active",
                        None,
                        now,
                        now,
                    ),
                )
                conn.commit()

        class RaceConnection:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                self.conn.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self.conn.__exit__(exc_type, exc, tb)

            def execute(self, sql, params=()):
                if "INSERT INTO learning_weaknesses" in sql:
                    insert_race_record_once()
                return self.conn.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self.conn, name)

        def connect_with_race():
            return RaceConnection(real_connect())

        with patch.object(self.store, "_connect", connect_with_race):
            record, created = self.store.upsert_weakness(
                "user-a",
                DEFAULT_CHILD_ID,
                category="pinyin",
                title="b/p/d/q 混淆",
                evidence="父母这次补充说拼读仍然慢。",
                severity="high",
                source_run_id="run-b",
            )

        self.assertFalse(created)
        self.assertEqual(record.weakness_id, "weakness_race")
        self.assertEqual(record.evidence, "父母这次补充说拼读仍然慢。")
        self.assertEqual(record.severity, "high")
        self.assertEqual(record.source_run_id, "run-b")

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
