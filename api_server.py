"""
Agent HTTP 服务 —— 把 Agent 变成 API
启动: cd agent-hub && source .venv/bin/activate && uvicorn api_server:app --reload --port 8000
测试: curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message":"帮我算 123*456"}'
"""
import json
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent as create_langchain_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from agent_console import (
    checkpointer,
    DB_PATH,
    load_app_env,
    selected_base_url_value,
    selected_model,
)
from tools import tools

load_app_env()  # 自动从 .env 读 OPENAI_API_KEY / OPENAI_BASE_URL

app = FastAPI(title="Agent Hub")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # 多用户会话隔离


class ChatResponse(BaseModel):
    reply: str
    steps: list[dict]  # Agent 思考过程


# ========== 创建 Agent（带 Checkpointer 实现多轮记忆）==========

llm = ChatOpenAI(
    model=selected_model(),
    temperature=0,
    base_url=selected_base_url_value(),
)

agent = create_langchain_agent(llm, tools=tools, checkpointer=checkpointer)

STREAM_INPUT_LIMIT = 200
STREAM_OUTPUT_LIMIT = 500


def truncate_stream_value(value: object, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit]


def make_stage_event(stage: str, message: str) -> dict[str, object]:
    return {
        "type": "stage",
        "stage": stage,
        "message": message,
    }


def make_tool_start_event(tool: str, input_value: object) -> dict[str, object]:
    return {
        "type": "tool_start",
        "tool": tool,
        "input": truncate_stream_value(input_value, STREAM_INPUT_LIMIT),
    }


def make_tool_end_event(
    tool: str,
    output_value: object,
    elapsed_ms: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "tool_end",
        "tool": tool,
        "output": truncate_stream_value(output_value, STREAM_OUTPUT_LIMIT),
    }
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    return payload


def make_text_event(content: str) -> dict[str, object]:
    return {
        "type": "text",
        "content": content,
    }


def make_error_event(message: str) -> dict[str, object]:
    return {
        "type": "error",
        "message": message,
    }


def stream_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def done_event() -> str:
    return "data: [DONE]\n\n"


# ========== API 接口 ==========

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """普通请求：一次返回完整结果"""
    config = {"configurable": {"thread_id": req.session_id}}

    # Agent 执行
    result = agent.invoke(
        {"messages": [("user", req.message)]},
        config=config,
    )

    # 提取最终回答
    final_msg = result["messages"][-1]
    reply = final_msg.content if hasattr(final_msg, "content") else str(final_msg)

    # 提取思考步骤（给前端展示用）
    steps = []
    for msg in result["messages"]:
        role = type(msg).__name__
        if role == "AIMessage" and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({
                    "type": "tool_call",
                    "tool": tc["name"],
                    "args": tc["args"],
                })
        elif role == "ToolMessage":
            steps.append({
                "type": "tool_result",
                "content": msg.content[:200],
            })

    return ChatResponse(reply=reply, steps=steps)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式：实时推送思考过程和回答"""

    async def event_generator() -> AsyncIterator[str]:
        config = {"configurable": {"thread_id": req.session_id}}

        # LangGraph 的 astream_events 逐事件推送
        async for event in agent.astream_events(
            {"messages": [("user", req.message)]},
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")

            # 工具调用开始
            if kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': event['name'], 'input': str(event['data'].get('input', ''))[:200]}, ensure_ascii=False)}\n\n"

            # 工具调用结束
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': event['name'], 'output': str(event['data'].get('output', ''))[:500]}, ensure_ascii=False)}\n\n"

            # LLM 流式输出 token
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk.content}, ensure_ascii=False)}\n\n"

        # 结束标记
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": selected_model()}


# ========== 启动说明 ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
