# Grade One Curriculum Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a grade-one primary curriculum tree with observable behavior nodes and let learning weaknesses optionally link to those nodes.

**Architecture:** Keep curriculum data in a read-only `curriculum_catalog.py` boundary backed by JSON, and keep child-specific records in `learning_store.py`. FastAPI exposes the catalog and enriches weakness responses with ability and behavior titles.

**Tech Stack:** Python 3.11, FastAPI, SQLite, unittest, TypeScript, React, Vite.

## Global Constraints

- API JSON uses camelCase.
- Python and SQLite use snake_case.
- Curriculum IDs are stable strings and should not include local textbook version names.
- New weakness curriculum fields are optional.
- `first_grade` remains a read compatibility alias for `grade_1`.
- Backend commits are pushed to `origin/main`; frontend commits remain local unless requested.

---

### Task 1: Curriculum Catalog

**Files:**
- Create: `curriculum/primary_grade_1.json`
- Create: `curriculum_catalog.py`
- Create: `test_curriculum_catalog.py`
- Modify: `api_server.py`
- Test: `test_curriculum_catalog.py`, `test_api_learning.py`

**Interfaces:**
- Produces: `get_primary_grade_curriculum(grade: str) -> dict[str, object]`
- Produces: `resolve_curriculum_behavior(grade: str, subject: str, behavior_id: str) -> CurriculumBehaviorRef`
- Produces: `resolve_curriculum_ability(grade: str, subject: str, ability_id: str) -> CurriculumAbilityRef`
- Produces: `GET /curriculum/primary/grades/{grade}`

- [ ] **Step 1: Write failing tests**

Add tests that require `grade_1` to return Chinese, English, and Math subjects, and require `chinese_g1_pinyin_initials_distinguish_bpdq` to resolve to parent ability `chinese_g1_pinyin_initials`.

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/python -m unittest test_curriculum_catalog.py test_api_learning.py`

Expected: import or endpoint failures.

- [ ] **Step 3: Implement catalog and API**

Add the JSON tree and loader functions. Add `GET /curriculum/primary/grades/{grade}` in `api_server.py`; return `404` when a grade is unsupported.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python -m unittest test_curriculum_catalog.py test_api_learning.py`

Expected: all tests pass.

### Task 2: Weakness Curriculum References

**Files:**
- Modify: `learning_store.py`
- Modify: `api_server.py`
- Modify: `tools/record_learning_weakness/record_learning_weakness.py`
- Modify: `tools/record_learning_weakness/TOOL.md`
- Modify: `skills/primary_learning_support/SKILL.md`
- Modify: `test_learning_store.py`
- Modify: `test_api_learning.py`
- Modify: `test_learning_tool.py`
- Modify: `test_tools.py`

**Interfaces:**
- Consumes: `resolve_curriculum_behavior(...)`
- Produces: `LearningWeaknessRecord.ability_id`
- Produces: `LearningWeaknessRecord.behavior_id`
- Produces: `LearningWeaknessRecord.match_confidence`
- Produces: optional API fields `abilityId`, `behaviorId`, `matchConfidence`, `abilityTitle`, `behaviorTitle`

- [ ] **Step 1: Write failing tests**

Add tests for creating a pinyin weakness linked to `chinese_g1_pinyin_initials_distinguish_bpdq`, serializing the optional IDs, rejecting a Math weakness linked to a Chinese behavior, and exposing behavior fields in tool schema.

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/python -m unittest test_learning_store.py test_api_learning.py test_learning_tool.py test_tools.py`

Expected: missing constructor fields or missing API fields.

- [ ] **Step 3: Implement store migration and validation**

Add nullable `ability_id`, `behavior_id`, and `match_confidence` columns. Validate references against grade and subject. When a behavior is supplied without an ability, derive its parent ability. Keep existing records valid with null references.

- [ ] **Step 4: Implement tool and skill contract**

Add optional `ability_id`, `behavior_id`, and `match_confidence` fields to `record_learning_weakness`. Update `primary_learning_support` so the model only passes IDs when it can match a known observable behavior.

- [ ] **Step 5: Verify tests pass**

Run: `.venv/bin/python -m unittest test_learning_store.py test_api_learning.py test_learning_tool.py test_tools.py`

Expected: all tests pass.

### Task 3: Frontend Contract and Display

**Files:**
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/api/learning.ts`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/chat/LearningProfilePanel.tsx`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/src/App.css`
- Modify: `/Users/caisufang/projects/agent-hub-frontend/contracts/learning.contract.tsx`

**Interfaces:**
- Consumes: `GET /curriculum/primary/grades/{grade}`
- Consumes: optional weakness fields `abilityTitle` and `behaviorTitle`
- Produces: `getPrimaryGradeCurriculum(grade: LearningGrade) -> Promise<CurriculumGradeDto>`

- [ ] **Step 1: Write failing contract**

Require the learning contract to fetch `/curriculum/primary/grades/grade_1` and require the rendered profile to show `可观察表现` and the behavior title for a linked weakness.

- [ ] **Step 2: Verify contract fails**

Run: `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts`

Expected: missing API helper or missing rendered behavior text.

- [ ] **Step 3: Implement DTOs and display**

Add curriculum DTOs and helper in `src/api/learning.ts`. Show behavior title below weakness evidence when present, with compact styling.

- [ ] **Step 4: Verify contract passes**

Run: `source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts`

Expected: all contracts pass.

### Task 4: Full Verification and Commits

**Files:**
- All files touched by Tasks 1-3.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: pushed backend commit and local frontend commit.

- [ ] **Step 1: Backend verification**

Run:

```bash
.venv/bin/python -m unittest
.venv/bin/python -m py_compile api_server.py curriculum_catalog.py learning_store.py tools/record_learning_weakness/record_learning_weakness.py
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 2: Frontend verification**

Run:

```bash
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run test:contracts
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run lint
source ~/.nvm/nvm.sh && nvm use 20.20.0 && npm run build
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 3: Commit and push backend**

Run:

```bash
git add api_server.py curriculum_catalog.py curriculum/primary_grade_1.json learning_store.py skills/primary_learning_support/SKILL.md tools/record_learning_weakness/TOOL.md tools/record_learning_weakness/record_learning_weakness.py test_curriculum_catalog.py test_api_learning.py test_learning_store.py test_learning_tool.py test_tools.py docs/superpowers/specs/2026-08-19-grade-one-curriculum-tree-design.md docs/superpowers/plans/2026-08-19-grade-one-curriculum-tree.md
git commit -m "feat: add grade one curriculum tree"
git push origin main
```

- [ ] **Step 4: Commit frontend locally**

Run in `/Users/caisufang/projects/agent-hub-frontend`:

```bash
git add contracts/learning.contract.tsx src/api/learning.ts src/chat/LearningProfilePanel.tsx src/App.css
git commit -m "feat: show curriculum behavior links"
```

## Self-Review

- Spec coverage: catalog, weakness association, API, frontend display, migration, and future Java extraction are covered.
- Placeholder scan: no placeholders remain.
- Type consistency: `abilityId`, `behaviorId`, and `matchConfidence` are camelCase API fields; `ability_id`, `behavior_id`, and `match_confidence` are Python and SQLite fields.
