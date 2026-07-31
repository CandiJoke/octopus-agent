KNOWLEDGE_BASE = {
    "langchain": "LangChain 是一个用于构建 LLM 应用的框架，支持链式调用、Agent、RAG 等功能。",
    "agent": "AI Agent 是能自主使用工具完成任务的智能体，核心是 LLM + 工具调用 + 决策循环。",
    "python": "Python 是一门解释型、面向对象的高级编程语言，以简洁易读著称。",
    "fastapi": "FastAPI 是一个现代、高性能的 Python Web 框架，基于类型提示，支持异步。",
}


def run(query: str) -> str:
    for key, value in KNOWLEDGE_BASE.items():
        if key.lower() in query.lower():
            return value
    return f"关于「{query}」，建议查阅最新文档或联网搜索。"
