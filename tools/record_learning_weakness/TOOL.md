---
name: record_learning_weakness
description: 记录小学阶段语文、英语或数学学习薄弱点。仅当家长明确描述具体问题时使用。输入学科、分类、标题、依据和严重程度。
---

# Record Learning Weakness

- **subject 可用值**：`chinese` / `语文`，`english` / `英语`，`math` / `数学`
- **中文 category**：`pinyin` / `拼音`，`character_recognition` / `识字`，`reading` / `朗读`，`expression` / `表达`，`learning_habit` / `学习习惯`
- **英语 category**：`listening` / `听音辨音`，`phonics` / `自然拼读`，`vocabulary` / `词汇`，`speaking` / `口语表达`，`learning_habit` / `学习习惯`
- **数学 category**：`number_sense` / `数感`，`calculation` / `计算`，`word_problem` / `应用题`，`geometry` / `图形空间`，`learning_habit` / `学习习惯`
- **severity 可用值**：`mild` / `轻微`，`medium` / `中等`，`high` / `明显`
- **ability_id / behavior_id / match_confidence**：可选。只有明确匹配到课标能力树的能力点或可观察表现时填写；不确定时留空。
- **一年级示例**：`behavior_id=chinese_g1_pinyin_initials_distinguish_bpdq` 表示“能区分 b/p/d/q 的形和音”。
- **输出**：记录或更新结果
- **限制**：不接收 userId、childId 或数据库 ID，这些由后端运行上下文注入
- **隐私**：title 和 evidence 不要写真实姓名、学校、住址、电话、诊断标签或家庭成员身份信息
