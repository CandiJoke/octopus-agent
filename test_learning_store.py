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
