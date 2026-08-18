# First Grade Chinese Literacy Support Design

## Goal

Build the first real business slice on Agent Hub: a first-grade Chinese literacy support assistant for parents.

The assistant helps parents record weak spots before or during first grade, keep a lightweight learning profile, and receive gentle, practical advice. V1 focuses on recording Chinese literacy weaknesses. Later versions add weekly plans, mistake tracking, exercise banks, and multiple children.

## Product Positioning

This feature is a learning support and family practice assistant. It is not a medical, psychological, or special-education diagnosis tool.

The core user is a parent who notices concrete behavior, for example:

- `孩子 b p d q 总混，拼音拼读慢。`
- `识字很吃力，见过几次的字还是容易忘。`
- `朗读时经常漏字、跳行。`

The system should turn this into structured records and practical next-step suggestions without making alarming conclusions.

## V1 Scope

V1 includes:

- A default child profile per `userId`.
- Chinese literacy weakness records for the default child.
- A local skill named `chinese_literacy_support`.
- A tool named `record_chinese_literacy_weakness`.
- Backend APIs for profile and weakness records.
- Frontend learning profile panel showing current weak spots.
- Agent-assisted recording from natural language chat.

V1 does not include:

- Weekly study plans.
- Mistake notebook.
- Exercise bank.
- Multiple children.
- Formal login or user account management.
- Uploaded textbooks or school materials.
- Teacher-facing workflows.

## Future Backlog

These are explicitly planned after V1:

1. Weekly enhancement plan
   - Generate 3-day and 7-day plans from active weaknesses.
   - Include daily goal, practice method, parent guidance, and observation metric.
   - Save generated plans for later review.

2. Review and adjustment
   - Parent reports how the child did today.
   - Agent marks a weakness as `improving`, keeps it `active`, or suggests changing practice style.
   - Later plans use review history.

3. Mistake notebook
   - Record concrete mistakes, such as confused pinyin, missed characters, or reading errors.
   - Link mistakes back to a weakness.
   - Show recurring patterns.

4. Exercise bank
   - Provide age-appropriate practice items for pinyin, character recognition, reading, and expression.
   - Keep generated exercises traceable to the weakness they support.
   - Avoid overloading the child; practice should stay short and parent-friendly.

5. Multiple children
   - Add multiple child profiles under one `userId`.
   - Let the frontend switch active `childId`.
   - Keep all profiles, weaknesses, plans, mistakes, and exercises isolated by `userId + childId`.

6. Learning resources and import
   - Later support textbook version, school schedule, uploaded materials, or teacher-provided word lists.
   - Keep this outside V1 because it introduces file handling and content provenance.

## Naming And Identity

- API JSON uses camelCase: `userId`, `childId`, `weaknessId`, `createdAt`, `updatedAt`.
- Python and SQLite use snake_case: `user_id`, `child_id`, `weakness_id`, `created_at`, `updated_at`.
- V1 uses `childId = default`.
- V1 profile display name defaults to `孩子`.
- Do not require or store a real child name in V1.
- `userId` continues to be the product identity boundary. Today it can be anonymous; later it comes from authenticated identity.
- `childId` belongs to the learning domain, not the auth domain.
- The schema must leave room for a future Java service to own child profiles, learning records, plans, exercises, and permissions.

## Backend Architecture

Keep the learning feature separate from chat history tables.

Add a new learning-domain store, for example `learning_store.py`, with responsibility for:

- Creating or returning the default child profile.
- Listing weakness records.
- Creating or updating weakness records.
- Validating allowed categories, severity values, and status values.

FastAPI remains the API boundary for V1. It exposes learning endpoints and also provides a request-scoped bridge so the Agent tool can record a weakness without trusting model-provided identity fields.

The existing skills registry continues to list available skills. Add `chinese_literacy_support` as another local skill. The skill gives task guidance; the tool performs persistence.

## Data Model

`child_profiles`

- `user_id` text, required
- `child_id` text, required
- `display_name` text, required, default `孩子`
- `grade` text, required, default `first_grade`
- `created_at` text ISO timestamp, required
- `updated_at` text ISO timestamp, required
- Primary key: `(user_id, child_id)`

`learning_weaknesses`

- `weakness_id` text primary key
- `user_id` text, required
- `child_id` text, required
- `subject` text, required, V1 always `chinese`
- `grade` text, required, V1 always `first_grade`
- `category` text, required
- `title` text, required
- `evidence` text, required
- `severity` text, required
- `status` text, required
- `source_run_id` text nullable
- `created_at` text ISO timestamp, required
- `updated_at` text ISO timestamp, required

Allowed `category` values:

- `pinyin`
- `character_recognition`
- `reading`
- `expression`
- `learning_habit`

Allowed `severity` values:

- `mild`
- `medium`
- `high`

Allowed `status` values:

- `active`
- `improving`
- `resolved`

V1 duplicate handling:

- If an active record already exists with the same `user_id`, `child_id`, `category`, and normalized `title`, the tool updates the existing record instead of creating a duplicate.
- The latest evidence is saved, severity can be raised or lowered, and `updated_at` changes.

## API Design

`GET /users/{userId}/children/default/profile`

- Returns the default child profile.
- Creates the default profile lazily if it does not exist.
- Response shape:

```json
{
  "userId": "anon_user_x",
  "childId": "default",
  "displayName": "孩子",
  "grade": "first_grade",
  "createdAt": "...",
  "updatedAt": "..."
}
```

`GET /users/{userId}/children/default/weaknesses`

- Returns the default child's Chinese literacy weakness records.
- Default sort: active and improving records first, then recently updated.
- Optional `status` filter can be added in V1 if simple.

`POST /users/{userId}/children/default/weaknesses`

- Creates or updates one weakness record.
- Request shape:

```json
{
  "category": "pinyin",
  "title": "b/p/d/q 混淆",
  "evidence": "家长反馈孩子读拼音时经常把 b、p、d、q 搞混。",
  "severity": "medium",
  "sourceRunId": "run_x"
}
```

- The backend sets `subject = chinese`, `grade = first_grade`, `status = active`, and `childId = default`.
- The backend rejects unsupported enum values with a 422-style validation response.

## Agent Tool

Add tool `record_chinese_literacy_weakness`.

Model-visible input:

- `category`
- `title`
- `evidence`
- `severity`

Backend-injected context:

- `user_id`
- `child_id = default`
- `source_run_id`

The model must not provide `userId`, `childId`, or database IDs. The runtime injects those values from the current chat request. This keeps the tool safe for future authenticated users and Java extraction.

The tool returns a short natural-language result, for example:

- `已记录薄弱点：b/p/d/q 混淆`
- `已更新薄弱点：b/p/d/q 混淆`

If persistence fails, the tool returns a safe failure message and the stream continues.

## Skill

Add local skill `chinese_literacy_support`.

The skill instructs the Agent to:

- Recognize first-grade Chinese literacy issues around pinyin, character recognition, reading, expression, and learning habits.
- Record a weakness when the parent clearly describes a concrete learning issue.
- Avoid diagnosing the child.
- Give short, encouraging, concrete family practice advice.
- Keep practice suggestions age-appropriate and usually within 10-15 minutes.

The skill binds to:

- `record_chinese_literacy_weakness`
- Later: plan generation, mistake notebook, and exercise bank tools.

## Frontend Experience

Add a learning profile area to the right side of the chat workspace.

The right rail should remain calm and useful:

- Top: `学习画像`
- Shows grade: `一年级`
- Shows active weakness count.
- Shows recent weakness records with category, severity, status, and updated time.
- Provides a refresh or retry state when loading fails.

The existing capability panel can remain below the learning profile area or be visually compressed. The first screen should still feel like an Agent workspace, not a school report dashboard.

After a chat run finishes, the frontend refreshes weakness records. If the stream includes a successful `record_chinese_literacy_weakness` tool event, the frontend can refresh immediately after that event as well.

## Data Flow

1. Frontend loads `userId`.
2. Frontend requests default child profile and weakness records.
3. Parent chats naturally about the child's issue.
4. Agent uses `chinese_literacy_support` instructions.
5. If the issue is concrete, Agent calls `record_chinese_literacy_weakness`.
6. Backend injects `user_id`, `child_id`, and `source_run_id`.
7. Learning store creates or updates a weakness.
8. Stream continues and final answer includes a short summary plus next-step suggestion.
9. Frontend refreshes learning profile.

## Error Handling

- Learning panel load failures should not block chat.
- Weakness recording tool failures should not crash Agent runs.
- API validation errors must be clear enough for frontend debugging.
- Unknown `userId` still works by lazily creating the default child profile.
- If the model tries to record vague content, it should ask one concise follow-up question instead of saving a low-quality record.

## Safety And Privacy

- Do not ask for the child's real name in V1.
- Do not store sensitive family, medical, or school identity data.
- Avoid labels such as `障碍`, `疾病`, or diagnosis-like claims.
- Say `可能需要继续观察` rather than making categorical judgments.
- Recommend consulting a teacher or professional only when the parent describes severe, persistent, or distressing issues; phrase this as support, not alarm.

## Testing

Backend tests:

- Learning store initializes tables.
- Default profile is created lazily.
- Weakness records can be created and listed.
- Duplicate active weakness updates instead of duplicating.
- Invalid category, severity, or status is rejected.
- Learning APIs isolate by `userId`.
- Agent recording tool injects identity from request context and does not trust model input.
- `chinese_literacy_support` appears in `/skills` and `/capabilities`.

Frontend contract tests:

- Learning API client builds expected paths.
- Learning profile panel renders loading, error, empty, and populated states.
- Active weakness count ignores resolved records.
- Chat completion can trigger a learning profile refresh.

Integration smoke:

- Start backend and frontend.
- Ask: `孩子 b p d q 经常混，拼音拼读慢。`
- Verify the Agent records one weakness and the learning profile panel shows it.

## Java Extraction Path

Keep the learning domain behind stable API and store boundaries.

Possible later split:

- Java identity service owns authenticated users and families.
- Java learning service owns child profiles, weakness records, plans, mistakes, and exercise banks.
- Python Agent runtime calls Java learning APIs as tools.
- Frontend reads learning data from the same API contract, regardless of whether Python or Java implements it.

For V1, Python can own the tables. The DTOs and service boundaries should already look like a future Java service contract.

## Open Decisions Resolved For V1

- Use default single child only.
- Use Chinese literacy only.
- Use Agent-assisted recording, not manual-first forms.
- Store structured weakness records outside chat history.
- Keep weekly plans, mistake notebook, exercise bank, and multiple children out of V1 but explicitly in the backlog.
