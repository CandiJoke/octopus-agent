# Grade One Curriculum Tree Design

## Goal

Build the first curriculum backbone for Agent Hub: a grade-one primary curriculum tree with observable behaviors, and let child weakness records optionally link to those behavior nodes.

## Scope

This version covers `grade_1` only, with Chinese, Math, and English. It creates enough real nodes for product behavior without trying to encode every official detail at once.

The first data shape is:

```text
stage -> subject -> grade -> domain -> ability -> observable behavior
```

Example:

```text
primary -> chinese -> grade_1 -> pinyin -> initials -> distinguish b/p/d/q
```

## Source Model

The backbone follows the Ministry of Education's 2022 compulsory education curriculum standards as the primary reference:

- https://www.moe.gov.cn/srcsite/A26/s8001/202204/t20220420_619921.html

The product data is a practical learning-support model, not a verbatim curriculum document. It converts curriculum direction into observable behaviors a parent or Agent can recognize from a short conversation.

## Backend Design

Create a `curriculum_catalog` boundary that owns read-only curriculum data while the current Python backend is still the learning service. This keeps future Java extraction simple:

- `curriculum_catalog.py` loads static JSON.
- `curriculum/primary_grade_1.json` stores grade-one domains, abilities, and observable behaviors.
- FastAPI exposes the catalog through `/curriculum/primary/grades/{grade}`.
- `learning_store.py` stores optional references from weakness records to `ability_id`, `behavior_id`, and `match_confidence`.

The learning store remains responsible for child-specific data only. It may validate that a supplied ability or behavior exists, but it does not own curriculum content.

## Weakness Association

Weakness records keep the existing broad `category` because it drives the current hexagon profile. The new fields are optional:

- `ability_id`: stable curriculum ability ID.
- `behavior_id`: stable observable behavior ID.
- `match_confidence`: number from `0.0` to `1.0`.

When `behavior_id` is supplied, the backend derives or validates its parent `ability_id`. If the behavior does not match the child's grade and subject, the backend rejects it.

If the Agent cannot confidently match a behavior, it should still record the weakness without these fields.

## API Contract

`GET /curriculum/primary/grades/grade_1` returns the grade-one tree.

Weakness create APIs accept optional camelCase fields:

```json
{
  "category": "pinyin",
  "title": "b/d 易混淆",
  "evidence": "读拼音时经常把 b 看成 d。",
  "severity": "medium",
  "abilityId": "chinese_g1_pinyin_initials",
  "behaviorId": "chinese_g1_pinyin_initials_distinguish_bpdq",
  "matchConfidence": 0.82
}
```

Weakness responses include the same IDs. When a behavior is known, the API also includes:

- `abilityTitle`
- `behaviorTitle`

## Agent Behavior

`primary_learning_support` should tell the model:

- If a parent describes a concrete grade-one learning issue, first infer the subject and broad category.
- Try to match the issue to one observable behavior.
- Pass `ability_id`, `behavior_id`, and `match_confidence` only when the match is concrete.
- Avoid inventing IDs. If unsure, record without a behavior reference.

## Frontend Design

The frontend does not own curriculum data. First version only adds:

- DTOs and API helper for the curriculum tree.
- Optional weakness fields for ability and behavior references.
- A small "可观察表现" line in the learning profile row when `behaviorTitle` is present.

The full tree browser can come later.

## Migration

Existing records migrate safely because all new weakness columns are nullable. Existing API consumers still receive the existing fields, plus optional new fields only when present.

## Non-Goals

- Full national curriculum coverage.
- Textbook version management.
- Region-specific adoption rules.
- Exercise generation.
- Wrong-question notebook.
- Multi-child support.
- Java service extraction in this step.
