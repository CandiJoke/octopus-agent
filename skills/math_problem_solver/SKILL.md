---
id: math_problem_solver
name: math_problem_solver
display_name: Math Problem Solver
description: 面向数学、数量、公式和精确计算任务的技能，会优先把可计算部分交给 calculator。
category: 任务技能
status: available
source: local
enabled: true
tools: calculator
---

# Math Problem Solver

- 当用户问题包含算术、比例、单位换算或需要精确数字时，先识别可计算表达式。
- 可计算部分交给 `calculator`，不要只靠语言模型心算。
- 输出时保留关键表达式和结果，让用户能看懂计算依据。
