"""
Agent HTTP 服务 —— 把 Agent 变成 API
启动: cd agent-hub && source .venv/bin/activate && uvicorn api_server:app --reload --port 8000
测试: curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message":"帮我算 123*456"}'
"""
import hashlib
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent as create_langchain_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from agent_console import (
    checkpointer,
    DB_PATH,
    load_app_env,
    selected_base_url_value,
    selected_model,
)
from agent_context import AGENT_SYSTEM_PROMPT
from capabilities import build_capability_catalog
from history_store import (
    AgentRunEventRecord,
    AgentRunRecord,
    ChatMessageRecord,
    ChatSessionRecord,
    HistoryStore,
    new_id,
)
from tools import tools
from skills import build_skill_catalog, get_skill, serialize_skill_detail

logger = logging.getLogger(__name__)

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
    model_config = ConfigDict(populate_by_name=True)

    message: str
    user_id: str = Field(
        default="anonymous_user_default",
        validation_alias=AliasChoices("userId", "user_id"),
    )
    session_id: str = Field(
        default="default",
        validation_alias=AliasChoices("sessionId", "session_id"),
    )


class ChatResponse(BaseModel):
    reply: str
    steps: list[dict]  # Agent 思考过程


# ========== 创建 Agent（带 Checkpointer 实现多轮记忆）==========

llm = ChatOpenAI(
    model=selected_model(),
    temperature=0,
    base_url=selected_base_url_value(),
)

agent = create_langchain_agent(
    llm,
    tools=tools,
    checkpointer=checkpointer,
    system_prompt=AGENT_SYSTEM_PROMPT,
)
history_store = HistoryStore(DB_PATH)
history_store.initialize()

STREAM_INPUT_LIMIT = 200
STREAM_OUTPUT_LIMIT = 500
STREAM_ERROR_MESSAGE = "Agent 运行失败，请稍后重试。"
STREAM_STOPPED_MESSAGE = "用户已停止本次运行。"
STREAM_STOPPED_ANSWER = "已停止输出。"


def get_history_store() -> HistoryStore:
    return history_store


def agent_thread_id(user_id: str, session_id: str) -> str:
    digest = hashlib.sha256(f"{user_id}\0{session_id}".encode("utf-8")).hexdigest()
    return f"thread_{digest[:32]}"


def serialize_session(record: ChatSessionRecord) -> dict[str, object]:
    return {
        "sessionId": record.session_id,
        "title": record.title,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def serialize_message(
    record: ChatMessageRecord,
    run_status: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "messageId": record.message_id,
        "sessionId": record.session_id,
        "role": record.role,
        "content": record.content,
        "createdAt": record.created_at,
    }
    if record.run_id is not None:
        payload["runId"] = record.run_id
    if run_status is not None:
        payload["runStatus"] = run_status
    return payload


def serialize_run(record: AgentRunRecord) -> dict[str, object]:
    return {
        "runId": record.run_id,
        "sessionId": record.session_id,
        "userMessageId": record.user_message_id,
        "agentMessageId": record.agent_message_id,
        "status": record.status,
        "prompt": record.prompt,
        "model": record.model,
        "startedAt": record.started_at,
        "endedAt": record.ended_at,
        "errorMessage": record.error_message,
    }


def serialize_run_event(record: AgentRunEventRecord) -> dict[str, object]:
    return {
        "eventId": record.event_id,
        "runId": record.run_id,
        "sequence": record.sequence,
        "eventType": record.event_type,
        "payload": record.payload,
        "createdAt": record.created_at,
    }


def truncate_stream_value(value: object, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit]


def make_stage_event(stage: str, message: str) -> dict[str, object]:
    return {
        "type": "stage",
        "stage": stage,
        "message": message,
    }


def make_tool_start_event(
    tool: str,
    input_value: object,
    run_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "tool_start",
        "tool": tool,
        "input": truncate_stream_value(input_value, STREAM_INPUT_LIMIT),
    }
    if run_id is not None:
        payload["run_id"] = run_id
    return payload


def make_tool_end_event(
    tool: str,
    output_value: object,
    elapsed_ms: int | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "tool_end",
        "tool": tool,
        "output": truncate_stream_value(output_value, STREAM_OUTPUT_LIMIT),
    }
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    if run_id is not None:
        payload["run_id"] = run_id
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


def make_stopped_event(message: str) -> dict[str, object]:
    return {
        "type": "stopped",
        "message": message,
    }


def stream_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def done_event() -> str:
    return "data: [DONE]\n\n"


def with_agent_run_id(payload: dict[str, object], run_id: str) -> dict[str, object]:
    return {**payload, "runId": run_id}


def persist_stream_event(
    store: HistoryStore,
    user_id: str,
    session_id: str,
    run_id: str,
    payload: dict[str, object],
) -> None:
    event_type = str(payload.get("type", "unknown"))
    store.append_run_event(user_id, session_id, run_id, event_type, payload)


@asynccontextmanager
async def stream_agent_context(stream_agent=None):
    if stream_agent is not None:
        yield stream_agent
        return

    async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as async_checkpointer:
        yield create_langchain_agent(
            llm,
            tools=tools,
            checkpointer=async_checkpointer,
            system_prompt=AGENT_SYSTEM_PROMPT,
        )


# ========== API 接口 ==========

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """普通请求：一次返回完整结果"""
    config = {"configurable": {"thread_id": agent_thread_id(req.user_id, req.session_id)}}

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


async def stream_chat_events(
    req: ChatRequest,
    stream_agent=None,
    store: HistoryStore | None = None,
) -> AsyncIterator[str]:
    active_store = store or history_store
    run_id = new_id("run")
    history_persistence_enabled = False
    event_persistence_enabled = False
    config = {"configurable": {"thread_id": agent_thread_id(req.user_id, req.session_id)}}
    tool_started_at: dict[str, float] = {}
    answer_started = False
    answer_parts: list[str] = []
    cancelled = False
    run_finished = False

    def emit(payload: dict[str, object]) -> str:
        nonlocal event_persistence_enabled

        event_payload = with_agent_run_id(payload, run_id)
        if event_persistence_enabled:
            try:
                persist_stream_event(
                    active_store,
                    req.user_id,
                    req.session_id,
                    run_id,
                    event_payload,
                )
            except Exception:
                event_persistence_enabled = False
                logger.exception("Chat history event persistence failed")
        return stream_event(event_payload)

    def persist_stopped_run() -> None:
        nonlocal event_persistence_enabled

        stopped_payload = with_agent_run_id(
            make_stopped_event(STREAM_STOPPED_MESSAGE),
            run_id,
        )
        if event_persistence_enabled:
            try:
                persist_stream_event(
                    active_store,
                    req.user_id,
                    req.session_id,
                    run_id,
                    stopped_payload,
                )
            except Exception:
                event_persistence_enabled = False
                logger.exception("Chat history stop event persistence failed")

        agent_message_id = None
        try:
            stopped_message = active_store.save_message(
                req.user_id,
                req.session_id,
                role="agent",
                content="".join(answer_parts) or STREAM_STOPPED_ANSWER,
                run_id=run_id,
            )
            agent_message_id = stopped_message.message_id
        except Exception:
            logger.exception("Chat history stop message persistence failed")

        try:
            active_store.stop_run(
                req.user_id,
                run_id,
                STREAM_STOPPED_MESSAGE,
                agent_message_id=agent_message_id,
            )
        except Exception:
            logger.exception("Chat history stop persistence failed")

    try:
        active_store.ensure_session(req.user_id, req.session_id, title="新会话")
        user_message = active_store.save_message(
            req.user_id,
            req.session_id,
            role="user",
            content=req.message,
        )
        active_store.create_run(
            req.user_id,
            req.session_id,
            user_message_id=user_message.message_id,
            prompt=req.message,
            model=selected_model(),
            run_id=run_id,
        )
        history_persistence_enabled = True
        event_persistence_enabled = True
    except Exception:
        logger.exception("Chat history setup failed")

    try:
        yield emit(make_stage_event("received", "已收到问题"))
        async with stream_agent_context(stream_agent) as active_agent:
            yield emit(make_stage_event("planning", "正在判断是否需要工具"))

            async for event in active_agent.astream_events(
                {"messages": [("user", req.message)]},
                config=config,
                version="v2",
            ):
                kind = event.get("event", "")

                if kind == "on_tool_start":
                    tool_name = event["name"]
                    event_run_id = event.get("run_id")
                    tool_run_id = (
                        str(event_run_id) if event_run_id is not None else None
                    )
                    timing_key = tool_run_id or tool_name
                    tool_started_at[timing_key] = time.perf_counter()
                    yield emit(make_stage_event("tooling", f"正在调用 {tool_name}"))
                    yield emit(
                        make_tool_start_event(
                            tool_name,
                            event["data"].get("input", ""),
                            run_id=tool_run_id,
                        )
                    )

                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    event_run_id = event.get("run_id")
                    tool_run_id = (
                        str(event_run_id) if event_run_id is not None else None
                    )
                    timing_key = tool_run_id or tool_name
                    started_at = tool_started_at.pop(timing_key, None)
                    elapsed_ms = None
                    if started_at is not None:
                        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
                    yield emit(
                        make_tool_end_event(
                            tool_name,
                            event["data"].get("output", ""),
                            elapsed_ms=elapsed_ms,
                            run_id=tool_run_id,
                        )
                    )

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = getattr(chunk, "content", "")
                    if content:
                        if not answer_started:
                            answer_started = True
                            yield emit(make_stage_event("answering", "正在整理最终回答"))
                        answer_parts.append(content)
                        yield emit(make_text_event(content))

            final_answer = "".join(answer_parts)
            if history_persistence_enabled:
                try:
                    agent_message = active_store.save_message(
                        req.user_id,
                        req.session_id,
                        role="agent",
                        content=final_answer,
                        run_id=run_id,
                    )
                    active_store.complete_run(
                        req.user_id,
                        run_id,
                        agent_message.message_id,
                    )
                    run_finished = True
                except Exception:
                    history_persistence_enabled = False
                    logger.exception("Chat history completion persistence failed")
            yield emit(make_stage_event("completed", "已完成"))
    except (asyncio.CancelledError, GeneratorExit):
        cancelled = True
        if history_persistence_enabled and not run_finished:
            persist_stopped_run()
        raise
    except Exception:
        logger.exception("Chat stream failed")
        if history_persistence_enabled:
            try:
                active_store.fail_run(req.user_id, run_id, STREAM_ERROR_MESSAGE)
            except Exception:
                logger.exception("Chat history failure persistence failed")
        yield emit(make_error_event(STREAM_ERROR_MESSAGE))
    finally:
        if not cancelled:
            yield done_event()


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    store: HistoryStore = Depends(get_history_store),
):
    """SSE 流式：实时推送可观察工作过程和回答"""
    return StreamingResponse(
        stream_chat_events(req, store=store),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/users/{user_id}/sessions")
def list_user_sessions(
    user_id: str,
    limit: int = 20,
    store: HistoryStore = Depends(get_history_store),
):
    safe_limit = min(max(limit, 1), 100)
    return [
        serialize_session(session)
        for session in store.list_sessions(user_id, safe_limit)
    ]


@app.get("/capabilities")
def list_capabilities():
    return build_capability_catalog()


@app.get("/skills")
def list_skill_catalog():
    return build_skill_catalog()


@app.get("/skills/{skill_id}")
def get_skill_detail(skill_id: str):
    skill = get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return serialize_skill_detail(skill)


@app.post("/users/{user_id}/sessions")
def create_user_session(
    user_id: str,
    store: HistoryStore = Depends(get_history_store),
):
    return serialize_session(store.create_session(user_id))


@app.delete("/users/{user_id}/sessions/{session_id}", status_code=204)
def delete_user_session(
    user_id: str,
    session_id: str,
    store: HistoryStore = Depends(get_history_store),
):
    if not store.delete_session(user_id, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@app.get("/users/{user_id}/sessions/{session_id}/messages")
def list_session_messages(
    user_id: str,
    session_id: str,
    store: HistoryStore = Depends(get_history_store),
):
    messages = store.list_messages(user_id, session_id)
    run_statuses = store.list_run_statuses(
        user_id,
        [message.run_id for message in messages if message.run_id is not None],
    )
    return [
        serialize_message(
            message,
            run_statuses.get(message.run_id) if message.run_id is not None else None,
        )
        for message in messages
    ]


@app.get("/users/{user_id}/runs/{run_id}")
def get_run_detail(
    user_id: str,
    run_id: str,
    store: HistoryStore = Depends(get_history_store),
):
    detail = store.get_run_detail(user_id, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run": serialize_run(detail.run),
        "events": [serialize_run_event(event) for event in detail.events],
    }


@app.get("/health")
def health():
    return {"status": "ok", "model": selected_model()}


# ========== 启动说明 ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
