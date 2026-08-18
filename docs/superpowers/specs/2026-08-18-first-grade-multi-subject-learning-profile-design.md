# First Grade Multi-Subject Learning Profile Design

## Goal

Extend the current first-grade Chinese literacy slice into a broader learning
profile for Chinese, English, and Math.

This version should still be a focused V1: it records subject-specific weak
spots, lets the agent identify and save concrete issues from parent chat, and
shows the parent a more intuitive profile view. It does not yet add weekly
plans, mistake notebooks, exercise banks, or multiple children.

## Product Positioning

The feature is a parent-facing learning support profile for children entering or
starting first grade. It helps a parent turn everyday observations into a
structured picture of weak spots across three subjects.

The product must stay gentle and practical:

- It records learning phenomena, not labels about the child.
- It avoids medical, psychological, or special-education diagnosis.
- It hides sensitive identity details before persistence.
- It should make the parent feel oriented, not alarmed.

Example parent inputs:

- `英语字母 b 和 d 总认反，听音也不太分得清。`
- `数学 20 以内加减法很慢，数感好像比较弱。`
- `语文朗读经常漏字，英语单词也记不住。`

## V1 Scope

Included:

- Support learning weakness records for `chinese`, `english`, and `math`.
- Keep the existing default child profile per `userId`.
- Add subject-aware backend APIs.
- Keep existing Chinese endpoints compatible.
- Add a general learning weakness recording tool for the agent.
- Add a local skill for first-grade multi-subject learning support.
- Update frontend learning profile data types and panel rendering.
- Add Canvas-based hexagon profile visualization by subject.

Not included:

- Weekly plans.
- Mistake notebook.
- Exercise bank.
- Multiple children.
- Formal login or permissions.
- Textbook version import.
- Teacher or classroom workflows.

## Subject Model

Allowed subjects:

- `chinese`
- `english`
- `math`

The database already has a `subject` column on `learning_weaknesses`. The next
implementation should make this column a real domain dimension instead of always
using `chinese`.

The existing `userId + childId` identity boundary remains unchanged. The future
Java learning service should be able to own this domain later with the same
natural aggregate: child profile, subject profile, weaknesses, plans, mistakes,
and exercises.

## Category Model

Use subject-specific category values. Keep values stable and English-like for
API/storage, while accepting common Chinese aliases in tools and API requests.

Chinese categories:

- `pinyin`: 拼音
- `character_recognition`: 识字
- `reading`: 朗读
- `expression`: 表达
- `learning_habit`: 学习习惯

English categories:

- `listening`: 听音辨音
- `phonics`: 字母/自然拼读
- `vocabulary`: 词汇
- `speaking`: 口语表达
- `learning_habit`: 学习习惯

Math categories:

- `number_sense`: 数感
- `calculation`: 计算
- `word_problem`: 应用题
- `geometry`: 图形空间
- `learning_habit`: 学习习惯

Allowed severity values stay:

- `mild`
- `medium`
- `high`

Allowed status values stay:

- `active`
- `improving`
- `resolved`

## Backend Architecture

Keep `learning_store.py` as the learning-domain boundary for now. It should
evolve from Chinese-only helper methods into subject-aware methods.

Expected store changes:

- Add subject validation and alias normalization.
- Normalize category values with subject context.
- List weaknesses by optional subject.
- Upsert weakness with explicit subject.
- Keep sensitive text sanitization in the store so API and tools share the same
  protection.
- Keep duplicate active record uniqueness based on
  `user_id + child_id + subject + category + normalized_title`.

The API layer should not duplicate the subject/category business rules. It
should parse request shape, call normalization/store methods, and return
camelCase JSON.

## API Design

Keep existing endpoints:

`GET /users/{userId}/children/default/profile`

`GET /users/{userId}/children/default/weaknesses`

- Continue returning all weakness records by default.
- Add optional `subject=chinese|english|math`.
- Keep optional `status`.

`POST /users/{userId}/children/default/weaknesses`

- Keep as a compatibility endpoint.
- Default subject remains `chinese`.

Add subject-aware endpoint:

`POST /users/{userId}/children/default/subjects/{subject}/weaknesses`

Request:

```json
{
  "category": "calculation",
  "title": "20 以内加减法慢",
  "evidence": "家长反馈孩子做 20 以内加减法常要数手指。",
  "severity": "medium",
  "sourceRunId": "run_x"
}
```

Response:

```json
{
  "weaknessId": "weakness_x",
  "userId": "anon_user_x",
  "childId": "default",
  "subject": "math",
  "grade": "first_grade",
  "category": "calculation",
  "title": "20 以内加减法慢",
  "evidence": "家长反馈孩子做 20 以内加减法常要数手指。",
  "severity": "medium",
  "status": "active",
  "sourceRunId": "run_x",
  "createdAt": "...",
  "updatedAt": "..."
}
```

Unsupported subject/category/severity/status should return 422-style validation
errors.

## Agent Tools And Skills

Add a general tool:

`record_learning_weakness`

Model-visible input:

- `subject`
- `category`
- `title`
- `evidence`
- `severity`

Backend-injected context remains:

- `user_id`
- `child_id = default`
- `source_run_id`

The tool must not accept `userId`, `childId`, or database IDs from the model.

The existing `record_chinese_literacy_weakness` can remain as a compatibility
tool in V1, but the new multi-subject skill should prefer
`record_learning_weakness`.

Add a new skill:

`first_grade_learning_support`

Skill behavior:

- Recognize concrete first-grade weak spots in Chinese, English, and Math.
- Record a weakness only when the parent gives enough concrete evidence.
- Choose subject and category from the allowed values.
- Hide real names, school, address, phone, diagnosis labels, and family identity
  details before calling the tool.
- Give short, encouraging, practical advice.
- Keep practice suggestions usually within 10-15 minutes.
- Ask one concise clarification question if the input is too vague.

## Frontend Data Flow

Update frontend DTOs:

- `LearningSubject = "chinese" | "english" | "math"`
- `WeaknessCategory` includes all subject category values.
- `LearningWeaknessDto.subject` can be any supported subject.

Update API helpers:

- `listDefaultChildWeaknesses(userId, options?: { subject?: LearningSubject })`
- Existing calls can continue without options to get all records.

Update stream refresh:

- Refresh learning profile when either `record_learning_weakness` or
  `record_chinese_literacy_weakness` finishes.
- Continue refreshing after stream completion.

## Learning Profile UI

The right-side learning profile panel should become multi-subject without
turning into a large dashboard.

Recommended layout:

- Header: `学习画像`
- Canvas hexagon visualization near the top.
- Compact subject chips or tabs: `全部`, `语文`, `英语`, `数学`.
- Metrics remain simple: active count and total count.
- Weakness list is filtered by selected subject.
- Each row shows subject, category, severity, status, updated time, title, and
  evidence.

Subject labels:

- `chinese`: 语文
- `english`: 英语
- `math`: 数学

## Canvas Hexagon Visualization

Add a Canvas component, for example `LearningHexagonCanvas`.

Purpose:

- Give parents a quick visual sense of where attention is needed.
- Avoid presenting it as a precise score or ranking.

Shape:

- Canvas-based hexagon visualization.
- Display three compact subject hexagons: Chinese, English, Math.
- Each subject hexagon uses five real subject dimensions plus one deterministic
  `overall` axis.
- The `overall` axis is the rounded average of the five real dimensions.

Scoring:

- Start each dimension at 100.
- Active weakness subtracts by severity:
  - `mild`: 12
  - `medium`: 24
  - `high`: 36
- `improving` counts at half weight.
- `resolved` does not reduce the score.
- Minimum score should be clamped, for example 35, to avoid an alarming collapsed
  shape.
- Empty data renders a neutral baseline with a note-like label such as `暂无明显薄弱点`.

Visual behavior:

- Use restrained, distinct colors for three subjects.
- Keep labels short and readable.
- Canvas must have stable dimensions and resize safely.
- Provide accessible fallback text outside the canvas.
- Do not use the chart as a diagnosis or grade.

## Error Handling

Backend:

- Invalid subject/category/severity/status returns 422.
- Persistence errors keep returning safe messages from tools.
- Sanitization remains deterministic and shared.

Frontend:

- Existing learning profile loading/error states remain.
- Canvas should render a neutral state if data is missing or empty.
- If Canvas context cannot be created, show the text summary/list normally.

## Testing

Backend tests:

- Store accepts and lists `english` and `math` records.
- Subject/category validation rejects mismatches.
- Existing Chinese compatibility endpoint still records `chinese`.
- New subject endpoint records `english` and `math`.
- General tool records a weakness using injected context.
- Capabilities include the new general tool and multi-subject skill.

Frontend tests:

- API helper supports optional subject query.
- Learning DTO supports `english` and `math`.
- Panel renders subject labels and filters.
- Canvas scoring converts weakness severity/status into subject scores.
- Contract test verifies the Canvas component appears in the profile panel.

Verification:

- Backend full unittest suite.
- Backend `py_compile`.
- Backend `git diff --check`.
- Frontend `test:contracts`.
- Frontend `lint`.
- Frontend `build`.

## Rollout And Compatibility

This is an additive version.

- Existing Chinese records remain valid.
- Existing frontend can still call the old weakness list endpoint.
- Existing Chinese tool can remain registered.
- New records should prefer the general `record_learning_weakness` tool.

When a future Java learning service is extracted, the Python app should call that
service through an interface with these same subject/category contracts.

## Future Backlog

After this version:

1. Weekly plan generated from multi-subject active weaknesses.
2. Daily review that can move weaknesses to `improving` or `resolved`.
3. Mistake notebook linked to subject/category/weakness.
4. Exercise bank for Chinese, English, and Math.
5. Multiple children under one authenticated user.
6. Java learning-domain service extraction.
