---
id: knowledge_lookup
name: knowledge_lookup
display_name: Knowledge Lookup
description: 面向概念解释、项目知识和基础资料查询的技能，会优先使用 search_knowledge 获取可信上下文。
category: 任务技能
status: available
source: local
enabled: true
tools: search_knowledge
---

# Knowledge Lookup

- 当用户询问概念、框架或项目知识时，先判断本地知识库是否能回答。
- 需要资料支撑时调用 `search_knowledge`，再基于返回内容组织答案。
- 如果知识库没有命中，明确说明当前知识不足，并给出下一步查询方向。
