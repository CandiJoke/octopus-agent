---
name: record_chinese_literacy_weakness
description: 记录一年级语文学习薄弱点。仅当家长明确描述孩子在拼音、识字、朗读、表达或学习习惯上的具体问题时使用。输入分类、标题、依据和严重程度。
---

# Record Chinese Literacy Weakness

- **输入**：category、title、evidence、severity
- **category 可用值**：
  - `pinyin` / `拼音`
  - `character_recognition` / `识字`
  - `reading` / `朗读`
  - `expression` / `表达`
  - `learning_habit` / `学习习惯`
- **severity 可用值**：
  - `mild` / `轻微`
  - `medium` / `中等`
  - `high` / `明显`
- **输出**：记录或更新结果
- **限制**：不接收 userId、childId 或数据库 ID，这些由后端运行上下文注入
- **隐私**：title 和 evidence 不要写真实姓名、学校、住址、电话、诊断标签或家庭成员身份信息
