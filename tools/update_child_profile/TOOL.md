---
name: update_child_profile
description: 更新小学阶段孩子学习画像。仅当家长明确说明孩子当前年级或年级发生变化时使用。输入年级。
---

# Update Child Profile

- **输入**：grade
- **grade 可用值**：
  - `grade_1` / `一年级`
  - `grade_2` / `二年级`
  - `grade_3` / `三年级`
  - `grade_4` / `四年级`
  - `grade_5` / `五年级`
  - `grade_6` / `六年级`
- **输出**：更新结果
- **限制**：不接收 userId、childId 或数据库 ID，这些由后端运行上下文注入
- **触发**：用户明确表达“孩子现在二年级了”“升到三年级了”“年级改成 grade_4”等画像基础信息变化
