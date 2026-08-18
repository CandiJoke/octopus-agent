# First Grade Multi-Subject Learning Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the first-grade learning profile from Chinese-only weakness records to Chinese, English, and Math, with a Canvas hexagon profile visualization.

**Architecture:** Keep `learning_store.py` as the temporary Python learning-domain boundary, but make subject/category validation explicit and reusable for future Java extraction. Add a general `record_learning_weakness` tool while preserving the existing Chinese compatibility tool. Update the React profile panel to consume all subjects, compute hexagon scores in a pure TypeScript module, and draw subject hexagons in a focused Canvas component.

**Tech Stack:** Python 3.11, FastAPI, SQLite, LangChain `StructuredTool`, Pydantic, React 19, TypeScript 6, Canvas 2D, Vite, `unittest`, contract tests.

## Global Constraints

- Allowed subjects are exactly `chinese`, `english`, and `math`.
- V1 keeps `childId = default`, `displayName = 孩子`, and `grade = first_grade`.
- API JSON uses camelCase and Python/SQLite use snake_case.
- Existing Chinese endpoints remain compatible.
- The model must not provide `userId`, `childId`, or database IDs to tools.
- Sensitive real names, school, address, phone, diagnosis labels, and family identity details must be hidden before persistence.
- Practice guidance must stay gentle, non-diagnostic, and parent-friendly.
- Frontend Canvas must have stable dimensions, readable labels, and accessible fallback text.
- Backend implementation must keep a future Java learning-domain service extraction straightforward.

---

### Task 1: Backend Subject-Aware Learning Store

**Files:**
- Modify: `learning_store.py`
- Modify: `test_learning_store.py`

**Interfaces:**
- Consumes: existing `LearningStore.upsert_weakness(user_id, child_id, category, title, evidence, severity, source_run_id=None)`, `LearningStore.list_weaknesses(user_id, child_id=DEFAULT_CHILD_ID, status=None)`, `serialize_learning_weakness(record)`.
- Produces:
  - `LearningSubject = Literal["chinese", "english", "math"]`
  - `LearningSubjectInput`
  - `normalize_subject_value(subject: str) -> str`
  - `normalize_category_value(subject: str, category: str) -> str`
  - `LearningStore.list_weaknesses(user_id: str, child_id: str = DEFAULT_CHILD_ID, status: str | None = None, subject: str | None = None) -> list[LearningWeaknessRecord]`
  - `LearningStore.upsert_weakness(user_id: str, child_id: str, category: str, title: str, evidence: str, severity: str, source_run_id: str | None = None, subject: str = DEFAULT_SUBJECT) -> tuple[LearningWeaknessRecord, bool]`

- [ ] **Step 1: Write failing store tests**

Add these tests to `test_learning_store.py`:

```python
def test_upsert_weakness_accepts_english_and_math_subjects(self):
    english, english_created = self.store.upsert_weakness(
        "user-a",
        DEFAULT_CHILD_ID,
        subject="english",
        category="phonics",
        title="b/d 字母认反",
        evidence="家长反馈孩子经常把 b 和 d 看反。",
        severity="medium",
    )
    math, math_created = self.store.upsert_weakness(
        "user-a",
        DEFAULT_CHILD_ID,
        subject="math",
        category="calculation",
        title="20 以内加减法慢",
        evidence="做 20 以内加减法常要数手指。",
        severity="high",
    )

    self.assertTrue(english_created)
    self.assertTrue(math_created)
    self.assertEqual(english.subject, "english")
    self.assertEqual(english.category, "phonics")
    self.assertEqual(math.subject, "math")
    self.assertEqual(math.category, "calculation")
```

```python
def test_list_weaknesses_filters_by_subject(self):
    self.store.upsert_weakness(
        "user-a",
        DEFAULT_CHILD_ID,
        subject="english",
        category="vocabulary",
        title="单词容易忘",
        evidence="学过的单词隔天就忘。",
        severity="medium",
    )
    self.store.upsert_weakness(
        "user-a",
        DEFAULT_CHILD_ID,
        subject="math",
        category="number_sense",
        title="数感弱",
        evidence="数量比较要数很久。",
        severity="mild",
    )

    english_records = self.store.list_weaknesses("user-a", subject="english")
    math_records = self.store.list_weaknesses("user-a", subject="math")

    self.assertEqual([item.subject for item in english_records], ["english"])
    self.assertEqual([item.subject for item in math_records], ["math"])
```

```python
def test_category_must_match_subject(self):
    with self.assertRaises(ValueError):
        self.store.upsert_weakness(
            "user-a",
            DEFAULT_CHILD_ID,
            subject="math",
            category="pinyin",
            title="拼音不属于数学",
            evidence="分类错配。",
            severity="medium",
        )
```

```python
def test_subject_and_category_aliases_are_normalized(self):
    record, created = self.store.upsert_weakness(
        "user-a",
        DEFAULT_CHILD_ID,
        subject="数学",
        category="计算",
        title="口算慢",
        evidence="口算 10 以内加法也会停很久。",
        severity="明显",
    )

    self.assertTrue(created)
    self.assertEqual(record.subject, "math")
    self.assertEqual(record.category, "calculation")
    self.assertEqual(record.severity, "high")
```

- [ ] **Step 2: Run failing store tests**

Run:

```bash
.venv/bin/python -m unittest test_learning_store.py
```

Expected: FAIL because `upsert_weakness` does not accept `subject`, `list_weaknesses` does not filter by subject, and `normalize_category_value` is Chinese-only.

- [ ] **Step 3: Implement subject/category domain constants and normalization**

In `learning_store.py`, add:

```python
LearningSubject = Literal["chinese", "english", "math"]
LearningSubjectInput = Literal["chinese", "english", "math", "语文", "英语", "数学"]
DEFAULT_SUBJECT = "chinese"

VALID_SUBJECTS = {"chinese", "english", "math"}
SUBJECT_ALIASES = {
    "chinese": "chinese",
    "语文": "chinese",
    "english": "english",
    "英语": "english",
    "math": "math",
    "数学": "math",
}
SUBJECT_CATEGORY_ALIASES = {
    "chinese": {
        "pinyin": "pinyin",
        "拼音": "pinyin",
        "拼读": "pinyin",
        "character_recognition": "character_recognition",
        "character-recognition": "character_recognition",
        "识字": "character_recognition",
        "认字": "character_recognition",
        "reading": "reading",
        "朗读": "reading",
        "阅读": "reading",
        "expression": "expression",
        "表达": "expression",
        "口语表达": "expression",
        "learning_habit": "learning_habit",
        "learning-habit": "learning_habit",
        "学习习惯": "learning_habit",
        "习惯": "learning_habit",
    },
    "english": {
        "listening": "listening",
        "听音": "listening",
        "听音辨音": "listening",
        "phonics": "phonics",
        "自然拼读": "phonics",
        "字母": "phonics",
        "vocabulary": "vocabulary",
        "词汇": "vocabulary",
        "单词": "vocabulary",
        "speaking": "speaking",
        "口语": "speaking",
        "口语表达": "speaking",
        "learning_habit": "learning_habit",
        "学习习惯": "learning_habit",
        "习惯": "learning_habit",
    },
    "math": {
        "number_sense": "number_sense",
        "number-sense": "number_sense",
        "数感": "number_sense",
        "calculation": "calculation",
        "计算": "calculation",
        "口算": "calculation",
        "word_problem": "word_problem",
        "word-problem": "word_problem",
        "应用题": "word_problem",
        "geometry": "geometry",
        "图形空间": "geometry",
        "图形": "geometry",
        "learning_habit": "learning_habit",
        "学习习惯": "learning_habit",
        "习惯": "learning_habit",
    },
}
VALID_CATEGORIES_BY_SUBJECT = {
    subject: set(aliases.values())
    for subject, aliases in SUBJECT_CATEGORY_ALIASES.items()
}
```

Replace `normalize_category_value(category: str)` with:

```python
def normalize_subject_value(subject: str) -> str:
    key = " ".join(str(subject).strip().split())
    normalized = SUBJECT_ALIASES.get(key) or SUBJECT_ALIASES.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported learning subject: {subject}")
    return normalized


def normalize_category_value(subject: str, category: str) -> str:
    subject = normalize_subject_value(subject)
    key = " ".join(str(category).strip().split())
    aliases = SUBJECT_CATEGORY_ALIASES[subject]
    normalized = aliases.get(key) or aliases.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported {subject} weakness category: {category}")
    return normalized
```

Keep this compatibility helper:

```python
def validate_category(category: str) -> None:
    normalize_category_value(DEFAULT_SUBJECT, category)
```

- [ ] **Step 4: Update store methods**

Change `list_weaknesses` to accept `subject`, normalize it when present, append `AND subject = ?`, and keep ordering unchanged.

Change `upsert_weakness` to accept `subject: str = DEFAULT_SUBJECT`, normalize subject first, then category with subject:

```python
subject = normalize_subject_value(subject)
category = normalize_category_value(subject, category)
```

Use `subject` instead of `DEFAULT_SUBJECT` in existing duplicate lookup, insert, and IntegrityError lookup SQL parameters.

- [ ] **Step 5: Run store tests**

Run:

```bash
.venv/bin/python -m unittest test_learning_store.py
```

Expected: PASS.

- [ ] **Step 6: Commit backend store task**

```bash
git add learning_store.py test_learning_store.py
git commit -m "feat: support multi-subject learning store"
```

---

### Task 2: Backend Subject-Aware APIs

**Files:**
- Modify: `api_server.py`
- Modify: `test_api_learning.py`

**Interfaces:**
- Consumes: `LearningStore.list_weaknesses(user_id, child_id=DEFAULT_CHILD_ID, status=None, subject=None)`, `LearningStore.upsert_weakness(user_id, child_id, category, title, evidence, severity, source_run_id=None, subject=DEFAULT_SUBJECT)`, `normalize_subject_value(subject)`, `normalize_category_value(subject, category)`.
- Produces:
  - `GET /users/{user_id}/children/default/weaknesses?subject=math`
  - `POST /users/{user_id}/children/default/subjects/{subject}/weaknesses`
  - Existing `POST /users/{user_id}/children/default/weaknesses` remains Chinese-compatible.

- [ ] **Step 1: Write failing API tests**

Add to `test_api_learning.py`:

```python
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
```

```python
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
```

```python
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
```

- [ ] **Step 2: Run failing API tests**

Run:

```bash
.venv/bin/python -m unittest test_api_learning.py
```

Expected: FAIL because the subject route and subject query behavior are missing.

- [ ] **Step 3: Update API imports and request model**

Import `LearningSubjectInput`, `normalize_subject_value`, and the new subject-aware `normalize_category_value`.

Keep `LearningWeaknessRequest.category` as the broad input type already accepted by Pydantic, because category validity depends on path subject. Keep `severity` as `WeaknessSeverityInput`.

- [ ] **Step 4: Update list endpoint**

Change `list_default_child_weaknesses`:

```python
def list_default_child_weaknesses(
    user_id: str,
    status: str | None = None,
    subject: str | None = None,
    store: LearningStore = Depends(get_learning_store),
):
    try:
        records = store.list_weaknesses(
            user_id,
            DEFAULT_CHILD_ID,
            status=status,
            subject=subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [serialize_learning_weakness(record) for record in records]
```

- [ ] **Step 5: Add subject-aware record helper and route**

Add:

```python
def record_child_weakness_for_subject(
    user_id: str,
    subject: str,
    req: LearningWeaknessRequest,
    store: LearningStore,
):
    try:
        normalized_subject = normalize_subject_value(subject)
        category = normalize_category_value(normalized_subject, req.category)
        severity = normalize_severity_value(req.severity)
        record, _ = store.upsert_weakness(
            user_id,
            DEFAULT_CHILD_ID,
            subject=normalized_subject,
            category=category,
            title=req.title,
            evidence=req.evidence,
            severity=severity,
            source_run_id=req.source_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_learning_weakness(record)
```

Make the old route call it with `DEFAULT_SUBJECT`. Add:

```python
@app.post("/users/{user_id}/children/default/subjects/{subject}/weaknesses")
def record_default_child_subject_weakness(
    user_id: str,
    subject: LearningSubjectInput,
    req: LearningWeaknessRequest,
    store: LearningStore = Depends(get_learning_store),
):
    return record_child_weakness_for_subject(user_id, subject, req, store)
```

- [ ] **Step 6: Run API tests**

Run:

```bash
.venv/bin/python -m unittest test_api_learning.py test_learning_store.py
```

Expected: PASS.

- [ ] **Step 7: Commit API task**

```bash
git add api_server.py test_api_learning.py
git commit -m "feat: expose multi-subject learning APIs"
```

---

### Task 3: General Learning Tool And Multi-Subject Skill

**Files:**
- Create: `tools/record_learning_weakness/TOOL.md`
- Create: `tools/record_learning_weakness/record_learning_weakness.py`
- Create: `skills/first_grade_learning_support/SKILL.md`
- Modify: `tools/registry.py`
- Modify: `skills/registry.py`
- Modify: `test_learning_tool.py`
- Modify: `test_tools.py`
- Modify: `test_api_capabilities.py`
- Modify: `test_api_stream_events.py`

**Interfaces:**
- Consumes: `LearningStore.upsert_weakness(user_id, child_id, category, title, evidence, severity, source_run_id=None, subject=DEFAULT_SUBJECT)`, `learning_run_context(user_id, child_id, source_run_id)`.
- Produces:
  - Tool `record_learning_weakness(subject, category, title, evidence, severity) -> str`
  - Pydantic args schema `RecordLearningWeaknessInput`
  - Skill `first_grade_learning_support`

- [ ] **Step 1: Write failing tool tests**

Add to `test_learning_tool.py`:

```python
from tools.record_learning_weakness.record_learning_weakness import run as run_general
```

Add:

```python
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
```

- [ ] **Step 2: Write failing schema/capability tests**

Update `test_tools.py` expected tool names to include `record_learning_weakness`, and add:

```python
def test_general_learning_tool_schema_explains_subject_and_category_values(self):
    record_tool = next(tool for tool in tools if tool.name == "record_learning_weakness")
    schema_text = json.dumps(
        record_tool.args_schema.model_json_schema(), ensure_ascii=False
    )

    self.assertIn("english", schema_text)
    self.assertIn("英语", schema_text)
    self.assertIn("calculation", schema_text)
    self.assertIn("计算", schema_text)
```

Update `test_api_capabilities.py` expected capability IDs:

```python
[
    "tool.calculator",
    "tool.search_knowledge",
    "tool.record_chinese_literacy_weakness",
    "tool.record_learning_weakness",
    "skill.math_problem_solver",
    "skill.knowledge_lookup",
    "skill.chinese_literacy_support",
    "skill.first_grade_learning_support",
]
```

Update `/skills` expected skill IDs to include `first_grade_learning_support`, and assert it binds `["record_learning_weakness"]`.

- [ ] **Step 3: Run failing tool/capability tests**

Run:

```bash
.venv/bin/python -m unittest test_learning_tool.py test_tools.py test_api_capabilities.py
```

Expected: FAIL because the new tool and skill do not exist.

- [ ] **Step 4: Implement general tool files**

Create `tools/record_learning_weakness/TOOL.md`:

```markdown
---
name: record_learning_weakness
description: 记录一年级语文、英语或数学学习薄弱点。仅当家长明确描述具体问题时使用。输入学科、分类、标题、依据和严重程度。
---

# Record Learning Weakness

- **subject 可用值**：`chinese` / `语文`，`english` / `英语`，`math` / `数学`
- **中文 category**：`pinyin` / `拼音`，`character_recognition` / `识字`，`reading` / `朗读`，`expression` / `表达`，`learning_habit` / `学习习惯`
- **英语 category**：`listening` / `听音辨音`，`phonics` / `自然拼读`，`vocabulary` / `词汇`，`speaking` / `口语表达`，`learning_habit` / `学习习惯`
- **数学 category**：`number_sense` / `数感`，`calculation` / `计算`，`word_problem` / `应用题`，`geometry` / `图形空间`，`learning_habit` / `学习习惯`
- **severity 可用值**：`mild` / `轻微`，`medium` / `中等`，`high` / `明显`
- **限制**：不接收 userId、childId 或数据库 ID，这些由后端运行上下文注入
- **隐私**：title 和 evidence 不要写真实姓名、学校、住址、电话、诊断标签或家庭成员身份信息
```

Create `tools/record_learning_weakness/record_learning_weakness.py` with the same DB path pattern as the Chinese tool and this schema:

```python
class RecordLearningWeaknessInput(BaseModel):
    subject: LearningSubjectInput = Field(
        description="学科。可用值：chinese/语文，english/英语，math/数学。"
    )
    category: str = Field(
        description=(
            "薄弱点分类。中文：pinyin/拼音、character_recognition/识字、reading/朗读、"
            "expression/表达、learning_habit/学习习惯；英语：listening/听音辨音、"
            "phonics/自然拼读、vocabulary/词汇、speaking/口语表达、learning_habit/学习习惯；"
            "数学：number_sense/数感、calculation/计算、word_problem/应用题、"
            "geometry/图形空间、learning_habit/学习习惯。"
        )
    )
    title: str = Field(description="短标题，只描述学习薄弱点，不写真实姓名、学校或诊断标签。")
    evidence: str = Field(description="家长描述中的具体依据，需隐藏真实姓名、学校、住址、电话和诊断标签。")
    severity: WeaknessSeverityInput = Field(
        description="严重程度。可用值：mild/轻微，medium/中等，high/明显。"
    )
```

`run(subject, category, title, evidence, severity)` should call:

```python
learning_store.upsert_weakness(
    context.user_id,
    context.child_id,
    subject=subject,
    category=category,
    title=title,
    evidence=evidence,
    severity=severity,
    source_run_id=context.source_run_id,
)
```

It returns `已记录薄弱点：{record.title}` or `已更新薄弱点：{record.title}`.

- [ ] **Step 5: Register general tool and skill**

In `tools/registry.py`, import `RecordLearningWeaknessInput` and `run as record_learning_weakness_run`, then append:

```python
ToolSpec(
    "record_learning_weakness",
    record_learning_weakness_run,
    "学习记录",
    RecordLearningWeaknessInput,
),
```

Create `skills/first_grade_learning_support/SKILL.md`:

```markdown
---
id: first_grade_learning_support
name: first_grade_learning_support
display_name: First Grade Learning Support
description: 面向一年级语文、英语和数学薄弱点识别和家庭练习建议的技能，会在家长明确描述问题时记录多学科学习薄弱点。
category: 学习支持
status: available
source: local
enabled: true
tools: record_learning_weakness
---

# First Grade Learning Support

- 当用户描述孩子在语文、英语或数学上的具体问题时，先识别 subject 和 category。
- 如果描述足够具体，调用 `record_learning_weakness` 保存记录。
- 调用工具前隐藏真实姓名、学校、住址、电话、诊断标签和家庭成员身份信息，只保留学习现象。
- subject 使用 `chinese`、`english` 或 `math`。
- 语文 category 使用 `pinyin`、`character_recognition`、`reading`、`expression` 或 `learning_habit`。
- 英语 category 使用 `listening`、`phonics`、`vocabulary`、`speaking` 或 `learning_habit`。
- 数学 category 使用 `number_sense`、`calculation`、`word_problem`、`geometry` 或 `learning_habit`。
- severity 使用 `mild`、`medium` 或 `high`。
- 不做医学、心理或特殊教育诊断，不使用吓人的标签。
- 回答要温和、短、可执行，适合家长在家陪练。
- 建议练习通常控制在 10-15 分钟。
- 如果问题描述太泛，先问一个简短澄清问题，不要保存低质量记录。
```

Add `SkillSpec("first_grade_learning_support")` in `skills/registry.py`.

- [ ] **Step 6: Update stream context test**

In `test_api_stream_events.py`, update the context test fake agent tool name or add a second assertion so streamed `tool_end` events for `record_learning_weakness` still run with `learning_run_context`.

- [ ] **Step 7: Run tool/capability tests**

Run:

```bash
.venv/bin/python -m unittest test_learning_tool.py test_tools.py test_api_capabilities.py test_api_stream_events.py
```

Expected: PASS.

- [ ] **Step 8: Commit tool and skill task**

```bash
git add tools/record_learning_weakness tools/registry.py skills/first_grade_learning_support skills/registry.py test_learning_tool.py test_tools.py test_api_capabilities.py test_api_stream_events.py
git commit -m "feat: add multi-subject learning tool"
```

---

### Task 4: Frontend Multi-Subject API And Hexagon Canvas

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`
- Create: `/Users/caisufang/projects/agent-hub-frontend/src/chat/learningHexagon.ts`
- Create: `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningHexagonCanvas.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`

**Interfaces:**
- Consumes: `LearningWeaknessDto[]`.
- Produces:
  - `LearningSubject = "chinese" | "english" | "math"`
  - `listDefaultChildWeaknesses(userId, options?: { subject?: LearningSubject })`
  - `calculateSubjectHexagonScores(weaknesses: LearningWeaknessDto[])`
  - React component `LearningHexagonCanvas({ weaknesses }: { weaknesses: LearningWeaknessDto[] })`

- [ ] **Step 1: Write failing frontend contract tests**

In `contracts/learning.contract.tsx`, add English and Math weaknesses:

```ts
{
  weaknessId: "weakness-c",
  userId: "user-a",
  childId: "default",
  subject: "english",
  grade: "first_grade",
  category: "phonics",
  title: "b/d 字母认反",
  evidence: "经常把 b 和 d 看反。",
  severity: "medium",
  status: "active",
  createdAt: "2026-08-18T00:00:00Z",
  updatedAt: "2026-08-18T10:00:00+08:00",
},
{
  weaknessId: "weakness-d",
  userId: "user-a",
  childId: "default",
  subject: "math",
  grade: "first_grade",
  category: "calculation",
  title: "口算慢",
  evidence: "10 以内口算会停很久。",
  severity: "high",
  status: "active",
  createdAt: "2026-08-18T00:00:00Z",
  updatedAt: "2026-08-18T10:20:00+08:00",
}
```

Assert subject query support:

```ts
await listDefaultChildWeaknesses("user-a", { subject: "math" });
assert.match(paths[2], /\/users\/user-a\/children\/default\/weaknesses\?subject=math$/);
```

Import `calculateSubjectHexagonScores` and assert:

```ts
const scores = calculateSubjectHexagonScores(weaknesses);
assert.equal(scores.math.dimensions.calculation, 64);
assert.equal(scores.english.dimensions.phonics, 76);
assert.equal(scores.chinese.dimensions.pinyin, 76);
```

Assert rendered HTML includes:

```ts
assert.match(html, /learning-hexagon-canvas/);
assert.match(html, /语文/);
assert.match(html, /英语/);
assert.match(html, /数学/);
```

- [ ] **Step 2: Run failing frontend contract tests**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: FAIL because subject DTOs, optional query, score module, and Canvas component do not exist yet.

- [ ] **Step 3: Update API types and helper**

In `src/api/learning.ts`:

```ts
export type LearningSubject = "chinese" | "english" | "math";
export type WeaknessCategory =
  | "pinyin"
  | "character_recognition"
  | "reading"
  | "expression"
  | "learning_habit"
  | "listening"
  | "phonics"
  | "vocabulary"
  | "speaking"
  | "number_sense"
  | "calculation"
  | "word_problem"
  | "geometry";
```

Change helper:

```ts
export function listDefaultChildWeaknesses(
  userId: string,
  options: { subject?: LearningSubject } = {},
): Promise<LearningWeaknessDto[]> {
  const query = options.subject ? `?subject=${encodeURIComponent(options.subject)}` : "";
  return requestJson<LearningWeaknessDto[]>(
    `/users/${encodeURIComponent(userId)}/children/default/weaknesses${query}`,
  );
}
```

- [ ] **Step 4: Add scoring module**

Create `src/chat/learningHexagon.ts` with:

```ts
import type { LearningSubject, LearningWeaknessDto } from "../api/learning.js";

export const subjectLabels: Record<LearningSubject, string> = {
  chinese: "语文",
  english: "英语",
  math: "数学",
};

export const subjectDimensions = {
  chinese: ["pinyin", "character_recognition", "reading", "expression", "learning_habit"],
  english: ["listening", "phonics", "vocabulary", "speaking", "learning_habit"],
  math: ["number_sense", "calculation", "word_problem", "geometry", "learning_habit"],
} as const;

const severityPenalty = { mild: 12, medium: 24, high: 36 } as const;
const statusWeight = { active: 1, improving: 0.5, resolved: 0 } as const;

export type SubjectHexagonScore = {
  subject: LearningSubject;
  label: string;
  axes: string[];
  dimensions: Record<string, number>;
};

export function calculateSubjectHexagonScores(
  weaknesses: LearningWeaknessDto[],
): Record<LearningSubject, SubjectHexagonScore> {
  const result = {} as Record<LearningSubject, SubjectHexagonScore>;
  (Object.keys(subjectDimensions) as LearningSubject[]).forEach((subject) => {
    const axes = Array.from(subjectDimensions[subject]);
    const dimensions = Object.fromEntries(axes.map((axis) => [axis, 100]));
    weaknesses
      .filter((item) => item.subject === subject)
      .forEach((item) => {
        if (!(item.category in dimensions)) return;
        const penalty = severityPenalty[item.severity] * statusWeight[item.status];
        dimensions[item.category] = Math.max(35, Math.round(dimensions[item.category] - penalty));
      });
    const overall = Math.round(
      axes.reduce((total, axis) => total + dimensions[axis], 0) / axes.length,
    );
    result[subject] = {
      subject,
      label: subjectLabels[subject],
      axes: axes.concat(["overall"]),
      dimensions: Object.assign({}, dimensions, { overall }),
    };
  });
  return result;
}
```

- [ ] **Step 5: Add Canvas component**

Create `src/chat/LearningHexagonCanvas.tsx`. The component should:

- Render `<canvas className="learning-hexagon-canvas" width={360} height={220} />`.
- Use `useEffect`, `useMemo`, and `useRef`.
- Call `calculateSubjectHexagonScores(weaknesses)`.
- Draw three compact hexagons with labels `语文`, `英语`, `数学`.
- Draw a neutral state for empty weaknesses.
- Render `<p className="learning-hexagon-summary">按语文、英语、数学展示学习关注点</p>` outside Canvas for accessibility.

- [ ] **Step 6: Run frontend contracts**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: PASS.

- [ ] **Step 7: Commit frontend Canvas task**

```bash
git add src/api/learning.ts src/chat/learningHexagon.ts src/chat/LearningHexagonCanvas.tsx contracts/learning.contract.tsx
git commit -m "feat: add learning hexagon canvas"
```

---

### Task 5: Frontend Panel Integration And Styling

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningProfilePanel.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.css`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`

**Interfaces:**
- Consumes: `LearningHexagonCanvas`, `subjectLabels`, `LearningSubject`.
- Produces:
  - Subject filter chips: `全部`, `语文`, `英语`, `数学`
  - Weakness list filtered by selected subject
  - Stream refresh on `record_learning_weakness`

- [ ] **Step 1: Write failing panel integration contract**

In `contracts/learning.contract.tsx`, assert:

```ts
assert.match(html, /全部/);
assert.match(html, /语文/);
assert.match(html, /英语/);
assert.match(html, /数学/);
assert.match(html, /b\/d 字母认反/);
assert.match(html, /口算慢/);
```

Add a CSS source assertion if not already covered by existing history contract:

```ts
const css = await readFile(new URL("../src/App.css", import.meta.url), "utf8");
assert.match(css, /\.learning-subject-filter/);
assert.match(css, /\.learning-hexagon-canvas/);
```

- [ ] **Step 2: Run failing frontend contracts**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
```

Expected: FAIL until the panel renders subject filter and styles.

- [ ] **Step 3: Update panel component**

In `LearningProfilePanel.tsx`:

- Import `useMemo`, `useState`, `LearningHexagonCanvas`, `subjectLabels`, and `LearningSubject`.
- Add `selectedSubject` state with type `LearningSubject | "all"`.
- Render `<LearningHexagonCanvas weaknesses={weaknesses} />` above metrics.
- Render four filter buttons.
- Use `visibleWeaknesses = selectedSubject === "all" ? weaknesses : weaknesses.filter((item) => item.subject === selectedSubject)`.
- Count metrics from `visibleWeaknesses`.
- Add subject label in each weakness row meta.

- [ ] **Step 4: Update stream refresh**

In `App.tsx`, change the stream tool refresh check:

```ts
if (
  event.type === "tool_end" &&
  (event.tool === "record_chinese_literacy_weakness" ||
    event.tool === "record_learning_weakness")
) {
  void loadLearningProfile();
}
```

- [ ] **Step 5: Add CSS**

In `App.css`, add:

```css
.learning-hexagon-canvas {
  width: 100%;
  height: 220px;
  border-bottom: 1px solid #e5ebf3;
  background: #fbfcfe;
}

.learning-hexagon-summary {
  margin: 0;
  padding: 8px 12px 0;
  color: #64748b;
  font-size: 12px;
}

.learning-subject-filter {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid #e5ebf3;
}

.learning-subject-filter button {
  min-width: 0;
  border: 1px solid #dbe4ee;
  border-radius: 7px;
  padding: 6px 7px;
  color: #475569;
  background: #ffffff;
  font-size: 12px;
}

.learning-subject-filter button.is-active {
  color: #0f172a;
  border-color: #94a3b8;
  background: #eef6ff;
}
```

- [ ] **Step 6: Run frontend verification**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit frontend panel task**

```bash
git add src/chat/LearningProfilePanel.tsx src/App.tsx src/App.css contracts/learning.contract.tsx
git commit -m "feat: show multi-subject learning profile"
```

---

### Task 6: Final Verification, Review, And Push

**Files:**
- Verify all backend and frontend changes.
- No new production file is created in this task unless verification exposes a bug.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: backend pushed to `origin/main`, frontend local commits only unless explicitly requested otherwise.

- [ ] **Step 1: Run backend full verification**

Run:

```bash
.venv/bin/python -m unittest
.venv/bin/python -m py_compile api_server.py agent_console.py agent_context.py capabilities.py history_store.py learning_context.py learning_store.py skills/__init__.py skills/loader.py skills/registry.py tools/registry.py tools/record_chinese_literacy_weakness/record_chinese_literacy_weakness.py tools/record_learning_weakness/record_learning_weakness.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Run frontend full verification**

Run in `/Users/caisufang/projects/agent-hub-frontend`:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Smoke-test backend API without calling the LLM**

Run:

```bash
curl -s -X POST http://127.0.0.1:8003/users/smoke_user/children/default/subjects/math/weaknesses \
  -H "Content-Type: application/json" \
  -d '{"category":"计算","title":"口算慢","evidence":"10以内口算会停很久。","severity":"中等","sourceRunId":"run-smoke-math"}'
curl -s "http://127.0.0.1:8003/users/smoke_user/children/default/weaknesses?subject=math"
```

Expected: returned JSON includes `"subject":"math"` and `"category":"calculation"`.

- [ ] **Step 4: Request code review**

Ask a reviewer to inspect:

- Backend diff from `bab8ae4..HEAD`
- Frontend diff from `154d1cb..HEAD`
- Spec: `docs/superpowers/specs/2026-08-18-first-grade-multi-subject-learning-profile-design.md`

Fix Critical and Important findings before final push.

- [ ] **Step 5: Push backend only**

Run in `/Users/caisufang/projects/agent-hub`:

```bash
git push origin main
```

Expected: backend `main` is aligned with `origin/main`.

- [ ] **Step 6: Report final state**

Report:

- Backend commits pushed.
- Frontend commits are local only.
- Verification commands and outcomes.
- Any smoke-test caveat if the local backend server was not running.
