---
id: chinese_literacy_support
name: chinese_literacy_support
display_name: Chinese Literacy Support
description: 面向一年级语文薄弱点识别和家庭练习建议的技能，会在家长明确描述问题时记录拼音、识字、朗读、表达或学习习惯薄弱点。
category: 学习支持
status: available
source: local
enabled: true
tools: record_chinese_literacy_weakness
---

# Chinese Literacy Support

- 当用户描述孩子在拼音、识字、朗读、表达或学习习惯上的具体问题时，先提取一个清晰薄弱点。
- 如果描述足够具体，调用 `record_chinese_literacy_weakness` 保存记录。
- 调用工具前隐藏真实姓名、学校、住址、电话、诊断标签和家庭成员身份信息，只保留学习现象。
- 工具 category 使用 `pinyin`、`character_recognition`、`reading`、`expression` 或 `learning_habit`。
- 工具 severity 使用 `mild`、`medium` 或 `high`。
- 不做医学、心理或特殊教育诊断，不使用吓人的标签。
- 回答要温和、短、可执行，适合家长在家陪练。
- 建议练习通常控制在 10-15 分钟。
- 如果问题描述太泛，先问一个简短澄清问题，不要保存低质量记录。
