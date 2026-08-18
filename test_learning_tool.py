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
                "tools.record_chinese_literacy_weakness."
                "record_chinese_literacy_weakness.learning_store",
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
            "tools.record_chinese_literacy_weakness."
            "record_chinese_literacy_weakness.learning_store",
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
