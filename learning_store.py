from __future__ import annotations

import sqlite3
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from curriculum_catalog import (
    infer_curriculum_behavior,
    resolve_curriculum_ability,
    resolve_curriculum_behavior,
)


DEFAULT_CHILD_ID = "default"
DEFAULT_CHILD_DISPLAY_NAME = "孩子"
DEFAULT_GRADE = "grade_1"
DEFAULT_SUBJECT = "chinese"

LearningSubject = Literal["chinese", "english", "math"]
LearningSubjectInput = Literal["chinese", "english", "math", "语文", "英语", "数学"]
LearningGrade = Literal["grade_1", "grade_2", "grade_3", "grade_4", "grade_5", "grade_6"]
LearningGradeInput = Literal[
    "grade_1",
    "grade_2",
    "grade_3",
    "grade_4",
    "grade_5",
    "grade_6",
    "first_grade",
    "second_grade",
    "third_grade",
    "fourth_grade",
    "fifth_grade",
    "sixth_grade",
    "一年级",
    "二年级",
    "三年级",
    "四年级",
    "五年级",
    "六年级",
    "小学一年级",
    "小学二年级",
    "小学三年级",
    "小学四年级",
    "小学五年级",
    "小学六年级",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
]
WeaknessCategory = Literal[
    "pinyin",
    "character_recognition",
    "reading",
    "expression",
    "learning_habit",
    "listening",
    "phonics",
    "vocabulary",
    "speaking",
    "number_sense",
    "calculation",
    "word_problem",
    "geometry",
]
WeaknessSeverity = Literal["mild", "medium", "high"]
WeaknessStatus = Literal["active", "improving", "resolved"]
LearningPlanStatus = Literal["draft", "active", "paused", "completed", "archived"]
LearningPlanCheckinStatus = Literal["done", "partial", "skipped"]
ChineseWeaknessCategoryInput = Literal[
    "pinyin",
    "character_recognition",
    "reading",
    "expression",
    "learning_habit",
    "拼音",
    "拼读",
    "识字",
    "认字",
    "朗读",
    "阅读",
    "表达",
    "口语表达",
    "学习习惯",
    "习惯",
]
WeaknessCategoryInput = Literal[
    "pinyin",
    "character_recognition",
    "reading",
    "expression",
    "learning_habit",
    "拼音",
    "拼读",
    "识字",
    "认字",
    "朗读",
    "阅读",
    "表达",
    "口语表达",
    "学习习惯",
    "习惯",
    "listening",
    "听音",
    "听音辨音",
    "phonics",
    "自然拼读",
    "字母",
    "vocabulary",
    "词汇",
    "单词",
    "speaking",
    "口语",
    "number_sense",
    "number-sense",
    "数感",
    "calculation",
    "计算",
    "口算",
    "word_problem",
    "word-problem",
    "应用题",
    "geometry",
    "图形空间",
    "图形",
]
WeaknessSeverityInput = Literal[
    "mild",
    "medium",
    "high",
    "轻微",
    "轻度",
    "中等",
    "中度",
    "明显",
    "严重",
    "重度",
]

VALID_SUBJECTS = {"chinese", "english", "math"}
VALID_GRADES = {"grade_1", "grade_2", "grade_3", "grade_4", "grade_5", "grade_6"}
VALID_SEVERITIES = {"mild", "medium", "high"}
VALID_STATUSES = {"active", "improving", "resolved"}
VALID_PLAN_STATUSES = {"draft", "active", "paused", "completed", "archived"}
VALID_PLAN_CHECKIN_STATUSES = {"done", "partial", "skipped"}
MAX_LEARNING_CALENDAR_RANGE_DAYS = 31
SUBJECT_SORT_ORDER = {"chinese": 0, "english": 1, "math": 2}
SEVERITY_SORT_ORDER = {"high": 0, "medium": 1, "mild": 2}
SUBJECT_LABELS = {
    "chinese": "语文",
    "english": "英语",
    "math": "数学",
}
CATEGORY_LABELS = {
    "pinyin": "拼音",
    "character_recognition": "识字",
    "reading": "朗读",
    "expression": "表达",
    "learning_habit": "学习习惯",
    "listening": "听音",
    "phonics": "拼读",
    "vocabulary": "词汇",
    "speaking": "口语",
    "number_sense": "数感",
    "calculation": "计算",
    "word_problem": "应用题",
    "geometry": "图形空间",
}
GRADE_ALIASES = {
    "grade_1": "grade_1",
    "first_grade": "grade_1",
    "一年级": "grade_1",
    "小学一年级": "grade_1",
    "1": "grade_1",
    "grade_2": "grade_2",
    "second_grade": "grade_2",
    "二年级": "grade_2",
    "小学二年级": "grade_2",
    "2": "grade_2",
    "grade_3": "grade_3",
    "third_grade": "grade_3",
    "三年级": "grade_3",
    "小学三年级": "grade_3",
    "3": "grade_3",
    "grade_4": "grade_4",
    "fourth_grade": "grade_4",
    "四年级": "grade_4",
    "小学四年级": "grade_4",
    "4": "grade_4",
    "grade_5": "grade_5",
    "fifth_grade": "grade_5",
    "五年级": "grade_5",
    "小学五年级": "grade_5",
    "5": "grade_5",
    "grade_6": "grade_6",
    "sixth_grade": "grade_6",
    "六年级": "grade_6",
    "小学六年级": "grade_6",
    "6": "grade_6",
}
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
        "learning-habit": "learning_habit",
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
        "learning-habit": "learning_habit",
        "学习习惯": "learning_habit",
        "习惯": "learning_habit",
    },
}
VALID_CATEGORIES_BY_SUBJECT = {
    subject: set(aliases.values())
    for subject, aliases in SUBJECT_CATEGORY_ALIASES.items()
}
VALID_CATEGORIES = set().union(*VALID_CATEGORIES_BY_SUBJECT.values())
SEVERITY_ALIASES = {
    "mild": "mild",
    "轻微": "mild",
    "轻度": "mild",
    "medium": "medium",
    "中等": "medium",
    "中度": "medium",
    "high": "high",
    "明显": "high",
    "严重": "high",
    "重度": "high",
}
SENSITIVE_TEXT_REPLACEMENTS = (
    (
        re.compile(
            r"(?:孩子|小孩|女儿|儿子|宝宝)?(?:名字是|姓名是|姓名[:：]?|叫|名叫)\s*[\u4e00-\u9fffA-Za-z]{1,12}"
        ),
        "孩子姓名[已隐藏]",
    ),
    (
        re.compile(
            r"(?:爸爸|妈妈|父亲|母亲|家长|奶奶|爷爷|外婆|外公)(?:名字是|姓名是|姓名[:：]?|叫|名叫)\s*[\u4e00-\u9fffA-Za-z]{1,12}"
        ),
        "家庭成员[已隐藏]",
    ),
    (
        re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{2,30}(?:小学|学校|幼儿园|中学)"),
        "学校[已隐藏]",
    ),
    (
        re.compile(r"(?:住在|住址[:：]?|地址[:：]?)[^，。,.；;]{2,50}"),
        "住址[已隐藏]",
    ),
    (
        re.compile(
            r"ADHD|多动症|自闭症|孤独症|抑郁症|焦虑症|阅读障碍|智力障碍|发育迟缓|感统失调",
            re.IGNORECASE,
        ),
        "敏感标签[已隐藏]",
    ),
    (re.compile(r"1[3-9]\d{9}"), "电话[已隐藏]"),
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "邮箱[已隐藏]",
    ),
    (re.compile(r"\d{17}[\dXx]"), "证件号[已隐藏]"),
)


@dataclass(frozen=True)
class ChildProfileRecord:
    user_id: str
    child_id: str
    display_name: str
    grade: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningWeaknessRecord:
    weakness_id: str
    user_id: str
    child_id: str
    subject: str
    grade: str
    category: str
    title: str
    normalized_title: str
    evidence: str
    severity: str
    status: str
    source_run_id: str | None
    ability_id: str | None
    behavior_id: str | None
    match_confidence: float | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningPlanRecord:
    plan_id: str
    user_id: str
    child_id: str
    title: str
    goal: str
    status: str
    start_date: str | None
    end_date: str | None
    created_from_prompt: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningPlanItemRecord:
    item_id: str
    plan_id: str
    user_id: str
    child_id: str
    subject: str
    title: str
    description: str
    target_weakness_id: str | None
    frequency: str
    estimated_minutes: int
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningPlanCheckinRecord:
    checkin_id: str
    plan_id: str
    item_id: str
    user_id: str
    child_id: str
    checkin_date: str
    status: str
    note: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class LearningPlanSnapshot:
    plan: LearningPlanRecord
    items: list[LearningPlanItemRecord]
    checkins_by_item_id: dict[str, list[LearningPlanCheckinRecord]]


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


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def normalize_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


def normalize_subject_value(subject: str) -> str:
    key = " ".join(str(subject).strip().split())
    normalized = SUBJECT_ALIASES.get(key) or SUBJECT_ALIASES.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported learning subject: {subject}")
    return normalized


def normalize_grade_value(grade: str | int) -> str:
    key = " ".join(str(grade).strip().split())
    normalized = GRADE_ALIASES.get(key) or GRADE_ALIASES.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported primary learning grade: {grade}")
    return normalized


def normalize_category_value(subject: str, category: str | None = None) -> str:
    if category is None:
        category = subject
        subject = DEFAULT_SUBJECT
    subject = normalize_subject_value(subject)
    key = " ".join(str(category).strip().split())
    aliases = SUBJECT_CATEGORY_ALIASES[subject]
    normalized = aliases.get(key) or aliases.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported {subject} weakness category: {category}")
    return normalized


def normalize_severity_value(severity: str) -> str:
    key = " ".join(str(severity).strip().split())
    normalized = SEVERITY_ALIASES.get(key) or SEVERITY_ALIASES.get(key.lower())
    if normalized is None:
        raise ValueError(f"unsupported weakness severity: {severity}")
    return normalized


def normalize_optional_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split())
    return normalized or None


def normalize_match_confidence(value: float | int | None) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if normalized < 0 or normalized > 1:
        raise ValueError("match confidence must be between 0 and 1")
    return round(normalized, 2)


def normalize_curriculum_reference(
    grade: str,
    subject: str,
    ability_id: str | None = None,
    behavior_id: str | None = None,
    match_confidence: float | int | None = None,
) -> tuple[str | None, str | None, float | None]:
    ability_id = normalize_optional_id(ability_id)
    behavior_id = normalize_optional_id(behavior_id)
    normalized_confidence = normalize_match_confidence(match_confidence)

    if normalized_confidence is not None and ability_id is None and behavior_id is None:
        raise ValueError("match confidence requires curriculum reference")

    try:
        if behavior_id is not None:
            behavior = resolve_curriculum_behavior(grade, subject, behavior_id)
            if ability_id is not None and ability_id != behavior.ability_id:
                raise ValueError("ability and behavior do not match")
            return behavior.ability_id, behavior.behavior_id, normalized_confidence

        if ability_id is not None:
            ability = resolve_curriculum_ability(grade, subject, ability_id)
            return ability.ability_id, None, normalized_confidence
    except LookupError as exc:
        raise ValueError(str(exc)) from exc

    return None, None, normalized_confidence


def infer_missing_curriculum_reference(
    grade: str,
    subject: str,
    category: str,
    title: str,
    evidence: str,
    ability_id: str | None,
    behavior_id: str | None,
    match_confidence: float | None,
) -> tuple[str | None, str | None, float | None]:
    if behavior_id is not None:
        return ability_id, behavior_id, match_confidence

    match = infer_curriculum_behavior(grade, subject, category, title, evidence)
    if match is None:
        return ability_id, behavior_id, match_confidence

    behavior = match.behavior
    if ability_id is not None and ability_id != behavior.ability_id:
        return ability_id, behavior_id, match_confidence

    return (
        behavior.ability_id,
        behavior.behavior_id,
        match_confidence if match_confidence is not None else match.confidence,
    )


def sanitize_learning_text(text: str) -> str:
    sanitized = " ".join(str(text).strip().split())
    for pattern, replacement in SENSITIVE_TEXT_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def validate_category(category: str) -> None:
    normalize_category_value(DEFAULT_SUBJECT, category)


def validate_grade(grade: str | int) -> None:
    normalize_grade_value(grade)


def validate_severity(severity: str) -> None:
    normalize_severity_value(severity)


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported weakness status: {status}")


def validate_plan_status(status: str) -> None:
    if status not in VALID_PLAN_STATUSES:
        raise ValueError(f"unsupported learning plan status: {status}")


def validate_plan_checkin_status(status: str) -> None:
    if status not in VALID_PLAN_CHECKIN_STATUSES:
        raise ValueError(f"unsupported learning plan checkin status: {status}")


def normalize_plan_date(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    try:
        datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"invalid learning plan date: {value}") from exc
    return normalized


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
    return [(start + timedelta(days=offset)).isoformat() for offset in range(day_count)]


def plan_is_visible_on_date(plan: LearningPlanRecord, day: str) -> bool:
    if plan.start_date is not None and day < plan.start_date:
        return False
    if plan.end_date is not None and day > plan.end_date:
        return False
    return True


def frequency_for_severity(severity: str) -> str:
    if severity == "high":
        return "每天"
    if severity == "medium":
        return "每周 3 次"
    return "每周 2 次"


def minutes_for_severity(severity: str) -> int:
    if severity == "high":
        return 15
    if severity == "medium":
        return 12
    return 10


def learning_plan_item_from_weakness(
    record: LearningWeaknessRecord,
    sort_order: int,
) -> dict[str, object]:
    payload = serialize_learning_weakness(record)
    behavior_title = payload.get("behaviorTitle")
    category_label = CATEGORY_LABELS.get(record.category, record.category)
    subject_label = SUBJECT_LABELS.get(record.subject, record.subject)
    focus = (
        f"围绕“{behavior_title}”进行观察和练习"
        if behavior_title
        else f"围绕“{record.evidence}”进行短练习"
    )
    return {
        "subject": record.subject,
        "title": f"{subject_label} · {category_label}：{record.title}",
        "description": f"{focus}，结束后记录孩子是否能稳定完成。",
        "target_weakness_id": record.weakness_id,
        "frequency": frequency_for_severity(record.severity),
        "estimated_minutes": minutes_for_severity(record.severity),
        "sort_order": sort_order,
    }


class LearningStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            self._create_schema(conn)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS child_profiles (
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                grade TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, child_id)
            );

            CREATE TABLE IF NOT EXISTS learning_weaknesses (
                weakness_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT NOT NULL,
                category TEXT NOT NULL CHECK (
                    category IN (
                        'pinyin',
                        'character_recognition',
                        'reading',
                        'expression',
                        'learning_habit',
                        'listening',
                        'phonics',
                        'vocabulary',
                        'speaking',
                        'number_sense',
                        'calculation',
                        'word_problem',
                        'geometry'
                    )
                ),
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                evidence TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('mild', 'medium', 'high')),
                status TEXT NOT NULL CHECK (status IN ('active', 'improving', 'resolved')),
                source_run_id TEXT,
                ability_id TEXT,
                behavior_id TEXT,
                match_confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_weakness_active_unique
                ON learning_weaknesses(
                    user_id, child_id, subject, category, normalized_title
                )
                WHERE status = 'active';

            CREATE INDEX IF NOT EXISTS idx_learning_weaknesses_user_child_status
                ON learning_weaknesses(user_id, child_id, status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS learning_plans (
                plan_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('draft', 'active', 'paused', 'completed', 'archived')
                ),
                start_date TEXT,
                end_date TEXT,
                created_from_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
            );

            CREATE INDEX IF NOT EXISTS idx_learning_plans_user_child_status
                ON learning_plans(user_id, child_id, status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS learning_plan_items (
                item_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                target_weakness_id TEXT,
                frequency TEXT NOT NULL,
                estimated_minutes INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id)
                    REFERENCES learning_plans(plan_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
            );

            CREATE INDEX IF NOT EXISTS idx_learning_plan_items_plan_order
                ON learning_plan_items(plan_id, sort_order ASC);

            CREATE TABLE IF NOT EXISTS learning_plan_checkins (
                checkin_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                checkin_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('done', 'partial', 'skipped')),
                note TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id)
                    REFERENCES learning_plans(plan_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(item_id)
                    REFERENCES learning_plan_items(item_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_plan_checkins_item_date
                ON learning_plan_checkins(user_id, child_id, item_id, checkin_date);
            """
        )
        self._migrate_learning_weaknesses_schema(conn)
        self._migrate_learning_curriculum_columns(conn)
        self._migrate_learning_grades(conn)
        self._backfill_learning_curriculum_references(conn)

    def _migrate_learning_weaknesses_schema(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'learning_weaknesses'
            """
        ).fetchone()
        if row is None or "phonics" in str(row["sql"]):
            return

        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ALTER TABLE learning_weaknesses RENAME TO learning_weaknesses_old")
            conn.execute("DROP INDEX IF EXISTS idx_learning_weakness_active_unique")
            conn.execute("DROP INDEX IF EXISTS idx_learning_weaknesses_user_child_status")
            conn.execute(
                """
                CREATE TABLE learning_weaknesses (
                weakness_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT NOT NULL,
                category TEXT NOT NULL CHECK (
                    category IN (
                        'pinyin',
                        'character_recognition',
                        'reading',
                        'expression',
                        'learning_habit',
                        'listening',
                        'phonics',
                        'vocabulary',
                        'speaking',
                        'number_sense',
                        'calculation',
                        'word_problem',
                        'geometry'
                    )
                ),
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                evidence TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('mild', 'medium', 'high')),
                status TEXT NOT NULL CHECK (status IN ('active', 'improving', 'resolved')),
                source_run_id TEXT,
                ability_id TEXT,
                behavior_id TEXT,
                match_confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id, child_id)
                    REFERENCES child_profiles(user_id, child_id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO learning_weaknesses(
                weakness_id, user_id, child_id, subject, grade, category,
                title, normalized_title, evidence, severity, status,
                source_run_id, ability_id, behavior_id, match_confidence,
                created_at, updated_at
                )
                SELECT
                weakness_id, user_id, child_id, subject, grade, category,
                title, normalized_title, evidence, severity, status,
                source_run_id, NULL, NULL, NULL, created_at, updated_at
                FROM learning_weaknesses_old
                """
            )
            conn.execute("DROP TABLE learning_weaknesses_old")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_weakness_active_unique
                ON learning_weaknesses(
                    user_id, child_id, subject, category, normalized_title
                )
                WHERE status = 'active'
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_learning_weaknesses_user_child_status
                ON learning_weaknesses(user_id, child_id, status, updated_at DESC)
                """
            )
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    def _migrate_learning_curriculum_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(learning_weaknesses)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "ability_id" not in column_names:
            conn.execute("ALTER TABLE learning_weaknesses ADD COLUMN ability_id TEXT")
        if "behavior_id" not in column_names:
            conn.execute("ALTER TABLE learning_weaknesses ADD COLUMN behavior_id TEXT")
        if "match_confidence" not in column_names:
            conn.execute(
                "ALTER TABLE learning_weaknesses ADD COLUMN match_confidence REAL"
            )

    def _migrate_learning_grades(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE child_profiles
            SET grade = ?
            WHERE grade = ?
            """,
            ("grade_1", "first_grade"),
        )
        conn.execute(
            """
            UPDATE learning_weaknesses
            SET grade = ?
            WHERE grade = ?
            """,
            ("grade_1", "first_grade"),
        )

    def _backfill_learning_curriculum_references(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT
                weakness_id, grade, subject, category, title, evidence,
                ability_id, behavior_id, match_confidence
            FROM learning_weaknesses
            WHERE behavior_id IS NULL
            """
        ).fetchall()
        for row in rows:
            ability_id, behavior_id, match_confidence = infer_missing_curriculum_reference(
                grade=str(row["grade"]),
                subject=str(row["subject"]),
                category=str(row["category"]),
                title=str(row["title"]),
                evidence=str(row["evidence"]),
                ability_id=(
                    str(row["ability_id"]) if row["ability_id"] is not None else None
                ),
                behavior_id=(
                    str(row["behavior_id"]) if row["behavior_id"] is not None else None
                ),
                match_confidence=(
                    float(row["match_confidence"])
                    if row["match_confidence"] is not None
                    else None
                ),
            )
            if behavior_id is None:
                continue
            conn.execute(
                """
                UPDATE learning_weaknesses
                SET ability_id = ?, behavior_id = ?, match_confidence = ?
                WHERE weakness_id = ?
                """,
                (ability_id, behavior_id, match_confidence, row["weakness_id"]),
            )

    def get_or_create_default_profile(self, user_id: str) -> ChildProfileRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, child_id, display_name, grade, created_at, updated_at
                FROM child_profiles
                WHERE user_id = ? AND child_id = ?
                """,
                (user_id, DEFAULT_CHILD_ID),
            ).fetchone()
            if row is None:
                now = utc_now()
                conn.execute(
                    """
                    INSERT INTO child_profiles(
                        user_id, child_id, display_name, grade, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        DEFAULT_CHILD_ID,
                        DEFAULT_CHILD_DISPLAY_NAME,
                        DEFAULT_GRADE,
                        now,
                        now,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT user_id, child_id, display_name, grade, created_at, updated_at
                    FROM child_profiles
                    WHERE user_id = ? AND child_id = ?
                    """,
                    (user_id, DEFAULT_CHILD_ID),
                ).fetchone()
            return child_profile_from_row(row)

    def update_default_profile_grade(
        self,
        user_id: str,
        grade: str | int,
    ) -> ChildProfileRecord:
        normalized_grade = normalize_grade_value(grade)
        self.get_or_create_default_profile(user_id)
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE child_profiles
                SET grade = ?, updated_at = ?
                WHERE user_id = ? AND child_id = ?
                """,
                (normalized_grade, now, user_id, DEFAULT_CHILD_ID),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT user_id, child_id, display_name, grade, created_at, updated_at
                FROM child_profiles
                WHERE user_id = ? AND child_id = ?
                """,
                (user_id, DEFAULT_CHILD_ID),
            ).fetchone()
            return child_profile_from_row(row)

    def list_weaknesses(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
        status: str | None = None,
        subject: str | None = None,
    ) -> list[LearningWeaknessRecord]:
        params: list[str] = [user_id, child_id]
        where_status = ""
        if status is not None:
            validate_status(status)
            where_status = "AND status = ?"
            params.append(status)
        where_subject = ""
        if subject is not None:
            subject = normalize_subject_value(subject)
            where_subject = "AND subject = ?"
            params.append(subject)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    weakness_id, user_id, child_id, subject, grade, category,
                    title, normalized_title, evidence, severity, status,
                    source_run_id, ability_id, behavior_id, match_confidence,
                    created_at, updated_at
                FROM learning_weaknesses
                WHERE user_id = ? AND child_id = ?
                {where_status}
                {where_subject}
                ORDER BY
                    CASE status
                        WHEN 'active' THEN 0
                        WHEN 'improving' THEN 1
                        ELSE 2
                    END ASC,
                    updated_at DESC,
                    weakness_id DESC
                """,
                params,
            ).fetchall()
            return [learning_weakness_from_row(row) for row in rows]

    def upsert_weakness(
        self,
        user_id: str,
        child_id: str,
        category: str,
        title: str,
        evidence: str,
        severity: str,
        source_run_id: str | None = None,
        subject: str = DEFAULT_SUBJECT,
        ability_id: str | None = None,
        behavior_id: str | None = None,
        match_confidence: float | int | None = None,
    ) -> tuple[LearningWeaknessRecord, bool]:
        subject = normalize_subject_value(subject)
        category = normalize_category_value(subject, category)
        severity = normalize_severity_value(severity)
        safe_title = sanitize_learning_text(title)
        safe_evidence = sanitize_learning_text(evidence)
        normalized_title = normalize_title(safe_title)
        if not normalized_title:
            raise ValueError("weakness title is required")
        if not safe_evidence:
            raise ValueError("weakness evidence is required")

        profile = self.get_or_create_default_profile(user_id)
        ability_id, behavior_id, match_confidence = normalize_curriculum_reference(
            profile.grade,
            subject,
            ability_id=ability_id,
            behavior_id=behavior_id,
            match_confidence=match_confidence,
        )
        ability_id, behavior_id, match_confidence = infer_missing_curriculum_reference(
            profile.grade,
            subject,
            category,
            safe_title,
            safe_evidence,
            ability_id,
            behavior_id,
            match_confidence,
        )
        now = utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT weakness_id
                FROM learning_weaknesses
                WHERE
                    user_id = ?
                    AND child_id = ?
                    AND subject = ?
                    AND category = ?
                    AND normalized_title = ?
                    AND status = 'active'
                """,
                (user_id, child_id, subject, category, normalized_title),
            ).fetchone()

            if existing is not None:
                weakness_id = str(existing["weakness_id"])
                conn.execute(
                    """
                    UPDATE learning_weaknesses
                    SET
                        title = ?,
                        evidence = ?,
                        severity = ?,
                        source_run_id = ?,
                        ability_id = COALESCE(?, ability_id),
                        behavior_id = COALESCE(?, behavior_id),
                        match_confidence = COALESCE(?, match_confidence),
                        updated_at = ?
                    WHERE user_id = ? AND weakness_id = ?
                    """,
                    (
                        safe_title,
                        safe_evidence,
                        severity,
                        source_run_id,
                        ability_id,
                        behavior_id,
                        match_confidence,
                        now,
                        user_id,
                        weakness_id,
                    ),
                )
                conn.commit()
                return self._get_weakness(conn, user_id, weakness_id), False

            weakness_id = new_id("weakness")
            try:
                conn.execute(
                    """
                    INSERT INTO learning_weaknesses(
                        weakness_id, user_id, child_id, subject, grade, category,
                        title, normalized_title, evidence, severity, status,
                        source_run_id, ability_id, behavior_id, match_confidence,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        weakness_id,
                        user_id,
                        child_id,
                        subject,
                        profile.grade,
                        category,
                        safe_title,
                        normalized_title,
                        safe_evidence,
                        severity,
                        "active",
                        source_run_id,
                        ability_id,
                        behavior_id,
                        match_confidence,
                        now,
                        now,
                    ),
                )
                conn.commit()
                return self._get_weakness(conn, user_id, weakness_id), True
            except sqlite3.IntegrityError:
                conn.rollback()
                existing = conn.execute(
                    """
                    SELECT weakness_id
                    FROM learning_weaknesses
                    WHERE
                        user_id = ?
                        AND child_id = ?
                        AND subject = ?
                        AND category = ?
                        AND normalized_title = ?
                        AND status = 'active'
                    """,
                    (user_id, child_id, subject, category, normalized_title),
                ).fetchone()
                if existing is None:
                    raise
                weakness_id = str(existing["weakness_id"])
                conn.execute(
                    """
                    UPDATE learning_weaknesses
                    SET
                        title = ?,
                        evidence = ?,
                        severity = ?,
                        source_run_id = ?,
                        ability_id = COALESCE(?, ability_id),
                        behavior_id = COALESCE(?, behavior_id),
                        match_confidence = COALESCE(?, match_confidence),
                        updated_at = ?
                    WHERE user_id = ? AND weakness_id = ?
                    """,
                    (
                        safe_title,
                        safe_evidence,
                        severity,
                        source_run_id,
                        ability_id,
                        behavior_id,
                        match_confidence,
                        utc_now(),
                        user_id,
                        weakness_id,
                    ),
                )
                conn.commit()
                return self._get_weakness(conn, user_id, weakness_id), False

    def update_weakness_status(
        self,
        user_id: str,
        weakness_id: str,
        status: str,
    ) -> LearningWeaknessRecord:
        validate_status(status)
        now = utc_now()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE learning_weaknesses
                SET status = ?, updated_at = ?
                WHERE user_id = ? AND weakness_id = ?
                """,
                (status, now, user_id, weakness_id),
            ).rowcount
            if updated == 0:
                raise LookupError(f"weakness not found: {weakness_id}")
            conn.commit()
            return self._get_weakness(conn, user_id, weakness_id)

    def get_weakness(
        self,
        user_id: str,
        weakness_id: str,
    ) -> LearningWeaknessRecord:
        with self._connect() as conn:
            return self._get_weakness(conn, user_id, weakness_id)

    def create_learning_plan_from_weaknesses(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
        goal: str | None = None,
        created_from_prompt: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> LearningPlanSnapshot:
        profile = self.get_or_create_default_profile(user_id)
        normalized_start_date = normalize_plan_date(start_date)
        normalized_end_date = normalize_plan_date(end_date)
        active_records = [
            record
            for record in self.list_weaknesses(user_id, child_id)
            if record.status in ("active", "improving")
        ]
        if not active_records:
            raise ValueError("learning plan requires active weaknesses")

        selected_records = sorted(
            active_records,
            key=lambda record: (
                SUBJECT_SORT_ORDER.get(record.subject, 99),
                SEVERITY_SORT_ORDER.get(record.severity, 99),
                record.updated_at,
            ),
        )[:6]
        safe_prompt = sanitize_learning_text(created_from_prompt or "")
        safe_goal = sanitize_learning_text(goal or safe_prompt)
        if not safe_goal:
            safe_goal = "基于当前薄弱点安排一周可执行练习。"

        now = utc_now()
        plan_id = new_id("plan")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_plans(
                    plan_id, user_id, child_id, title, goal, status,
                    start_date, end_date, created_from_prompt, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    user_id,
                    profile.child_id,
                    "本周学习计划",
                    safe_goal,
                    "draft",
                    normalized_start_date,
                    normalized_end_date,
                    safe_prompt,
                    now,
                    now,
                ),
            )
            for sort_order, record in enumerate(selected_records, start=1):
                item = learning_plan_item_from_weakness(record, sort_order)
                conn.execute(
                    """
                    INSERT INTO learning_plan_items(
                        item_id, plan_id, user_id, child_id, subject, title,
                        description, target_weakness_id, frequency,
                        estimated_minutes, sort_order, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("plan_item"),
                        plan_id,
                        user_id,
                        profile.child_id,
                        item["subject"],
                        item["title"],
                        item["description"],
                        item["target_weakness_id"],
                        item["frequency"],
                        item["estimated_minutes"],
                        item["sort_order"],
                        now,
                        now,
                    ),
                )
            conn.commit()
            return self._get_learning_plan_snapshot(conn, user_id, plan_id)

    def list_learning_plans(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
        status: str | None = None,
    ) -> list[LearningPlanRecord]:
        params: list[str] = [user_id, child_id]
        where_status = ""
        if status is not None:
            validate_plan_status(status)
            where_status = "AND status = ?"
            params.append(status)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    plan_id, user_id, child_id, title, goal, status,
                    start_date, end_date, created_from_prompt,
                    created_at, updated_at
                FROM learning_plans
                WHERE user_id = ? AND child_id = ?
                {where_status}
                ORDER BY updated_at DESC, plan_id DESC
                """,
                params,
            ).fetchall()
            return [learning_plan_from_row(row) for row in rows]

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
            checkins_by_item_date: dict[
                tuple[str, str],
                LearningPlanCheckinRecord,
            ] = {}
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

    def get_current_learning_plan(
        self,
        user_id: str,
        child_id: str = DEFAULT_CHILD_ID,
    ) -> LearningPlanSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT plan_id
                FROM learning_plans
                WHERE user_id = ? AND child_id = ? AND status != 'archived'
                ORDER BY
                    CASE status
                        WHEN 'active' THEN 0
                        WHEN 'draft' THEN 1
                        WHEN 'paused' THEN 2
                        WHEN 'completed' THEN 3
                        ELSE 4
                    END ASC,
                    updated_at DESC,
                    plan_id DESC
                LIMIT 1
                """,
                (user_id, child_id),
            ).fetchone()
            if row is None:
                return None
            return self._get_learning_plan_snapshot(conn, user_id, str(row["plan_id"]))

    def update_learning_plan_status(
        self,
        user_id: str,
        plan_id: str,
        status: str,
    ) -> LearningPlanSnapshot:
        validate_plan_status(status)
        now = utc_now()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE learning_plans
                SET status = ?, updated_at = ?
                WHERE user_id = ? AND plan_id = ?
                """,
                (status, now, user_id, plan_id),
            ).rowcount
            if updated == 0:
                raise LookupError(f"learning plan not found: {plan_id}")
            conn.commit()
            return self._get_learning_plan_snapshot(conn, user_id, plan_id)

    def upsert_learning_plan_checkin(
        self,
        user_id: str,
        plan_id: str,
        item_id: str,
        checkin_date: str,
        status: str,
        note: str | None = None,
    ) -> LearningPlanSnapshot:
        normalized_date = normalize_plan_date(checkin_date)
        if normalized_date is None:
            raise ValueError("learning plan checkin date is required")
        validate_plan_checkin_status(status)
        safe_note = sanitize_learning_text(note or "")
        now = utc_now()
        with self._connect() as conn:
            item = conn.execute(
                """
                SELECT item_id
                FROM learning_plan_items
                WHERE user_id = ? AND plan_id = ? AND item_id = ?
                """,
                (user_id, plan_id, item_id),
            ).fetchone()
            if item is None:
                raise LookupError(f"learning plan item not found: {item_id}")

            existing = conn.execute(
                """
                SELECT checkin_id
                FROM learning_plan_checkins
                WHERE user_id = ? AND plan_id = ? AND item_id = ? AND checkin_date = ?
                """,
                (user_id, plan_id, item_id, normalized_date),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO learning_plan_checkins(
                        checkin_id, plan_id, item_id, user_id, child_id,
                        checkin_date, status, note, created_at, updated_at
                    )
                    SELECT ?, plan_id, item_id, user_id, child_id, ?, ?, ?, ?, ?
                    FROM learning_plan_items
                    WHERE user_id = ? AND plan_id = ? AND item_id = ?
                    """,
                    (
                        new_id("checkin"),
                        normalized_date,
                        status,
                        safe_note,
                        now,
                        now,
                        user_id,
                        plan_id,
                        item_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE learning_plan_checkins
                    SET status = ?, note = ?, updated_at = ?
                    WHERE user_id = ? AND checkin_id = ?
                    """,
                    (status, safe_note, now, user_id, str(existing["checkin_id"])),
                )
            conn.execute(
                """
                UPDATE learning_plans
                SET updated_at = ?
                WHERE user_id = ? AND plan_id = ?
                """,
                (now, user_id, plan_id),
            )
            conn.commit()
            return self._get_learning_plan_snapshot(conn, user_id, plan_id)

    def _get_weakness(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        weakness_id: str,
    ) -> LearningWeaknessRecord:
        row = conn.execute(
            """
            SELECT
                weakness_id, user_id, child_id, subject, grade, category,
                title, normalized_title, evidence, severity, status,
                source_run_id, ability_id, behavior_id, match_confidence,
                created_at, updated_at
            FROM learning_weaknesses
            WHERE user_id = ? AND weakness_id = ?
            """,
            (user_id, weakness_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"weakness not found: {weakness_id}")
        return learning_weakness_from_row(row)

    def _get_learning_plan_snapshot(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        plan_id: str,
    ) -> LearningPlanSnapshot:
        plan_row = conn.execute(
            """
            SELECT
                plan_id, user_id, child_id, title, goal, status,
                start_date, end_date, created_from_prompt, created_at, updated_at
            FROM learning_plans
            WHERE user_id = ? AND plan_id = ?
            """,
            (user_id, plan_id),
        ).fetchone()
        if plan_row is None:
            raise LookupError(f"learning plan not found: {plan_id}")

        item_rows = conn.execute(
            """
            SELECT
                item_id, plan_id, user_id, child_id, subject, title,
                description, target_weakness_id, frequency, estimated_minutes,
                sort_order, created_at, updated_at
            FROM learning_plan_items
            WHERE user_id = ? AND plan_id = ?
            ORDER BY
                CASE subject
                    WHEN 'chinese' THEN 0
                    WHEN 'english' THEN 1
                    WHEN 'math' THEN 2
                    ELSE 3
                END ASC,
                sort_order ASC,
                item_id ASC
            """,
            (user_id, plan_id),
        ).fetchall()
        checkin_rows = conn.execute(
            """
            SELECT
                checkin_id, plan_id, item_id, user_id, child_id,
                checkin_date, status, note, created_at, updated_at
            FROM learning_plan_checkins
            WHERE user_id = ? AND plan_id = ?
            ORDER BY checkin_date DESC, updated_at DESC
            """,
            (user_id, plan_id),
        ).fetchall()
        checkins_by_item_id: dict[str, list[LearningPlanCheckinRecord]] = {}
        for row in checkin_rows:
            record = learning_plan_checkin_from_row(row)
            checkins_by_item_id.setdefault(record.item_id, []).append(record)

        return LearningPlanSnapshot(
            plan=learning_plan_from_row(plan_row),
            items=[learning_plan_item_from_row(row) for row in item_rows],
            checkins_by_item_id=checkins_by_item_id,
        )


def child_profile_from_row(row: sqlite3.Row) -> ChildProfileRecord:
    return ChildProfileRecord(
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        display_name=str(row["display_name"]),
        grade=str(row["grade"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def learning_weakness_from_row(row: sqlite3.Row) -> LearningWeaknessRecord:
    source_run_id = row["source_run_id"]
    ability_id = row["ability_id"]
    behavior_id = row["behavior_id"]
    match_confidence = row["match_confidence"]
    return LearningWeaknessRecord(
        weakness_id=str(row["weakness_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        subject=str(row["subject"]),
        grade=str(row["grade"]),
        category=str(row["category"]),
        title=str(row["title"]),
        normalized_title=str(row["normalized_title"]),
        evidence=str(row["evidence"]),
        severity=str(row["severity"]),
        status=str(row["status"]),
        source_run_id=str(source_run_id) if source_run_id is not None else None,
        ability_id=str(ability_id) if ability_id is not None else None,
        behavior_id=str(behavior_id) if behavior_id is not None else None,
        match_confidence=(
            float(match_confidence) if match_confidence is not None else None
        ),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def learning_plan_from_row(row: sqlite3.Row) -> LearningPlanRecord:
    start_date = row["start_date"]
    end_date = row["end_date"]
    return LearningPlanRecord(
        plan_id=str(row["plan_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        title=str(row["title"]),
        goal=str(row["goal"]),
        status=str(row["status"]),
        start_date=str(start_date) if start_date is not None else None,
        end_date=str(end_date) if end_date is not None else None,
        created_from_prompt=str(row["created_from_prompt"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


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


def learning_plan_item_from_row(row: sqlite3.Row) -> LearningPlanItemRecord:
    target_weakness_id = row["target_weakness_id"]
    return LearningPlanItemRecord(
        item_id=str(row["item_id"]),
        plan_id=str(row["plan_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        subject=str(row["subject"]),
        title=str(row["title"]),
        description=str(row["description"]),
        target_weakness_id=(
            str(target_weakness_id) if target_weakness_id is not None else None
        ),
        frequency=str(row["frequency"]),
        estimated_minutes=int(row["estimated_minutes"]),
        sort_order=int(row["sort_order"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def learning_plan_checkin_from_row(row: sqlite3.Row) -> LearningPlanCheckinRecord:
    return LearningPlanCheckinRecord(
        checkin_id=str(row["checkin_id"]),
        plan_id=str(row["plan_id"]),
        item_id=str(row["item_id"]),
        user_id=str(row["user_id"]),
        child_id=str(row["child_id"]),
        checkin_date=str(row["checkin_date"]),
        status=str(row["status"]),
        note=str(row["note"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def serialize_child_profile(record: ChildProfileRecord) -> dict[str, object]:
    return {
        "userId": record.user_id,
        "childId": record.child_id,
        "displayName": record.display_name,
        "grade": record.grade,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def serialize_learning_weakness(record: LearningWeaknessRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "weaknessId": record.weakness_id,
        "userId": record.user_id,
        "childId": record.child_id,
        "subject": record.subject,
        "grade": record.grade,
        "category": record.category,
        "title": record.title,
        "evidence": record.evidence,
        "severity": record.severity,
        "status": record.status,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }
    if record.source_run_id is not None:
        payload["sourceRunId"] = record.source_run_id
    if record.ability_id is not None:
        payload["abilityId"] = record.ability_id
        try:
            ability = resolve_curriculum_ability(
                record.grade,
                record.subject,
                record.ability_id,
            )
        except LookupError:
            pass
        else:
            payload["abilityTitle"] = ability.title
    if record.behavior_id is not None:
        payload["behaviorId"] = record.behavior_id
        try:
            behavior = resolve_curriculum_behavior(
                record.grade,
                record.subject,
                record.behavior_id,
            )
        except LookupError:
            pass
        else:
            payload["abilityTitle"] = behavior.ability_title
            payload["behaviorTitle"] = behavior.behavior_title
    if record.match_confidence is not None:
        payload["matchConfidence"] = record.match_confidence
    return payload


def serialize_learning_plan_checkin(
    record: LearningPlanCheckinRecord,
) -> dict[str, object]:
    return {
        "checkinId": record.checkin_id,
        "planId": record.plan_id,
        "itemId": record.item_id,
        "userId": record.user_id,
        "childId": record.child_id,
        "checkinDate": record.checkin_date,
        "status": record.status,
        "note": record.note,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def serialize_learning_plan(snapshot: LearningPlanSnapshot) -> dict[str, object]:
    return {
        "planId": snapshot.plan.plan_id,
        "userId": snapshot.plan.user_id,
        "childId": snapshot.plan.child_id,
        "title": snapshot.plan.title,
        "goal": snapshot.plan.goal,
        "status": snapshot.plan.status,
        "startDate": snapshot.plan.start_date,
        "endDate": snapshot.plan.end_date,
        "createdFromPrompt": snapshot.plan.created_from_prompt,
        "createdAt": snapshot.plan.created_at,
        "updatedAt": snapshot.plan.updated_at,
        "items": [
            {
                "itemId": item.item_id,
                "planId": item.plan_id,
                "userId": item.user_id,
                "childId": item.child_id,
                "subject": item.subject,
                "title": item.title,
                "description": item.description,
                "targetWeaknessId": item.target_weakness_id,
                "frequency": item.frequency,
                "estimatedMinutes": item.estimated_minutes,
                "sortOrder": item.sort_order,
                "createdAt": item.created_at,
                "updatedAt": item.updated_at,
                "checkins": [
                    serialize_learning_plan_checkin(checkin)
                    for checkin in snapshot.checkins_by_item_id.get(item.item_id, [])
                ],
            }
            for item in snapshot.items
        ],
    }


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
