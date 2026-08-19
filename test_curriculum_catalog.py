import unittest

from curriculum_catalog import (
    get_primary_grade_curriculum,
    resolve_curriculum_ability,
    resolve_curriculum_behavior,
)


class CurriculumCatalogTests(unittest.TestCase):
    def test_grade_one_catalog_contains_subjects_abilities_and_behaviors(self):
        catalog = get_primary_grade_curriculum("grade_1")

        self.assertEqual(catalog["schemaVersion"], "curriculum_tree.v1")
        self.assertEqual(catalog["stage"], "primary")
        self.assertEqual(catalog["grade"], "grade_1")
        self.assertEqual(
            [subject["subject"] for subject in catalog["subjects"]],
            ["chinese", "math", "english"],
        )

        chinese = catalog["subjects"][0]
        pinyin = chinese["domains"][0]
        initials = pinyin["abilities"][0]
        self.assertEqual(initials["abilityId"], "chinese_g1_pinyin_initials")
        self.assertIn(
            "chinese_g1_pinyin_initials_distinguish_bpdq",
            [behavior["behaviorId"] for behavior in initials["behaviors"]],
        )

    def test_behavior_reference_resolves_parent_ability(self):
        behavior = resolve_curriculum_behavior(
            "grade_1",
            "chinese",
            "chinese_g1_pinyin_initials_distinguish_bpdq",
        )

        self.assertEqual(behavior.subject, "chinese")
        self.assertEqual(behavior.grade, "grade_1")
        self.assertEqual(behavior.ability_id, "chinese_g1_pinyin_initials")
        self.assertEqual(behavior.ability_title, "声母辨认")
        self.assertEqual(behavior.behavior_title, "能区分 b/p/d/q 的形和音")
        self.assertEqual(behavior.category, "pinyin")

    def test_ability_reference_resolves_without_behavior(self):
        ability = resolve_curriculum_ability(
            "grade_1",
            "math",
            "math_g1_number_add_subtract_20",
        )

        self.assertEqual(ability.subject, "math")
        self.assertEqual(ability.title, "20 以内加减法")
        self.assertEqual(ability.category, "calculation")

    def test_unknown_curriculum_reference_is_rejected(self):
        with self.assertRaises(LookupError):
            resolve_curriculum_behavior("grade_2", "chinese", "missing")


if __name__ == "__main__":
    unittest.main()
