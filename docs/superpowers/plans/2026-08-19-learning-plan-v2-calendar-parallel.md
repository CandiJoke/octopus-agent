# Learning Plan V2 Calendar Parallel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Learning Plan V2 with multiple plan selection, single-plan detail loading, and a 7-day calendar view for date-specific check-ins.

**Architecture:** Backend keeps the current learning-domain boundary in `learning_store.py`, adding summary and calendar read models over the existing V1 plan, item, and check-in tables. FastAPI exposes list, detail, and calendar endpoints while preserving V1 current-plan and check-in APIs. Frontend extends `src/api/learning.ts`, then upgrades `LearningPlanPanel` and `App.tsx` to load summaries, selected plan detail, and calendar range data.

**Tech Stack:** Python 3.11, FastAPI, SQLite, unittest, React, TypeScript, Vite, oxlint, Node 20.20.0.

## Global Constraints

- Backend repo: `/Users/caisufang/projects/agent-hub`.
- Frontend repo: `/Users/caisufang/projects/agent-hub-frontend`.
- Backend commits should be pushed to `origin/main`.
- Frontend commits should remain local unless the user asks to push.
- Frontend commands must use `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run <script>`.
- Keep `GET /users/{userId}/children/default/learning-plans/current` compatible.
- Keep V1 check-in endpoint compatible and use `checkinDate` for selected-date check-ins.
- Do not add a full month calendar UI in V2.
- Do not add plan item CRUD, drag-and-drop, recurrence editing, multi-child support, login, reminders, analytics, or Java extraction in V2.
- Preserve future Java service boundaries: plan summaries, plan detail, calendar range, and check-in command.

---

## File Structure

Backend files:

- Modify `/Users/caisufang/projects/agent-hub/learning_store.py`: add V2 read-model dataclasses, date-range helpers, summary/detail/calendar store methods, and serializers.
- Modify `/Users/caisufang/projects/agent-hub/api_server.py`: add request query parsing and V2 routes.
- Modify `/Users/caisufang/projects/agent-hub/test_learning_store.py`: add store tests for summaries, calendar data, filters, and date validation.
- Modify `/Users/caisufang/projects/agent-hub/test_api_learning.py`: add API tests for list, detail, calendar, filters, and invalid dates.

Frontend files:

- Modify `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`: add DTOs and API helpers for plan summaries, plan detail, and calendar range.
- Modify `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`: add contract coverage for new API helpers and calendar/selector rendering.
- Modify `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`: add summary, selected plan, calendar, selected date, and refresh flows.
- Modify `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningPlanPanel.tsx`: render plan selector, 7-day strip, selected-date task list, and existing status/check-in actions.
- Modify `/Users/caisufang/projects/agent-hub-frontend/src/App.css`: style the selector, calendar strip, selected-day task list, and keep plan body scrollable.

---

### Task 1: Backend Store Read Models

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub/learning_store.py`
- Test: `/Users/caisufang/projects/agent-hub/test_learning_store.py`

**Interfaces:**
- Consumes existing V1 records:
  - `LearningPlanRecord`
  - `LearningPlanItemRecord`
  - `LearningPlanCheckinRecord`
  - `LearningPlanSnapshot`
  - `serialize_learning_plan(snapshot: LearningPlanSnapshot) -> dict[str, object]`
- Produces:
  - `LearningPlanSummary`
  - `LearningCalendarItem`
  - `LearningCalendarPlan`
  - `LearningCalendarDay`
  - `LearningCalendar`
  - `LearningStore.list_learning_plan_summaries(user_id: str, child_id: str = DEFAULT_CHILD_ID, status: str | None = None, limit: int = 20, today: str | None = None) -> list[LearningPlanSummary]`
  - `LearningStore.get_learning_plan(user_id: str, plan_id: str) -> LearningPlanSnapshot`
  - `LearningStore.get_learning_calendar(user_id: str, from_date: str, to_date: str, child_id: str = DEFAULT_CHILD_ID, plan_id: str | None = None, status: str | None = None) -> LearningCalendar`
  - `serialize_learning_plan_summary(record: LearningPlanSummary) -> dict[str, object]`
  - `serialize_learning_calendar(calendar: LearningCalendar) -> dict[str, object]`

- [ ] **Step 1: Write failing store tests**

Add these imports in `/Users/caisufang/projects/agent-hub/test_learning_store.py`:

```python
from learning_store import (
    DEFAULT_CHILD_ID,
    DEFAULT_SUBJECT,
    LearningStore,
    normalize_grade_value,
    normalize_title,
    serialize_child_profile,
    serialize_learning_calendar,
    serialize_learning_plan,
    serialize_learning_plan_summary,
    serialize_learning_weakness,
    utc_now,
)
```

Add these test methods to `LearningStoreTests`, after `test_learning_plan_schema_allows_parallel_active_plans`:

```python
    def test_learning_plan_summaries_include_parallel_plans_and_today_counts(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="math",
            category="calculation",
            title="口算慢",
            evidence="10 以内口算会停很久。",
            severity="medium",
        )
        first = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="本周口算计划。",
            start_date="2026-08-19",
            end_date="2026-08-25",
        )
        second = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="周末专项计划。",
            start_date="2026-08-19",
            end_date="2026-08-21",
        )
        self.store.update_learning_plan_status("user-a", first.plan.plan_id, "active")
        self.store.update_learning_plan_status("user-a", second.plan.plan_id, "active")
        self.store.upsert_learning_plan_checkin(
            "user-a",
            first.plan.plan_id,
            first.items[0].item_id,
            checkin_date="2026-08-19",
            status="done",
        )

        summaries = self.store.list_learning_plan_summaries(
            "user-a",
            today="2026-08-19",
        )
        payloads = [serialize_learning_plan_summary(summary) for summary in summaries]

        self.assertEqual(len(payloads), 2)
        self.assertEqual({item["status"] for item in payloads}, {"active"})
        self.assertEqual({item["itemCount"] for item in payloads}, {1})
        first_payload = next(
            item for item in payloads if item["planId"] == first.plan.plan_id
        )
        second_payload = next(
            item for item in payloads if item["planId"] == second.plan.plan_id
        )
        self.assertEqual(first_payload["todayCheckinCount"], 1)
        self.assertEqual(second_payload["todayCheckinCount"], 0)

    def test_get_learning_plan_returns_selected_plan_snapshot(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title="b/p/d/q 混淆",
            evidence="拼读时经常混淆。",
            severity="high",
        )
        first = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="第一份计划。",
        )
        second = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="第二份计划。",
        )

        snapshot = self.store.get_learning_plan("user-a", second.plan.plan_id)

        self.assertEqual(snapshot.plan.plan_id, second.plan.plan_id)
        self.assertNotEqual(snapshot.plan.plan_id, first.plan.plan_id)
        self.assertEqual(snapshot.items[0].plan_id, second.plan.plan_id)

    def test_learning_calendar_returns_range_items_and_selected_date_checkins(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            category="pinyin",
            title="b/p/d/q 混淆",
            evidence="拼读时经常混淆。",
            severity="high",
        )
        plan = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="一周拼音计划。",
            start_date="2026-08-19",
            end_date="2026-08-21",
        )
        self.store.update_learning_plan_status("user-a", plan.plan.plan_id, "active")
        self.store.upsert_learning_plan_checkin(
            "user-a",
            plan.plan.plan_id,
            plan.items[0].item_id,
            checkin_date="2026-08-20",
            status="partial",
            note="完成一半。",
        )

        calendar = self.store.get_learning_calendar(
            "user-a",
            "2026-08-19",
            "2026-08-21",
            plan_id=plan.plan.plan_id,
        )
        payload = serialize_learning_calendar(calendar)

        self.assertEqual(payload["from"], "2026-08-19")
        self.assertEqual(payload["to"], "2026-08-21")
        self.assertEqual([day["date"] for day in payload["days"]], [
            "2026-08-19",
            "2026-08-20",
            "2026-08-21",
        ])
        day_with_checkin = payload["days"][1]
        self.assertEqual(day_with_checkin["plans"][0]["planId"], plan.plan.plan_id)
        item = day_with_checkin["plans"][0]["items"][0]
        self.assertEqual(item["itemId"], plan.items[0].item_id)
        self.assertEqual(item["checkin"]["status"], "partial")
        self.assertEqual(item["checkin"]["checkinDate"], "2026-08-20")
        self.assertIsNone(payload["days"][0]["plans"][0]["items"][0]["checkin"])

    def test_learning_calendar_filters_plan_and_rejects_bad_ranges(self):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="math",
            category="calculation",
            title="口算慢",
            evidence="10 以内口算会停很久。",
            severity="medium",
        )
        first = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="第一份计划。",
        )
        second = self.store.create_learning_plan_from_weaknesses(
            "user-a",
            created_from_prompt="第二份计划。",
        )

        filtered = self.store.get_learning_calendar(
            "user-a",
            "2026-08-19",
            "2026-08-19",
            plan_id=second.plan.plan_id,
        )
        payload = serialize_learning_calendar(filtered)
        self.assertEqual(
            [plan["planId"] for plan in payload["days"][0]["plans"]],
            [second.plan.plan_id],
        )

        with self.assertRaises(ValueError):
            self.store.get_learning_calendar("user-a", "2026-08-22", "2026-08-19")

        with self.assertRaises(ValueError):
            self.store.get_learning_calendar("user-a", "2026/08/19", "2026-08-20")

        with self.assertRaises(ValueError):
            self.store.get_learning_calendar("user-a", "2026-08-01", "2026-09-05")
```

- [ ] **Step 2: Run store tests to verify they fail**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest test_learning_store.py
```

Expected: fail with import errors for `serialize_learning_calendar` or missing `LearningStore.get_learning_calendar`.

- [ ] **Step 3: Implement backend store read models**

In `/Users/caisufang/projects/agent-hub/learning_store.py`, add this import:

```python
from datetime import UTC, date, datetime, timedelta
```

Add this constant near the existing plan status constants:

```python
MAX_LEARNING_CALENDAR_RANGE_DAYS = 31
```

Add these dataclasses after `LearningPlanSnapshot`:

```python
@dataclass(frozen=True)
class LearningPlanSummary:
    plan_id: str
    user_id: str
    child_id: str
    title: str
    goal: str
    status: str
    start_date: str | None
    end_date: str | None
    created_from_prompt: str
    item_count: int
    today_checkin_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningCalendarItem:
    item_id: str
    subject: str
    title: str
    estimated_minutes: int
    checkin: LearningPlanCheckinRecord | None


@dataclass(frozen=True)
class LearningCalendarPlan:
    plan_id: str
    title: str
    status: str
    items: list[LearningCalendarItem]


@dataclass(frozen=True)
class LearningCalendarDay:
    date: str
    plans: list[LearningCalendarPlan]


@dataclass(frozen=True)
class LearningCalendar:
    from_date: str
    to_date: str
    days: list[LearningCalendarDay]
```

Add these helper functions near `normalize_plan_date`:

```python
def parse_plan_date(value: str) -> date:
    normalized = normalize_plan_date(value)
    if normalized is None:
        raise ValueError("learning plan date is required")
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def inclusive_plan_dates(from_date: str, to_date: str) -> list[str]:
    start = parse_plan_date(from_date)
    end = parse_plan_date(to_date)
    if start > end:
        raise ValueError("learning calendar from date must be before to date")
    day_count = (end - start).days + 1
    if day_count > MAX_LEARNING_CALENDAR_RANGE_DAYS:
        raise ValueError("learning calendar range must be at most 31 days")
    return [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(day_count)
    ]


def plan_is_visible_on_date(plan: LearningPlanRecord, day: str) -> bool:
    if plan.start_date is not None and day < plan.start_date:
        return False
    if plan.end_date is not None and day > plan.end_date:
        return False
    return True
```

Add these methods inside `LearningStore`, after `list_learning_plans`:

```python
    def list_learning_plan_summaries(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
        status: str | None = None,
        limit: int = 20,
        today: str | None = None,
    ) -> list[LearningPlanSummary]:
        safe_limit = min(max(limit, 1), 100)
        today = normalize_plan_date(today) or datetime.now(UTC).date().isoformat()
        params: list[object] = [today, user_id, child_id]
        where_status = ""
        if status is not None:
            validate_plan_status(status)
            where_status = "AND p.status = ?"
            params.append(status)
        params.append(safe_limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.plan_id,
                    p.user_id,
                    p.child_id,
                    p.title,
                    p.goal,
                    p.status,
                    p.start_date,
                    p.end_date,
                    p.created_from_prompt,
                    p.created_at,
                    p.updated_at,
                    COUNT(DISTINCT i.item_id) AS item_count,
                    COUNT(DISTINCT c.checkin_id) AS today_checkin_count
                FROM learning_plans p
                LEFT JOIN learning_plan_items i
                    ON i.plan_id = p.plan_id
                LEFT JOIN learning_plan_checkins c
                    ON c.item_id = i.item_id
                    AND c.checkin_date = ?
                WHERE p.user_id = ? AND p.child_id = ?
                {where_status}
                GROUP BY p.plan_id
                ORDER BY
                    CASE p.status
                        WHEN 'active' THEN 0
                        WHEN 'draft' THEN 1
                        WHEN 'paused' THEN 2
                        WHEN 'completed' THEN 3
                        WHEN 'archived' THEN 4
                        ELSE 5
                    END ASC,
                    p.updated_at DESC,
                    p.plan_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [learning_plan_summary_from_row(row) for row in rows]

    def get_learning_plan(
        self,
        user_id: str,
        plan_id: str,
    ) -> LearningPlanSnapshot:
        with self._connect() as conn:
            return self._get_learning_plan_snapshot(conn, user_id, plan_id)

    def get_learning_calendar(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        child_id: str = DEFAULT_CHILD_ID,
        plan_id: str | None = None,
        status: str | None = None,
    ) -> LearningCalendar:
        days = inclusive_plan_dates(from_date, to_date)
        params: list[object] = [user_id, child_id]
        where_plan = ""
        where_status = "AND p.status != 'archived'"
        if plan_id is not None:
            where_plan = "AND p.plan_id = ?"
            where_status = ""
            params.append(plan_id)
        elif status is not None:
            validate_plan_status(status)
            where_status = "AND p.status = ?"
            params.append(status)

        with self._connect() as conn:
            plan_rows = conn.execute(
                f"""
                SELECT
                    p.plan_id,
                    p.user_id,
                    p.child_id,
                    p.title,
                    p.goal,
                    p.status,
                    p.start_date,
                    p.end_date,
                    p.created_from_prompt,
                    p.created_at,
                    p.updated_at
                FROM learning_plans p
                WHERE p.user_id = ? AND p.child_id = ?
                {where_plan}
                {where_status}
                ORDER BY
                    CASE p.status
                        WHEN 'active' THEN 0
                        WHEN 'draft' THEN 1
                        WHEN 'paused' THEN 2
                        WHEN 'completed' THEN 3
                        ELSE 4
                    END ASC,
                    p.updated_at DESC,
                    p.plan_id DESC
                """,
                params,
            ).fetchall()
            plans = [learning_plan_from_row(row) for row in plan_rows]
            if plan_id is not None and not plans:
                raise LookupError(f"learning plan not found: {plan_id}")

            plan_ids = [plan.plan_id for plan in plans]
            items_by_plan_id: dict[str, list[LearningPlanItemRecord]] = {
                current_plan_id: [] for current_plan_id in plan_ids
            }
            checkins_by_item_date: dict[tuple[str, str], LearningPlanCheckinRecord] = {}
            if plan_ids:
                placeholders = ",".join("?" for _ in plan_ids)
                item_rows = conn.execute(
                    f"""
                    SELECT
                        item_id, plan_id, user_id, child_id, subject, title,
                        description, target_weakness_id, frequency,
                        estimated_minutes, sort_order, created_at, updated_at
                    FROM learning_plan_items
                    WHERE user_id = ? AND plan_id IN ({placeholders})
                    ORDER BY sort_order ASC, item_id ASC
                    """,
                    [user_id, *plan_ids],
                ).fetchall()
                items = [learning_plan_item_from_row(row) for row in item_rows]
                for item in items:
                    items_by_plan_id.setdefault(item.plan_id, []).append(item)

                item_ids = [item.item_id for item in items]
                if item_ids:
                    item_placeholders = ",".join("?" for _ in item_ids)
                    checkin_rows = conn.execute(
                        f"""
                        SELECT
                            checkin_id, plan_id, item_id, user_id, child_id,
                            checkin_date, status, note, created_at, updated_at
                        FROM learning_plan_checkins
                        WHERE user_id = ?
                            AND item_id IN ({item_placeholders})
                            AND checkin_date BETWEEN ? AND ?
                        """,
                        [user_id, *item_ids, days[0], days[-1]],
                    ).fetchall()
                    for row in checkin_rows:
                        checkin = learning_plan_checkin_from_row(row)
                        checkins_by_item_date[
                            (checkin.item_id, checkin.checkin_date)
                        ] = checkin

            calendar_days: list[LearningCalendarDay] = []
            for day in days:
                day_plans: list[LearningCalendarPlan] = []
                for plan in plans:
                    if not plan_is_visible_on_date(plan, day):
                        continue
                    calendar_items = [
                        LearningCalendarItem(
                            item_id=item.item_id,
                            subject=item.subject,
                            title=item.title,
                            estimated_minutes=item.estimated_minutes,
                            checkin=checkins_by_item_date.get((item.item_id, day)),
                        )
                        for item in items_by_plan_id.get(plan.plan_id, [])
                    ]
                    if calendar_items:
                        day_plans.append(
                            LearningCalendarPlan(
                                plan_id=plan.plan_id,
                                title=plan.title,
                                status=plan.status,
                                items=calendar_items,
                            )
                        )
                calendar_days.append(LearningCalendarDay(date=day, plans=day_plans))

        return LearningCalendar(from_date=days[0], to_date=days[-1], days=calendar_days)
```

Add these row converters near `learning_plan_from_row`:

```python
def learning_plan_summary_from_row(row: sqlite3.Row) -> LearningPlanSummary:
    start_date = row["start_date"]
    end_date = row["end_date"]
    return LearningPlanSummary(
        plan_id=str(row["plan_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        title=str(row["title"]),
        goal=str(row["goal"]),
        status=str(row["status"]),
        start_date=str(start_date) if start_date is not None else None,
        end_date=str(end_date) if end_date is not None else None,
        created_from_prompt=str(row["created_from_prompt"]),
        item_count=int(row["item_count"]),
        today_checkin_count=int(row["today_checkin_count"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
```

Add these serializers after `serialize_learning_plan`:

```python
def serialize_learning_plan_summary(record: LearningPlanSummary) -> dict[str, object]:
    return {
        "planId": record.plan_id,
        "userId": record.user_id,
        "childId": record.child_id,
        "title": record.title,
        "goal": record.goal,
        "status": record.status,
        "startDate": record.start_date,
        "endDate": record.end_date,
        "createdFromPrompt": record.created_from_prompt,
        "itemCount": record.item_count,
        "todayCheckinCount": record.today_checkin_count,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def serialize_learning_calendar(calendar: LearningCalendar) -> dict[str, object]:
    return {
        "from": calendar.from_date,
        "to": calendar.to_date,
        "days": [
            {
                "date": day.date,
                "plans": [
                    {
                        "planId": plan.plan_id,
                        "title": plan.title,
                        "status": plan.status,
                        "items": [
                            {
                                "itemId": item.item_id,
                                "subject": item.subject,
                                "title": item.title,
                                "estimatedMinutes": item.estimated_minutes,
                                "checkin": (
                                    serialize_learning_plan_checkin(item.checkin)
                                    if item.checkin is not None
                                    else None
                                ),
                            }
                            for item in plan.items
                        ],
                    }
                    for plan in day.plans
                ],
            }
            for day in calendar.days
        ],
    }
```

- [ ] **Step 4: Run store tests to verify they pass**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest test_learning_store.py
```

Expected: all `LearningStoreTests` pass.

- [ ] **Step 5: Commit backend store task**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
git add learning_store.py test_learning_store.py
git commit -m "feat: add learning plan calendar store"
```

---

### Task 2: Backend API Routes

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub/api_server.py`
- Test: `/Users/caisufang/projects/agent-hub/test_api_learning.py`

**Interfaces:**
- Consumes Task 1:
  - `LearningStore.list_learning_plan_summaries`
  - `LearningStore.get_learning_plan`
  - `LearningStore.get_learning_calendar`
  - `serialize_learning_plan_summary`
  - `serialize_learning_calendar`
- Produces API endpoints:
  - `GET /users/{user_id}/children/default/learning-plans`
  - `GET /users/{user_id}/children/default/learning-plans/{plan_id}`
  - `GET /users/{user_id}/children/default/learning-calendar?from=YYYY-MM-DD&to=YYYY-MM-DD`

- [ ] **Step 1: Write failing API tests**

Add these test methods to `/Users/caisufang/projects/agent-hub/test_api_learning.py`, after `test_learning_plan_api_saves_flow_and_checkins`:

```python
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
            f"/users/user-a/children/default/learning-plans/{first['planId']}/items/{first_item_id}/checkins",
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
            f"/users/user-a/children/default/learning-calendar?from=2026-08-19&to=2026-08-21&planId={first['planId']}"
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
            "/users/user-a/children/default/learning-calendar?from=2026-08-22&to=2026-08-19"
        )
        self.assertEqual(invalid_order.status_code, 422)

        invalid_format = self.client.get(
            "/users/user-a/children/default/learning-calendar?from=2026/08/19&to=2026-08-20"
        )
        self.assertEqual(invalid_format.status_code, 422)

        oversized = self.client.get(
            "/users/user-a/children/default/learning-calendar?from=2026-08-01&to=2026-09-05"
        )
        self.assertEqual(oversized.status_code, 422)
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest test_api_learning.py
```

Expected: fail with `404` for `/learning-calendar` or missing `/learning-plans/{plan_id}` route.

- [ ] **Step 3: Implement API routes**

In `/Users/caisufang/projects/agent-hub/api_server.py`, change the FastAPI import:

```python
from fastapi import Depends, FastAPI, HTTPException, Query, Response
```

Add serializers to the learning-store import:

```python
    serialize_learning_calendar,
    serialize_learning_plan,
    serialize_learning_plan_summary,
    serialize_learning_weakness,
)
```

Add these routes after `update_default_child_weakness_status` and before the existing `/learning-plans/current` route. Keep `/learning-plans/current` before `/learning-plans/{plan_id}`:

```python
@app.get("/users/{user_id}/children/default/learning-plans")
def list_default_child_learning_plans(
    user_id: str,
    status: LearningPlanStatus | None = None,
    limit: int = 20,
    store: LearningStore = Depends(get_learning_store),
):
    try:
        summaries = store.list_learning_plan_summaries(
            user_id,
            DEFAULT_CHILD_ID,
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [serialize_learning_plan_summary(summary) for summary in summaries]
```

Add this route after `/learning-plans/current`:

```python
@app.get("/users/{user_id}/children/default/learning-plans/{plan_id}")
def get_default_child_learning_plan(
    user_id: str,
    plan_id: str,
    store: LearningStore = Depends(get_learning_store),
):
    try:
        snapshot = store.get_learning_plan(user_id, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_learning_plan(snapshot)
```

Add this route near the plan routes:

```python
@app.get("/users/{user_id}/children/default/learning-calendar")
def get_default_child_learning_calendar(
    user_id: str,
    from_date: str = Query(alias="from"),
    to_date: str = Query(alias="to"),
    plan_id: str | None = Query(default=None, alias="planId"),
    status: LearningPlanStatus | None = None,
    store: LearningStore = Depends(get_learning_store),
):
    try:
        calendar = store.get_learning_calendar(
            user_id,
            from_date,
            to_date,
            DEFAULT_CHILD_ID,
            plan_id=plan_id,
            status=status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_learning_calendar(calendar)
```

- [ ] **Step 4: Run API tests to verify they pass**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest test_api_learning.py
```

Expected: all `LearningApiTests` pass.

- [ ] **Step 5: Run backend full test suite**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest
```

Expected: all backend tests pass.

- [ ] **Step 6: Commit and push backend API task**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
git add api_server.py learning_store.py test_api_learning.py test_learning_store.py
git commit -m "feat: add learning plan calendar api"
git push origin main
```

---

### Task 3: Frontend API Contracts

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`

**Interfaces:**
- Consumes backend endpoints from Task 2.
- Produces:
  - `LearningPlanSummaryDto`
  - `LearningCalendarDto`
  - `LearningCalendarDayDto`
  - `LearningCalendarPlanDto`
  - `LearningCalendarItemDto`
  - `listLearningPlans(userId: string, options?: { status?: LearningPlanStatus; limit?: number })`
  - `getLearningPlan(userId: string, planId: string)`
  - `getLearningCalendar(userId: string, options: { from: string; to: string; planId?: string; status?: LearningPlanStatus })`

- [ ] **Step 1: Write failing frontend contract tests**

In `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`, add imports:

```ts
  getLearningCalendar,
  getLearningPlan,
  listLearningPlans,
  type LearningCalendarDto,
  type LearningPlanSummaryDto,
```

Add fixtures after `checkedLearningPlan`:

```ts
const learningPlanSummaries: LearningPlanSummaryDto[] = [
  {
    planId: "plan-a",
    userId: "user-a",
    childId: "default",
    title: "本周学习计划",
    goal: "请制定一周学习计划，每天 15 分钟。",
    status: "active",
    startDate: "2026-08-19",
    endDate: "2026-08-25",
    createdFromPrompt: "请制定一周学习计划，每天 15 分钟。",
    itemCount: 2,
    todayCheckinCount: 1,
    createdAt: "2026-08-19T00:00:00Z",
    updatedAt: "2026-08-19T08:00:00Z",
  },
  {
    planId: "plan-b",
    userId: "user-a",
    childId: "default",
    title: "周末专项计划",
    goal: "周末集中复习口算。",
    status: "draft",
    startDate: "2026-08-22",
    endDate: "2026-08-23",
    createdFromPrompt: "周末专项计划。",
    itemCount: 1,
    todayCheckinCount: 0,
    createdAt: "2026-08-19T01:00:00Z",
    updatedAt: "2026-08-19T01:00:00Z",
  },
];

const learningCalendar: LearningCalendarDto = {
  from: "2026-08-19",
  to: "2026-08-25",
  days: [
    {
      date: "2026-08-19",
      plans: [
        {
          planId: "plan-a",
          title: "本周学习计划",
          status: "active",
          items: [
            {
              itemId: "item-a",
              subject: "chinese",
              title: "语文 · 拼音：b/p/d/q 混淆",
              estimatedMinutes: 15,
              checkin: checkedLearningPlan.items[0].checkins[0],
            },
          ],
        },
      ],
    },
    {
      date: "2026-08-20",
      plans: [
        {
          planId: "plan-a",
          title: "本周学习计划",
          status: "active",
          items: [
            {
              itemId: "item-a",
              subject: "chinese",
              title: "语文 · 拼音：b/p/d/q 混淆",
              estimatedMinutes: 15,
              checkin: null,
            },
          ],
        },
      ],
    },
  ],
};
```

Add fetch handlers before the generic weakness response:

```ts
    if (path.endsWith("/learning-plans?status=active&limit=10")) {
      return new Response(JSON.stringify(learningPlanSummaries), { status: 200 });
    }
    if (path.endsWith("/learning-plans/plan-a")) {
      return new Response(JSON.stringify(checkedLearningPlan), { status: 200 });
    }
    if (
      path.endsWith(
        "/learning-calendar?from=2026-08-19&to=2026-08-25&planId=plan-a",
      )
    ) {
      return new Response(JSON.stringify(learningCalendar), { status: 200 });
    }
```

Add API calls and assertions after `checkedPlan`:

```ts
  const loadedPlanSummaries = await listLearningPlans("user-a", {
    status: "active",
    limit: 10,
  });
  const selectedPlan = await getLearningPlan("user-a", "plan-a");
  const loadedCalendar = await getLearningCalendar("user-a", {
    from: "2026-08-19",
    to: "2026-08-25",
    planId: "plan-a",
  });

  assert.equal(loadedPlanSummaries.length, 2);
  assert.equal(loadedPlanSummaries[0].todayCheckinCount, 1);
  assert.equal(selectedPlan.planId, "plan-a");
  assert.equal(loadedCalendar.days[0].plans[0].items[0].checkin?.status, "done");
  assert.equal(loadedCalendar.days[1].plans[0].items[0].checkin, null);
```

Add request path assertions after the existing plan request assertions:

```ts
  assert.match(
    requests[11].path,
    /\/users\/user-a\/children\/default\/learning-plans\?status=active&limit=10$/,
  );
  assert.match(
    requests[12].path,
    /\/users\/user-a\/children\/default\/learning-plans\/plan-a$/,
  );
  assert.match(
    requests[13].path,
    /\/users\/user-a\/children\/default\/learning-calendar\?from=2026-08-19&to=2026-08-25&planId=plan-a$/,
  );
```

- [ ] **Step 2: Run frontend contracts to verify they fail**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: TypeScript errors for missing exported DTOs and functions from `src/api/learning.ts`.

- [ ] **Step 3: Implement frontend API helpers**

In `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`, add DTOs after `LearningPlanDto`:

```ts
export interface LearningPlanSummaryDto {
  planId: string;
  userId: string;
  childId: string;
  title: string;
  goal: string;
  status: LearningPlanStatus;
  startDate?: string | null;
  endDate?: string | null;
  createdFromPrompt: string;
  itemCount: number;
  todayCheckinCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface LearningCalendarItemDto {
  itemId: string;
  subject: LearningSubject;
  title: string;
  estimatedMinutes: number;
  checkin: LearningPlanCheckinDto | null;
}

export interface LearningCalendarPlanDto {
  planId: string;
  title: string;
  status: LearningPlanStatus;
  items: LearningCalendarItemDto[];
}

export interface LearningCalendarDayDto {
  date: string;
  plans: LearningCalendarPlanDto[];
}

export interface LearningCalendarDto {
  from: string;
  to: string;
  days: LearningCalendarDayDto[];
}
```

Add this helper near the existing API functions:

```ts
function buildLearningQuery(
  params: Record<string, string | number | undefined>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      query.set(key, String(value));
    }
  }
  const queryText = query.toString();
  return queryText ? `?${queryText}` : "";
}
```

Add these functions after `getCurrentLearningPlan`:

```ts
export function listLearningPlans(
  userId: string,
  options: { status?: LearningPlanStatus; limit?: number } = {},
): Promise<LearningPlanSummaryDto[]> {
  const query = buildLearningQuery({
    status: options.status,
    limit: options.limit,
  });
  return requestJson<LearningPlanSummaryDto[]>(
    `/users/${encodeURIComponent(userId)}/children/default/learning-plans${query}`,
  );
}

export function getLearningPlan(
  userId: string,
  planId: string,
): Promise<LearningPlanDto> {
  return requestJson<LearningPlanDto>(
    `/users/${encodeURIComponent(userId)}/children/default/learning-plans/${encodeURIComponent(
      planId,
    )}`,
  );
}

export function getLearningCalendar(
  userId: string,
  options: {
    from: string;
    to: string;
    planId?: string;
    status?: LearningPlanStatus;
  },
): Promise<LearningCalendarDto> {
  const query = buildLearningQuery({
    from: options.from,
    to: options.to,
    planId: options.planId,
    status: options.status,
  });
  return requestJson<LearningCalendarDto>(
    `/users/${encodeURIComponent(userId)}/children/default/learning-calendar${query}`,
  );
}
```

- [ ] **Step 4: Run frontend contracts to verify API task passes**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: contracts pass up to the UI assertions already present before Task 4 changes.

- [ ] **Step 5: Commit frontend API task locally**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
git add contracts/learning.contract.tsx src/api/learning.ts
git commit -m "feat: add learning plan v2 api client"
```

---

### Task 4: Frontend Plan Selector And Calendar UI

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningPlanPanel.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.css`

**Interfaces:**
- Consumes Task 3:
  - `LearningPlanSummaryDto`
  - `LearningCalendarDto`
  - `LearningCalendarItemDto`
  - `listLearningPlans`
  - `getLearningPlan`
  - `getLearningCalendar`
- Produces:
  - `LearningPlanPanel` props with plan summaries and calendar data.
  - Date-specific `onCheckIn(itemId, status, date)` flow.
  - Right-rail UI for multi-plan selector and 7-day date strip.

- [ ] **Step 1: Write failing UI contract tests**

In `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`, update the `LearningPlanPanel` render call for `planHtml`:

```tsx
const planHtml = renderToStaticMarkup(
  createElement(LearningPlanPanel, {
    plan: learningPlan,
    planSummaries: learningPlanSummaries,
    calendar: learningCalendar,
    selectedPlanId: "plan-a",
    selectedDate: "2026-08-19",
    loading: false,
    listLoading: false,
    calendarLoading: false,
    creating: false,
    statusUpdating: false,
    today: "2026-08-19",
    onCreatePlan: () => undefined,
    onSelectPlan: () => undefined,
    onSelectDate: () => undefined,
    onUpdateStatus: () => undefined,
    onCheckIn: () => undefined,
    onRetry: () => undefined,
  }),
);
```

Add these assertions after the existing plan HTML assertions:

```ts
assert.match(planHtml, /learning-plan-selector/);
assert.match(planHtml, /本周学习计划/);
assert.match(planHtml, /周末专项计划/);
assert.match(planHtml, /learning-plan-calendar-strip/);
assert.match(planHtml, /今天/);
assert.match(planHtml, /8\/20/);
assert.match(planHtml, /learning-plan-day-tasks/);
assert.match(planHtml, /语文 · 拼音：b\/p\/d\/q 混淆/);
assert.match(planHtml, /今日：已完成/);
```

Add CSS assertions after existing plan CSS assertions:

```ts
assert.match(css, /\.learning-plan-selector/);
assert.match(css, /\.learning-plan-calendar-strip/);
assert.match(css, /\.learning-plan-date-button/);
assert.match(css, /\.learning-plan-day-tasks/);
```

Add source assertions:

```ts
assert.match(appSource, /listLearningPlans/);
assert.match(appSource, /getLearningCalendar/);
assert.match(appSource, /selectedLearningPlanId/);
assert.match(appSource, /selectedLearningDate/);
```

- [ ] **Step 2: Run frontend contracts to verify they fail**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: TypeScript errors because `LearningPlanPanelProps` does not yet accept `planSummaries`, `calendar`, `selectedPlanId`, `selectedDate`, `onSelectPlan`, or `onSelectDate`.

- [ ] **Step 3: Update `LearningPlanPanel` props and helpers**

In `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningPlanPanel.tsx`, update imports:

```ts
  LearningCalendarDto,
  LearningCalendarItemDto,
  LearningPlanCheckinStatus,
  LearningPlanDto,
  LearningPlanItemDto,
  LearningPlanStatus,
  LearningPlanSummaryDto,
  LearningSubject,
```

Replace the props interface with:

```ts
interface LearningPlanPanelProps {
  plan?: LearningPlanDto | null;
  planSummaries?: LearningPlanSummaryDto[];
  calendar?: LearningCalendarDto;
  selectedPlanId?: string;
  selectedDate: string;
  loading: boolean;
  listLoading: boolean;
  calendarLoading: boolean;
  error?: string;
  calendarError?: string;
  creating: boolean;
  statusUpdating: boolean;
  checkinUpdatingItemId?: string;
  latestPrompt?: string;
  today?: string;
  onCreatePlan: () => void;
  onSelectPlan: (planId: string) => void;
  onSelectDate: (date: string) => void;
  onUpdateStatus: (status: LearningPlanStatus) => void;
  onCheckIn: (
    item: LearningPlanItemDto | LearningCalendarItemDto,
    status: LearningPlanCheckinStatus,
    checkinDate: string,
  ) => void;
  onRetry: () => void;
}
```

Add helper functions:

```ts
function calendarDays(calendar?: LearningCalendarDto): string[] {
  return calendar?.days.map((day) => day.date) ?? [];
}

function formatCalendarDate(dateValue: string, today: string): string {
  if (dateValue === today) return "今天";
  const date = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateValue;
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function selectedDayItems(
  calendar: LearningCalendarDto | undefined,
  selectedDate: string,
): LearningCalendarItemDto[] {
  const day = calendar?.days.find((item) => item.date === selectedDate);
  return day?.plans.flatMap((plan) => plan.items) ?? [];
}

function checkinLabel(status?: LearningPlanCheckinStatus): string | undefined {
  if (!status) return undefined;
  return checkinLabels[status];
}
```

- [ ] **Step 4: Render selector, calendar strip, and selected-day tasks**

Inside `LearningPlanPanel`, compute:

```ts
  const summaries = planSummaries ?? [];
  const dates = calendarDays(calendar);
  const dayItems = selectedDayItems(calendar, selectedDate);
```

Inside `.learning-plan-body`, render this selector above `.learning-plan-summary`:

```tsx
          <div className="learning-plan-selector" aria-label="计划切换">
            {summaries.map((summary) => (
              <button
                type="button"
                key={summary.planId}
                className={
                  summary.planId === selectedPlanId ? "is-active" : undefined
                }
                disabled={listLoading}
                onClick={() => onSelectPlan(summary.planId)}
              >
                <span>{summary.title}</span>
                <strong>
                  {statusLabels[summary.status]} · {summary.itemCount} 项
                </strong>
              </button>
            ))}
          </div>
```

Render this calendar strip under `.learning-plan-flow-actions`:

```tsx
          <div className="learning-plan-calendar-strip" aria-label="学习日历">
            {calendarError && <span>{calendarError}</span>}
            {!calendarError &&
              dates.map((dateValue) => (
                <button
                  type="button"
                  key={dateValue}
                  className={`learning-plan-date-button${
                    dateValue === selectedDate ? " is-active" : ""
                  }`}
                  disabled={calendarLoading}
                  onClick={() => onSelectDate(dateValue)}
                >
                  <span>{formatCalendarDate(dateValue, today)}</span>
                </button>
              ))}
          </div>
```

Render selected-day tasks under the strip:

```tsx
          <div className="learning-plan-day-tasks" aria-label="所选日期任务">
            {calendarLoading && <span>日历加载中</span>}
            {!calendarLoading && dayItems.length === 0 && (
              <span>这一天暂无计划任务</span>
            )}
            {!calendarLoading &&
              dayItems.map((item) => {
                const updating = checkinUpdatingItemId === item.itemId;
                const statusText = checkinLabel(item.checkin?.status);
                return (
                  <div className="learning-plan-day-task" key={item.itemId}>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.estimatedMinutes} 分钟</span>
                      {statusText && <em>今日：{statusText}</em>}
                    </div>
                    <div className="learning-plan-checkin-actions">
                      {(["done", "partial", "skipped"] as const).map((status) => (
                        <button
                          type="button"
                          key={status}
                          disabled={!canCheckIn || updating}
                          onClick={() => onCheckIn(item, status, selectedDate)}
                        >
                          {updating
                            ? "记录中"
                            : checkinLabels[status].replace("已", "")}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
          </div>
```

- [ ] **Step 5: Update `App.tsx` state and loaders**

In `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`, update learning imports:

```ts
  getLearningCalendar,
  getLearningPlan,
  listLearningPlans,
  type LearningCalendarDto,
  type LearningPlanCheckinStatus,
  type LearningPlanDto,
  type LearningPlanItemDto,
  type LearningPlanStatus,
  type LearningPlanSummaryDto,
```

Add state near existing learning-plan state:

```ts
  const [learningPlanSummaries, setLearningPlanSummaries] = useState<
    LearningPlanSummaryDto[]
  >([]);
  const [selectedLearningPlanId, setSelectedLearningPlanId] = useState<string>();
  const [selectedLearningDate, setSelectedLearningDate] = useState(() => todayString());
  const [learningCalendar, setLearningCalendar] = useState<LearningCalendarDto>();
  const [learningPlansLoading, setLearningPlansLoading] = useState(true);
  const [learningCalendarLoading, setLearningCalendarLoading] = useState(false);
  const [learningCalendarError, setLearningCalendarError] = useState<string>();
```

Add refs:

```ts
  const learningPlansRequestIdRef = useRef(0);
  const learningCalendarRequestIdRef = useRef(0);
```

Add helpers near `todayString`:

```ts
function addDays(dateValue: string, days: number): string {
  const date = new Date(`${dateValue}T00:00:00`);
  date.setDate(date.getDate() + days);
  return todayString(date);
}
```

Add loaders:

```ts
  const loadLearningPlanSummaries = useCallback(async () => {
    const requestId = ++learningPlansRequestIdRef.current;
    setLearningPlansLoading(true);
    setLearningPlanError(undefined);
    try {
      const summaries = await listLearningPlans(userId, { limit: 20 });
      if (learningPlansRequestIdRef.current !== requestId) return;

      setLearningPlanSummaries(summaries);
      setSelectedLearningPlanId((currentId) => {
        if (currentId && summaries.some((summary) => summary.planId === currentId)) {
          return currentId;
        }
        return summaries[0]?.planId;
      });
      if (summaries.length === 0) {
        setLearningPlan(null);
      }
    } catch {
      if (learningPlansRequestIdRef.current === requestId) {
        setLearningPlanError("学习计划列表加载失败");
      }
    } finally {
      if (learningPlansRequestIdRef.current === requestId) {
        setLearningPlansLoading(false);
      }
    }
  }, [userId]);

  const loadSelectedLearningPlan = useCallback(async () => {
    if (!selectedLearningPlanId) return;

    const requestId = ++learningPlanRequestIdRef.current;
    setLearningPlanLoading(true);
    setLearningPlanError(undefined);
    try {
      const plan = await getLearningPlan(userId, selectedLearningPlanId);
      if (learningPlanRequestIdRef.current === requestId) {
        setLearningPlan(plan);
      }
    } catch {
      if (learningPlanRequestIdRef.current === requestId) {
        setLearningPlanError("学习计划加载失败");
      }
    } finally {
      if (learningPlanRequestIdRef.current === requestId) {
        setLearningPlanLoading(false);
      }
    }
  }, [selectedLearningPlanId, userId]);

  const loadLearningCalendar = useCallback(async () => {
    if (!selectedLearningPlanId) {
      setLearningCalendar(undefined);
      return;
    }

    const requestId = ++learningCalendarRequestIdRef.current;
    setLearningCalendarLoading(true);
    setLearningCalendarError(undefined);
    try {
      const calendar = await getLearningCalendar(userId, {
        from: selectedLearningDate,
        to: addDays(selectedLearningDate, 6),
        planId: selectedLearningPlanId,
      });
      if (learningCalendarRequestIdRef.current === requestId) {
        setLearningCalendar(calendar);
      }
    } catch {
      if (learningCalendarRequestIdRef.current === requestId) {
        setLearningCalendarError("学习日历加载失败");
      }
    } finally {
      if (learningCalendarRequestIdRef.current === requestId) {
        setLearningCalendarLoading(false);
      }
    }
  }, [selectedLearningDate, selectedLearningPlanId, userId]);
```

Replace the old `loadLearningPlan` initial effect with:

```ts
  useEffect(() => {
    void loadLearningPlanSummaries();
  }, [loadLearningPlanSummaries]);

  useEffect(() => {
    void loadSelectedLearningPlan();
  }, [loadSelectedLearningPlan]);

  useEffect(() => {
    void loadLearningCalendar();
  }, [loadLearningCalendar]);
```

After `createLearningPlan`, status update, and check-in success, refresh:

```ts
      setLearningPlan(plan);
      setSelectedLearningPlanId(plan.planId);
      void loadLearningPlanSummaries();
      void loadLearningCalendar();
```

For status update and check-in, use the same two refresh calls after `setLearningPlan(plan)`.

- [ ] **Step 6: Pass new props to `LearningPlanPanel`**

In the `LearningPlanPanel` JSX call in `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`, pass:

```tsx
          plan={learningPlan}
          planSummaries={learningPlanSummaries}
          calendar={learningCalendar}
          selectedPlanId={selectedLearningPlanId}
          selectedDate={selectedLearningDate}
          loading={learningPlanLoading}
          listLoading={learningPlansLoading}
          calendarLoading={learningCalendarLoading}
          error={learningPlanError}
          calendarError={learningCalendarError}
          creating={learningPlanCreating}
          statusUpdating={learningPlanStatusUpdating}
          checkinUpdatingItemId={learningPlanCheckinItemId}
          latestPrompt={lastLearningPlanPrompt}
          today={todayString()}
          onCreatePlan={() => void handleCreateLearningPlan()}
          onSelectPlan={(planId) => setSelectedLearningPlanId(planId)}
          onSelectDate={(date) => setSelectedLearningDate(date)}
          onUpdateStatus={(status) => void handleUpdateLearningPlanStatus(status)}
          onCheckIn={(item, status, checkinDate) =>
            void handleLearningPlanCheckIn(item, status, checkinDate)
          }
          onRetry={() => void loadLearningPlanSummaries()}
```

- [ ] **Step 7: Add CSS for selector, date strip, and day tasks**

In `/Users/caisufang/projects/agent-hub-frontend/src/App.css`, add after `.learning-plan-body`:

```css
.learning-plan-selector {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.learning-plan-selector button {
  flex: 0 0 148px;
  display: grid;
  gap: 3px;
  border: 1px solid #d8e1ee;
  border-radius: 7px;
  padding: 7px 8px;
  color: #334155;
  background: #ffffff;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.learning-plan-selector button.is-active {
  border-color: #9ac7ad;
  background: #ecfdf5;
}

.learning-plan-selector span,
.learning-plan-selector strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.learning-plan-selector span {
  font-size: 12px;
  font-weight: 700;
}

.learning-plan-selector strong {
  color: #728096;
  font-size: 11px;
  font-weight: 500;
}

.learning-plan-calendar-strip {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  border-block: 1px solid #e5ebf3;
  padding-block: 8px;
}

.learning-plan-calendar-strip > span {
  color: #991b1b;
  font-size: 12px;
}

.learning-plan-date-button {
  flex: 0 0 54px;
  border: 1px solid #d8e1ee;
  border-radius: 7px;
  padding: 6px 7px;
  color: #475569;
  background: #ffffff;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.learning-plan-date-button.is-active {
  color: #14532d;
  border-color: #9ac7ad;
  background: #ecfdf5;
  font-weight: 700;
}

.learning-plan-day-tasks {
  display: grid;
  gap: 7px;
}

.learning-plan-day-tasks > span {
  color: #728096;
  font-size: 12px;
}

.learning-plan-day-task {
  display: grid;
  gap: 7px;
  border: 1px solid #e1e7f0;
  border-radius: 8px;
  padding: 9px;
  background: #ffffff;
}

.learning-plan-day-task div:first-child {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.learning-plan-day-task strong {
  flex: 1 1 100%;
  color: #263348;
  font-size: 12px;
  line-height: 1.35;
}

.learning-plan-day-task span,
.learning-plan-day-task em {
  border-radius: 999px;
  padding: 3px 7px;
  color: #475569;
  background: #f1f5f9;
  font-size: 11px;
  font-style: normal;
}

.learning-plan-day-task em {
  color: #166534;
  background: #f0fdf4;
  font-weight: 700;
}
```

- [ ] **Step 8: Run frontend verification**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
```

Expected: all three commands pass.

- [ ] **Step 9: Commit frontend UI task locally**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
git add contracts/learning.contract.tsx src/App.css src/App.tsx src/chat/LearningPlanPanel.tsx
git commit -m "feat: add learning plan calendar UI"
```

---

### Task 5: Final Cross-Repo Verification

**Files:**
- Verify only, no source edits expected.

**Interfaces:**
- Consumes completed Tasks 1-4.
- Produces final clean working trees and ready-to-review commits.

- [ ] **Step 1: Run backend full verification**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
.venv/bin/python -m unittest
git diff --check
git status --short
```

Expected:

- unittest reports all tests passing.
- `git diff --check` prints no output.
- `git status --short` prints no output after backend commits are made.

- [ ] **Step 2: Run frontend full verification**

Run:

```bash
cd /Users/caisufang/projects/agent-hub-frontend
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
git diff --check
git status --short
```

Expected:

- contracts pass.
- lint exits `0`.
- build exits `0`.
- `git diff --check` prints no output.
- `git status --short` prints no output after frontend commits are made.

- [ ] **Step 3: Confirm backend pushed and frontend local only**

Run:

```bash
cd /Users/caisufang/projects/agent-hub
git log -2 --oneline
git status --short

cd /Users/caisufang/projects/agent-hub-frontend
git log -2 --oneline
git status --short
```

Expected:

- Backend latest relevant commit includes `feat: add learning plan calendar api` and has already been pushed to `origin/main`.
- Frontend latest relevant commits are local.
- Both working trees are clean.

## Self-Review

Spec coverage:

- Multiple plans are covered by Task 1 summaries, Task 2 list endpoint, and Task 4 selector.
- Specific plan detail is covered by Task 1 `get_learning_plan`, Task 2 detail route, Task 3 API helper, and Task 4 selected plan loading.
- Calendar range is covered by Task 1 calendar read model, Task 2 calendar endpoint, Task 3 API helper, and Task 4 7-day strip.
- Selected-date check-ins are covered by Task 1 calendar check-in mapping and Task 4 `onCheckIn` using selected date.
- Calendar date validation is covered by Task 1 and Task 2 tests.
- Full month calendar, item CRUD, recurrence editing, multi-child, login, reminders, analytics, and Java extraction remain outside scope.

Placeholder scan:

- This plan uses no placeholder markers or copy-by-reference instructions.
- Every task lists concrete files, interfaces, test code, implementation code, commands, expected failures, and expected pass criteria.

Type consistency:

- Backend consistently uses Python snake_case for functions and SQLite columns.
- API and frontend DTOs consistently use camelCase fields.
- `planId`, `itemId`, `checkinDate`, `selectedLearningPlanId`, and `selectedLearningDate` are used consistently across API and UI tasks.
