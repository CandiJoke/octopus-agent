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
