import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_context import learning_run_context
from learning_store import LearningStore
from tools.record_chinese_literacy_weakness.record_chinese_literacy_weakness import (
    run as run_chinese,
)
from tools.record_learning_weakness.record_learning_weakness import run as run_general
from tools.update_child_profile.update_child_profile import run as run_update_profile


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
                "tools.record_chinese_literacy_weakness."
                "record_chinese_literacy_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-a"),
        ):
            result = run_chinese(
                category="pinyin",
                title="b/p/d/q 混淆",
                evidence="孩子拼音拼读时经常混淆。",
                severity="medium",
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_run_id, "run-a")

    def test_tool_accepts_chinese_enum_aliases(self):
        with (
            patch(
                "tools.record_chinese_literacy_weakness."
                "record_chinese_literacy_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-a"),
        ):
            result = run_chinese(
                category="拼音",
                title="声母容易混",
                evidence="拼读声母时反复混淆。",
                severity="中等",
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(records[0].category, "pinyin")
        self.assertEqual(records[0].severity, "medium")

    def test_chinese_tool_records_observable_behavior_reference(self):
        with (
            patch(
                "tools.record_chinese_literacy_weakness."
                "record_chinese_literacy_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-chinese-behavior"),
        ):
            result = run_chinese(
                category="拼音",
                title="b/d 易混淆",
                evidence="读拼音时经常把 b 看成 d。",
                severity="中等",
                behavior_id="chinese_g1_pinyin_initials_distinguish_bpdq",
                match_confidence=0.82,
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(records[0].ability_id, "chinese_g1_pinyin_initials")
        self.assertEqual(
            records[0].behavior_id,
            "chinese_g1_pinyin_initials_distinguish_bpdq",
        )

    def test_chinese_tool_accepts_ui_iu_observable_behavior_reference(self):
        with (
            patch(
                "tools.record_chinese_literacy_weakness."
                "record_chinese_literacy_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-chinese-ui-iu"),
        ):
            result = run_chinese(
                category="拼音",
                title="ui 和 iu 不分",
                evidence="读复韵母时经常把 ui 读成 iu。",
                severity="中等",
                behavior_id="chinese_g1_pinyin_finals_distinguish_ui_iu",
                match_confidence=0.82,
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(records[0].ability_id, "chinese_g1_pinyin_finals")
        self.assertEqual(
            records[0].behavior_id,
            "chinese_g1_pinyin_finals_distinguish_ui_iu",
        )

    def test_general_tool_records_math_weakness_from_context(self):
        with (
            patch(
                "tools.record_learning_weakness.record_learning_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-math"),
        ):
            result = run_general(
                subject="数学",
                category="计算",
                title="口算慢",
                evidence="10 以内口算会停很久。",
                severity="中等",
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a", subject="math")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_run_id, "run-math")
        self.assertEqual(records[0].category, "calculation")

    def test_general_tool_records_observable_behavior_reference(self):
        with (
            patch(
                "tools.record_learning_weakness.record_learning_weakness.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-behavior"),
        ):
            result = run_general(
                subject="语文",
                category="拼音",
                title="b/d 易混淆",
                evidence="读拼音时经常把 b 看成 d。",
                severity="中等",
                behavior_id="chinese_g1_pinyin_initials_distinguish_bpdq",
                match_confidence=0.82,
            )

        self.assertIn("已记录薄弱点", result)
        records = self.store.list_weaknesses("user-a")
        self.assertEqual(records[0].ability_id, "chinese_g1_pinyin_initials")
        self.assertEqual(
            records[0].behavior_id,
            "chinese_g1_pinyin_initials_distinguish_bpdq",
        )

    def test_update_profile_tool_updates_grade_from_injected_context(self):
        with (
            patch(
                "tools.update_child_profile.update_child_profile.learning_store",
                self.store,
            ),
            learning_run_context("user-a", "default", "run-grade"),
        ):
            result = run_update_profile(grade="二年级")

        self.assertIn("已更新学习画像", result)
        profile = self.store.get_or_create_default_profile("user-a")
        self.assertEqual(profile.grade, "grade_2")

    def test_tool_refuses_to_record_without_context(self):
        with patch(
            "tools.record_chinese_literacy_weakness."
            "record_chinese_literacy_weakness.learning_store",
            self.store,
        ):
            result = run_chinese(
                category="pinyin",
                title="b/p/d/q 混淆",
                evidence="孩子拼音拼读时经常混淆。",
                severity="medium",
            )

        self.assertIn("暂时无法记录", result)
        self.assertEqual(self.store.list_weaknesses("user-a"), [])

    def test_update_profile_tool_refuses_without_context(self):
        with patch(
            "tools.update_child_profile.update_child_profile.learning_store",
            self.store,
        ):
            result = run_update_profile(grade="二年级")

        self.assertIn("暂时无法更新学习画像", result)
        profile = self.store.get_or_create_default_profile("user-a")
        self.assertEqual(profile.grade, "grade_1")


if __name__ == "__main__":
    unittest.main()
