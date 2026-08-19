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
        self.assertEqual(payload["grade"], "grade_1")

    def test_profile_endpoint_updates_primary_grade(self):
        response = self.client.patch(
            "/users/user-a/children/default/profile",
            json={"grade": "三年级"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grade"], "grade_3")

        same_profile = self.client.get("/users/user-a/children/default/profile")
        self.assertEqual(same_profile.status_code, 200)
        self.assertEqual(same_profile.json()["grade"], "grade_3")

    def test_invalid_profile_grade_returns_422(self):
        response = self.client.patch(
            "/users/user-a/children/default/profile",
            json={"grade": "初一"},
        )

        self.assertEqual(response.status_code, 422)

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
        self.assertEqual(created["grade"], "grade_1")
        self.assertEqual(created["status"], "active")
        self.assertEqual(created["sourceRunId"], "run-a")

        list_response = self.client.get("/users/user-a/children/default/weaknesses")
        self.assertEqual(list_response.status_code, 200)
        listed = list_response.json()
        self.assertEqual([item["weaknessId"] for item in listed], [created["weaknessId"]])

    def test_curriculum_endpoint_returns_grade_one_tree(self):
        response = self.client.get("/curriculum/primary/grades/grade_1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "curriculum_tree.v1")
        self.assertEqual(payload["grade"], "grade_1")
        self.assertEqual(
            [subject["subject"] for subject in payload["subjects"]],
            ["chinese", "math", "english"],
        )

    def test_unsupported_curriculum_grade_returns_404(self):
        response = self.client.get("/curriculum/primary/grades/grade_2")

        self.assertEqual(response.status_code, 404)

    def test_create_weakness_can_link_observable_behavior(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "b/d 易混淆",
                "evidence": "读拼音时经常把 b 看成 d。",
                "severity": "medium",
                "behaviorId": "chinese_g1_pinyin_initials_distinguish_bpdq",
                "matchConfidence": 0.82,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["abilityId"], "chinese_g1_pinyin_initials")
        self.assertEqual(
            payload["behaviorId"],
            "chinese_g1_pinyin_initials_distinguish_bpdq",
        )
        self.assertEqual(payload["matchConfidence"], 0.82)
        self.assertEqual(payload["abilityTitle"], "声母辨认")
        self.assertEqual(payload["behaviorTitle"], "能区分 b/p/d/q 的形和音")

    def test_create_weakness_infers_observable_behavior(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "b/d 易混淆",
                "evidence": "读拼音时经常把 b 看成 d。",
                "severity": "medium",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["abilityId"], "chinese_g1_pinyin_initials")
        self.assertEqual(
            payload["behaviorId"],
            "chinese_g1_pinyin_initials_distinguish_bpdq",
        )
        self.assertEqual(payload["matchConfidence"], 0.76)
        self.assertEqual(payload["abilityTitle"], "声母辨认")
        self.assertEqual(payload["behaviorTitle"], "能区分 b/p/d/q 的形和音")

    def test_create_weakness_infers_ui_iu_observable_behavior(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "ui 和 iu 不分",
                "evidence": "读复韵母时经常把 ui 读成 iu。",
                "severity": "medium",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["abilityId"], "chinese_g1_pinyin_finals")
        self.assertEqual(
            payload["behaviorId"],
            "chinese_g1_pinyin_finals_distinguish_ui_iu",
        )
        self.assertEqual(payload["matchConfidence"], 0.76)
        self.assertEqual(payload["abilityTitle"], "复韵母辨认")
        self.assertEqual(payload["behaviorTitle"], "能区分 ui 和 iu 的形和音")

    def test_generate_weakness_practice_returns_observable_behavior_training(self):
        create_response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "ui 和 iu 不分",
                "evidence": "读复韵母时经常把 ui 读成 iu。",
                "severity": "medium",
            },
        )
        weakness_id = create_response.json()["weaknessId"]

        response = self.client.post(
            f"/users/user-a/children/default/weaknesses/{weakness_id}/practice"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["weaknessId"], weakness_id)
        self.assertEqual(
            payload["behaviorId"],
            "chinese_g1_pinyin_finals_distinguish_ui_iu",
        )
        self.assertEqual(payload["behaviorTitle"], "能区分 ui 和 iu 的形和音")
        self.assertEqual(payload["abilityTitle"], "复韵母辨认")
        self.assertEqual(payload["passingScore"], 3)
        self.assertIn("连续答对", payload["passingCriteria"])
        self.assertEqual(len(payload["questions"]), 4)
        self.assertEqual(payload["questions"][0]["questionId"], "q1")
        self.assertIn("ui", payload["questions"][0]["prompt"])
        self.assertIn("iu", payload["questions"][0]["options"])
        self.assertIn("ui", payload["questions"][0]["answer"])

    def test_mark_weakness_status_updates_learning_profile(self):
        create_response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "b/d 易混淆",
                "evidence": "读拼音时经常把 b 看成 d。",
                "severity": "medium",
            },
        )
        weakness_id = create_response.json()["weaknessId"]

        response = self.client.patch(
            f"/users/user-a/children/default/weaknesses/{weakness_id}/status",
            json={"status": "resolved"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["weaknessId"], weakness_id)
        self.assertEqual(payload["status"], "resolved")

        list_response = self.client.get("/users/user-a/children/default/weaknesses")
        listed = list_response.json()
        self.assertEqual(listed[0]["weaknessId"], weakness_id)
        self.assertEqual(listed[0]["status"], "resolved")

    def test_created_weakness_uses_updated_primary_grade(self):
        self.client.patch(
            "/users/user-a/children/default/profile",
            json={"grade": "grade_5"},
        )

        response = self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "计算",
                "title": "小数计算慢",
                "evidence": "小数加减法步骤容易漏。",
                "severity": "medium",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["grade"], "grade_5")

    def test_create_weakness_accepts_chinese_enum_aliases(self):
        response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "拼音",
                "title": "声母容易混",
                "evidence": "拼读声母时反复混淆。",
                "severity": "中等",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["category"], "pinyin")
        self.assertEqual(payload["severity"], "medium")

    def test_subject_endpoint_records_math_weakness(self):
        response = self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "计算",
                "title": "20 以内加减法慢",
                "evidence": "做 20 以内加减法常要数手指。",
                "severity": "明显",
                "sourceRunId": "run-math",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["subject"], "math")
        self.assertEqual(payload["category"], "calculation")
        self.assertEqual(payload["severity"], "high")
        self.assertEqual(payload["sourceRunId"], "run-math")

    def test_list_weaknesses_can_filter_by_subject(self):
        self.client.post(
            "/users/user-a/children/default/subjects/english/weaknesses",
            json={
                "category": "单词",
                "title": "单词容易忘",
                "evidence": "学过的单词隔天就忘。",
                "severity": "中等",
            },
        )
        self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "数感",
                "title": "数量比较慢",
                "evidence": "比较数量要数很久。",
                "severity": "轻微",
            },
        )

        response = self.client.get(
            "/users/user-a/children/default/weaknesses?subject=english"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["subject"], "english")

    def test_subject_category_mismatch_returns_422(self):
        response = self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "pinyin",
                "title": "分类错配",
                "evidence": "拼音不是数学分类。",
                "severity": "medium",
            },
        )

        self.assertEqual(response.status_code, 422)

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

    def test_learning_plan_api_saves_flow_and_checkins(self):
        chinese_response = self.client.post(
            "/users/user-a/children/default/weaknesses",
            json={
                "category": "pinyin",
                "title": "b/p/d/q 混淆",
                "evidence": "拼读时经常混淆。",
                "severity": "high",
                "behaviorId": "chinese_g1_pinyin_initials_distinguish_bpdq",
            },
        )
        math_response = self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "计算",
                "title": "口算慢",
                "evidence": "10 以内口算会停很久。",
                "severity": "medium",
            },
        )
        chinese_weakness_id = chinese_response.json()["weaknessId"]
        math_weakness_id = math_response.json()["weaknessId"]

        create_response = self.client.post(
            "/users/user-a/children/default/learning-plans",
            json={
                "createdFromPrompt": "请制定一周学习计划，每天 15 分钟。",
                "startDate": "2026-08-19",
                "endDate": "2026-08-25",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertEqual(created["status"], "draft")
        self.assertEqual(created["createdFromPrompt"], "请制定一周学习计划，每天 15 分钟。")
        self.assertEqual(created["startDate"], "2026-08-19")
        self.assertEqual(created["endDate"], "2026-08-25")
        self.assertEqual(
            {item["targetWeaknessId"] for item in created["items"]},
            {chinese_weakness_id, math_weakness_id},
        )
        self.assertEqual([item["subject"] for item in created["items"]], ["chinese", "math"])

        current_response = self.client.get(
            "/users/user-a/children/default/learning-plans/current"
        )
        self.assertEqual(current_response.status_code, 200)
        self.assertEqual(current_response.json()["planId"], created["planId"])

        active_response = self.client.patch(
            f"/users/user-a/children/default/learning-plans/{created['planId']}/status",
            json={"status": "active"},
        )
        self.assertEqual(active_response.status_code, 200)
        self.assertEqual(active_response.json()["status"], "active")

        item_id = active_response.json()["items"][0]["itemId"]
        checkin_response = self.client.post(
            f"/users/user-a/children/default/learning-plans/{created['planId']}/items/{item_id}/checkins",
            json={
                "checkinDate": "2026-08-19",
                "status": "done",
                "note": "今天完成 15 分钟。",
            },
        )
        self.assertEqual(checkin_response.status_code, 200)
        checked = checkin_response.json()
        self.assertEqual(checked["items"][0]["checkins"][0]["status"], "done")
        self.assertEqual(
            checked["items"][0]["checkins"][0]["checkinDate"],
            "2026-08-19",
        )

    def test_learning_plan_v2_api_lists_gets_and_returns_calendar(self):
        self.client.post(
            "/users/user-a/children/default/subjects/math/weaknesses",
            json={
                "category": "计算",
                "title": "口算慢",
                "evidence": "10 以内口算会停很久。",
                "severity": "medium",
            },
        )
        first = self.client.post(
            "/users/user-a/children/default/learning-plans",
            json={
                "createdFromPrompt": "第一份计划。",
                "startDate": "2026-08-19",
                "endDate": "2026-08-25",
            },
        ).json()
        second = self.client.post(
            "/users/user-a/children/default/learning-plans",
            json={
                "createdFromPrompt": "第二份计划。",
                "startDate": "2026-08-19",
                "endDate": "2026-08-21",
            },
        ).json()
        self.client.patch(
            f"/users/user-a/children/default/learning-plans/{first['planId']}/status",
            json={"status": "active"},
        )
        self.client.patch(
            f"/users/user-a/children/default/learning-plans/{second['planId']}/status",
            json={"status": "active"},
        )
        first_item_id = first["items"][0]["itemId"]
        self.client.post(
            (
                "/users/user-a/children/default/learning-plans/"
                f"{first['planId']}/items/{first_item_id}/checkins"
            ),
            json={"checkinDate": "2026-08-19", "status": "done"},
        )

        list_response = self.client.get(
            "/users/user-a/children/default/learning-plans?status=active&limit=10"
        )
        self.assertEqual(list_response.status_code, 200)
        summaries = list_response.json()
        self.assertEqual(len(summaries), 2)
        self.assertEqual({item["status"] for item in summaries}, {"active"})
        self.assertEqual({item["itemCount"] for item in summaries}, {1})

        detail_response = self.client.get(
            f"/users/user-a/children/default/learning-plans/{second['planId']}"
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["planId"], second["planId"])

        calendar_response = self.client.get(
            (
                "/users/user-a/children/default/learning-calendar"
                f"?from=2026-08-19&to=2026-08-21&planId={first['planId']}"
            )
        )
        self.assertEqual(calendar_response.status_code, 200)
        calendar = calendar_response.json()
        self.assertEqual(calendar["from"], "2026-08-19")
        self.assertEqual(calendar["to"], "2026-08-21")
        self.assertEqual(len(calendar["days"]), 3)
        self.assertEqual(calendar["days"][0]["plans"][0]["planId"], first["planId"])
        self.assertEqual(
            calendar["days"][0]["plans"][0]["items"][0]["checkin"]["status"],
            "done",
        )
        self.assertIsNone(calendar["days"][1]["plans"][0]["items"][0]["checkin"])

    def test_learning_calendar_api_rejects_invalid_dates(self):
        invalid_order = self.client.get(
            (
                "/users/user-a/children/default/learning-calendar"
                "?from=2026-08-22&to=2026-08-19"
            )
        )
        self.assertEqual(invalid_order.status_code, 422)

        invalid_format = self.client.get(
            (
                "/users/user-a/children/default/learning-calendar"
                "?from=2026/08/19&to=2026-08-20"
            )
        )
        self.assertEqual(invalid_format.status_code, 422)

        oversized = self.client.get(
            (
                "/users/user-a/children/default/learning-calendar"
                "?from=2026-08-01&to=2026-09-05"
            )
        )
        self.assertEqual(oversized.status_code, 422)

    def test_current_learning_plan_returns_null_when_empty(self):
        response = self.client.get(
            "/users/user-a/children/default/learning-plans/current"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json())


if __name__ == "__main__":
    unittest.main()
