# Learning Plan V2 Calendar And Parallel Plans Design

## Goal

Extend Learning Plan V1 from a single current-plan execution panel into a small planning workspace that supports multiple parallel plans and a date-based calendar view.

V2 should let parents keep several plans at the same time, switch between them, inspect what is scheduled for a selected day, and check in tasks for that date.

## Product Direction

The product is still parent-facing and lightweight. A parent should be able to answer three questions quickly:

- What plans do I currently have?
- What should we do today or on a selected day?
- Which tasks have already been checked in?

The UI should stay compact because the right rail also contains the learning profile. V2 uses a 7-day strip instead of a full month calendar. The backend contract should still support later month and agenda views.

## Existing V1 Baseline

V1 already has:

- `learning_plans`
- `learning_plan_items`
- `learning_plan_checkins`
- `checkin_date` on every check-in
- plan statuses: `draft`, `active`, `paused`, `completed`, `archived`
- no uniqueness constraint that limits a user to one active plan
- current-plan endpoint:
  `GET /users/{userId}/children/default/learning-plans/current`

V2 should build on this schema. It should not redesign plan persistence or require a migration that breaks existing V1 records.

## V2 Scope

Included:

- List multiple plans for the default child.
- Fetch one specific plan by `planId`.
- Return a calendar range derived from plans, items, and check-ins.
- Let the frontend select a plan from the right rail.
- Show a 7-day calendar strip.
- Show selected-date tasks and their check-in state.
- Allow date-specific check-in using the existing V1 check-in endpoint.
- Keep the current-plan endpoint for compatibility.

Not included:

- Full month calendar UI.
- Dragging tasks between dates.
- Recurring schedule editing.
- Plan item CRUD.
- Automatic plan rebalancing.
- Multiple children.
- User login or permissions beyond current `userId`.
- Java service extraction in this step.

## Backend API Design

### List Plans

`GET /users/{userId}/children/default/learning-plans`

Query parameters:

- `status`: optional plan status filter.
- `limit`: optional, default `20`, clamped to `1..100`.

Response is a list of plan summaries, ordered by:

1. `active`
2. `draft`
3. `paused`
4. `completed`
5. `archived`
6. newest `updatedAt`

Summary response shape:

```json
[
  {
    "planId": "plan_x",
    "userId": "user-a",
    "childId": "default",
    "title": "本周学习计划",
    "goal": "每天 15 分钟，重点拼音和口算。",
    "status": "active",
    "startDate": "2026-08-19",
    "endDate": "2026-08-25",
    "createdFromPrompt": "请制定一周学习计划。",
    "itemCount": 4,
    "todayCheckinCount": 2,
    "createdAt": "2026-08-19T00:00:00+00:00",
    "updatedAt": "2026-08-19T08:00:00+00:00"
  }
]
```

The summary intentionally avoids returning all plan items. This keeps the list endpoint useful when the project later supports many plans.

### Get Plan

`GET /users/{userId}/children/default/learning-plans/{planId}`

Response uses the existing V1 full plan shape:

- plan fields
- `items`
- each item's `checkins`

This endpoint powers plan switching. The frontend should select a plan summary, then fetch the full selected plan.

### Calendar Range

`GET /users/{userId}/children/default/learning-calendar?from=YYYY-MM-DD&to=YYYY-MM-DD`

Optional query parameters:

- `planId`: return calendar entries for one plan only.
- `status`: filter plans by status, useful later for completed-plan review.

Response shape:

```json
{
  "from": "2026-08-19",
  "to": "2026-08-25",
  "days": [
    {
      "date": "2026-08-19",
      "plans": [
        {
          "planId": "plan_x",
          "title": "本周学习计划",
          "status": "active",
          "items": [
            {
              "itemId": "item_x",
              "subject": "chinese",
              "title": "语文 · 拼音：b/p/d/q 混淆",
              "estimatedMinutes": 15,
              "checkin": {
                "checkinId": "checkin_x",
                "checkinDate": "2026-08-19",
                "status": "done",
                "note": "",
                "createdAt": "2026-08-19T08:00:00+00:00",
                "updatedAt": "2026-08-19T08:00:00+00:00"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

Calendar date validation:

- `from` and `to` must be `YYYY-MM-DD`.
- `from` must be less than or equal to `to`.
- Range length is clamped to at most `31` days for V2.

Plan inclusion rules:

- If `planId` is provided, include that plan even if it is `completed` or `paused`.
- If `planId` is omitted, include non-archived plans.
- A plan with `startDate` and `endDate` only appears on dates within that range.
- A plan without date bounds can appear in the requested range.
- `archived` plans are excluded unless a future endpoint explicitly requests archives.

Item scheduling rule for V2:

- V2 treats every item in an included plan as visible on every included date.
- The existing `frequency` field remains guidance copy.
- Later schedule editing can add a `learning_plan_item_schedules` table without breaking the calendar response shape.

### Existing Check-In Endpoint

V2 keeps:

`POST /users/{userId}/children/default/learning-plans/{planId}/items/{itemId}/checkins`

The frontend sends the selected calendar date as `checkinDate`. The endpoint remains an upsert by `(userId, childId, itemId, checkinDate)`.

## Backend Store Design

Add store methods:

- `list_learning_plan_summaries(user_id, child_id=DEFAULT_CHILD_ID, status=None, limit=20, today=None)`
- `get_learning_plan(user_id, plan_id)`
- `get_learning_calendar(user_id, from_date, to_date, child_id=DEFAULT_CHILD_ID, plan_id=None, status=None)`

Keep V1 methods:

- `get_current_learning_plan`
- `create_learning_plan_from_weaknesses`
- `update_learning_plan_status`
- `upsert_learning_plan_checkin`

Add dataclasses:

- `LearningPlanSummary`
- `LearningCalendar`
- `LearningCalendarDay`
- `LearningCalendarPlan`
- `LearningCalendarItem`

Serialization should stay in `learning_store.py` for now:

- `serialize_learning_plan_summary`
- `serialize_learning_calendar`

The future Java learning service can own the same aggregate boundaries:

- plan summaries
- plan detail
- calendar range
- check-in command

## Frontend Design

### API Layer

Extend `src/api/learning.ts` with:

- `LearningPlanSummaryDto`
- `LearningCalendarDto`
- `LearningCalendarDayDto`
- `LearningCalendarPlanDto`
- `LearningCalendarItemDto`
- `listLearningPlans(userId, options)`
- `getLearningPlan(userId, planId)`
- `getLearningCalendar(userId, options)`

Keep V1 functions unchanged for compatibility.

### App State

Add state in `App.tsx`:

- `learningPlanSummaries`
- `selectedLearningPlanId`
- `learningCalendar`
- `selectedLearningDate`
- `learningPlansLoading`
- `learningCalendarLoading`
- related error states

Behavior:

- Initial load fetches plan summaries.
- If no selected plan exists, choose the first summary by backend ordering.
- Fetch full plan detail for selected plan.
- Fetch 7-day calendar for selected plan and selected date window.
- After create, status update, or check-in, refresh summaries, selected plan, and calendar.

### Learning Plan Panel

Update `LearningPlanPanel` to support:

- Plan list or compact selector at the top.
- Multiple active plans visible as separate rows or chips.
- 7-day calendar strip under the plan selector.
- Selected-date task list.
- Existing subject-grouped plan detail remains below the date actions or inside the selected plan area.

The right rail should remain compact:

- Plan selector row is short.
- Calendar strip is horizontal and button-based.
- Selected-date tasks remain scrollable inside the plan panel.
- Full month calendar is deferred.

### Calendar Interaction

Default selected date is today.

Date labels:

- `今天` for today's date.
- Weekday plus `M/D` for other dates.

Clicking a date:

- updates `selectedLearningDate`
- reloads calendar range only if the date falls outside the currently loaded range
- shows check-in status for that date

Checking in:

- uses the existing check-in endpoint
- sends the selected date as `checkinDate`
- updates selected plan and calendar after success

## Error Handling

Backend:

- invalid date returns `422`
- unknown plan returns `404`
- invalid status returns `422`
- calendar range over `31` days returns `422`

Frontend:

- plan list error displays inside the learning plan panel
- calendar error displays inside the date strip area
- selected plan fetch error keeps the plan selector usable
- check-in error displays without clearing the existing calendar

## Testing

Backend tests:

- listing plans returns multiple parallel active plans.
- plan summaries include `itemCount` and `todayCheckinCount`.
- get plan returns full V1 plan shape for a selected `planId`.
- calendar endpoint returns days, plans, items, and selected-date check-ins.
- calendar supports `planId` filtering.
- invalid calendar dates and oversized ranges return `422`.

Frontend contract tests:

- API helpers call the new endpoints with camelCase query and response fields.
- `LearningPlanPanel` renders a plan selector.
- `LearningPlanPanel` renders the 7-day calendar strip.
- selected-date tasks show check-in state.
- CSS keeps the plan content scrollable.

Verification commands:

- Backend: `.venv/bin/python -m unittest`
- Frontend: `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts`
- Frontend: `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint`
- Frontend: `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build`

## Non-Goals

- Full calendar month UI.
- Task drag-and-drop.
- Persistent custom recurrence rules.
- Teacher or classroom collaboration.
- Reminder notifications.
- Analytics dashboards.
- Multi-child selector.
- Java service extraction in V2.
