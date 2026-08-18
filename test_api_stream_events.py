import json
import os
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import api_server
from history_store import HistoryStore


def parse_sse_payload(chunk: str) -> dict:
    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    return json.loads(chunk.removeprefix("data: ").strip())


class StreamEventHelperTests(unittest.TestCase):
    def test_stage_event_serializes_as_sse_json(self):
        chunk = api_server.stream_event(
            api_server.make_stage_event("received", "已收到问题")
        )

        self.assertEqual(
            parse_sse_payload(chunk),
            {
                "type": "stage",
                "stage": "received",
                "message": "已收到问题",
            },
        )

    def test_tool_events_truncate_display_payloads(self):
        input_payload = {"expression": "1+" * 300}
        output_payload = "结果" * 400

        start_event = api_server.make_tool_start_event(
            "calculator",
            input_payload,
            run_id="tool-run-1",
        )
        end_event = api_server.make_tool_end_event(
            "calculator",
            output_payload,
            elapsed_ms=42,
            run_id="tool-run-1",
        )

        self.assertEqual(start_event["type"], "tool_start")
        self.assertEqual(start_event["tool"], "calculator")
        self.assertEqual(start_event["run_id"], "tool-run-1")
        self.assertLessEqual(len(start_event["input"]), api_server.STREAM_INPUT_LIMIT)
        self.assertEqual(end_event["type"], "tool_end")
        self.assertEqual(end_event["tool"], "calculator")
        self.assertEqual(end_event["run_id"], "tool-run-1")
        self.assertEqual(end_event["elapsed_ms"], 42)
        self.assertLessEqual(len(end_event["output"]), api_server.STREAM_OUTPUT_LIMIT)
        self.assertNotIn(
            "run_id",
            api_server.make_tool_start_event("calculator", input_payload),
        )

    def test_text_error_and_done_events_have_expected_shapes(self):
        self.assertEqual(
            api_server.make_text_event("hello"),
            {"type": "text", "content": "hello"},
        )
        self.assertEqual(
            api_server.make_error_event("boom"),
            {"type": "error", "message": "boom"},
        )
        self.assertEqual(
            api_server.make_stopped_event("用户已停止本次运行。"),
            {"type": "stopped", "message": "用户已停止本次运行。"},
        )
        self.assertEqual(api_server.done_event(), "data: [DONE]\n\n")


class FakeChunk:
    def __init__(self, content: str):
        self.content = content


class FakeStreamAgent:
    def __init__(self, events, error: Exception | None = None):
        self.events = events
        self.error = error
        self.payload = None
        self.config = None
        self.version = None

    async def astream_events(self, payload, config=None, version=None):
        self.payload = payload
        self.config = config
        self.version = version
        for event in self.events:
            yield event
        if self.error is not None:
            raise self.error


class FakeAsyncSaverContext:
    def __init__(self, saver):
        self.saver = saver
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.saver

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True


class FailingAsyncSaverContext:
    async def __aenter__(self):
        raise RuntimeError("/private/database/agent_hub.db is locked")

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class SetupFailingHistoryStore:
    def ensure_session(self, *args, **kwargs):
        raise RuntimeError("history setup failed")


class AppendFailingHistoryStore(HistoryStore):
    def append_run_event(self, *args, **kwargs):
        raise RuntimeError("history event append failed")


async def collect_stream(req: api_server.ChatRequest, fake_agent: FakeStreamAgent):
    chunks = []
    async for chunk in api_server.stream_chat_events(req, stream_agent=fake_agent):
        chunks.append(chunk)
    return chunks


async def collect_stream_with_store(
    req: api_server.ChatRequest,
    fake_agent: FakeStreamAgent,
    store: HistoryStore,
):
    chunks = []
    async for chunk in api_server.stream_chat_events(
        req,
        stream_agent=fake_agent,
        store=store,
    ):
        chunks.append(chunk)
    return chunks


def make_temp_store(test_case) -> HistoryStore:
    tmpdir = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmpdir.cleanup)
    store = HistoryStore(Path(tmpdir.name) / "history.db")
    store.initialize()
    return store


def json_chunks(chunks: list[str]) -> list[dict]:
    return [
        parse_sse_payload(chunk)
        for chunk in chunks
        if chunk != api_server.done_event()
    ]


class StreamChatEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_thread_id_is_scoped_by_user_and_session(self):
        user_a_thread = api_server.agent_thread_id("user-a", "shared-session")
        user_b_thread = api_server.agent_thread_id("user-b", "shared-session")
        other_session_thread = api_server.agent_thread_id("user-a", "other-session")

        self.assertTrue(user_a_thread.startswith("thread_"))
        self.assertNotEqual(user_a_thread, user_b_thread)
        self.assertNotEqual(user_a_thread, other_session_thread)

    async def test_stream_chat_events_creates_agent_with_async_sqlite_saver(self):
        store = make_temp_store(self)
        async_saver = object()
        saver_context = FakeAsyncSaverContext(async_saver)
        stream_agent = FakeStreamAgent(
            [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("流式回答")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="async-saver-test",
        )

        with (
            mock.patch.object(
                api_server.AsyncSqliteSaver,
                "from_conn_string",
                return_value=saver_context,
            ) as create_saver,
            mock.patch.object(
                api_server,
                "create_langchain_agent",
                return_value=stream_agent,
            ) as create_agent,
        ):
            chunks = [
                chunk
                async for chunk in api_server.stream_chat_events(req, store=store)
            ]

        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]
        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(
            [payload["type"] for payload in payloads],
            ["stage", "stage", "stage", "text", "stage"],
        )
        self.assertTrue(all(payload["runId"] == run_id for payload in payloads))
        self.assertEqual(payloads[2]["stage"], "answering")
        self.assertEqual(
            payloads[3],
            {"type": "text", "content": "流式回答", "runId": run_id},
        )
        self.assertEqual(payloads[4]["stage"], "completed")
        self.assertFalse(any(payload["type"] == "error" for payload in payloads))
        create_saver.assert_called_once_with(str(api_server.DB_PATH))
        create_agent.assert_called_once_with(
            api_server.llm,
            tools=api_server.tools,
            checkpointer=async_saver,
            system_prompt=api_server.AGENT_SYSTEM_PROMPT,
        )
        self.assertTrue(saver_context.entered)
        self.assertTrue(saver_context.exited)

    async def test_stream_chat_events_emits_stages_tools_text_and_done(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_tool_start",
                    "name": "calculator",
                    "run_id": "calculator-run-1",
                    "data": {"input": {"expression": "2+3"}},
                },
                {
                    "event": "on_tool_end",
                    "name": "calculator",
                    "run_id": "calculator-run-1",
                    "data": {"output": "2+3 = 5"},
                },
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("答案")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="帮我算 2+3",
            user_id="user-stream",
            session_id="session-test",
        )

        chunks = await collect_stream_with_store(req, fake_agent, store)
        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(
            [payload["type"] for payload in payloads],
            [
                "stage",
                "stage",
                "stage",
                "tool_start",
                "tool_end",
                "stage",
                "text",
                "stage",
            ],
        )
        self.assertTrue(all(payload["runId"] == run_id for payload in payloads))
        self.assertEqual(payloads[0]["stage"], "received")
        self.assertEqual(payloads[1]["stage"], "planning")
        self.assertEqual(payloads[2]["stage"], "tooling")
        self.assertEqual(payloads[3]["tool"], "calculator")
        self.assertEqual(payloads[3]["run_id"], "calculator-run-1")
        self.assertEqual(payloads[4]["tool"], "calculator")
        self.assertEqual(payloads[4]["run_id"], "calculator-run-1")
        self.assertIn("elapsed_ms", payloads[4])
        self.assertEqual(payloads[5]["stage"], "answering")
        self.assertEqual(payloads[6]["content"], "答案")
        self.assertEqual(payloads[7]["stage"], "completed")
        self.assertEqual(
            fake_agent.config,
            {
                "configurable": {
                    "thread_id": api_server.agent_thread_id(
                        "user-stream",
                        "session-test",
                    )
                }
            },
        )
        self.assertEqual(fake_agent.version, "v2")

    async def test_parallel_same_name_tools_keep_run_ids_and_timings(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_tool_start",
                    "name": "search",
                    "run_id": "search-run-a",
                    "data": {"input": {"query": "alpha"}},
                },
                {
                    "event": "on_tool_start",
                    "name": "search",
                    "run_id": "search-run-b",
                    "data": {"input": {"query": "beta"}},
                },
                {
                    "event": "on_tool_end",
                    "name": "search",
                    "run_id": "search-run-a",
                    "data": {"output": "alpha result"},
                },
                {
                    "event": "on_tool_end",
                    "name": "search",
                    "run_id": "search-run-b",
                    "data": {"output": "beta result"},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="search",
            user_id="user-stream",
            session_id="parallel-tools",
        )

        with mock.patch.object(
            api_server.time,
            "perf_counter",
            side_effect=[1.0, 2.0, 3.0, 5.0],
        ):
            payloads = json_chunks(
                await collect_stream_with_store(req, fake_agent, store)
            )

        tool_events = [
            payload
            for payload in payloads
            if payload["type"] in {"tool_start", "tool_end"}
        ]
        agent_run_id = payloads[0]["runId"]
        self.assertTrue(all(payload["runId"] == agent_run_id for payload in payloads))
        self.assertEqual(
            [payload["run_id"] for payload in tool_events],
            ["search-run-a", "search-run-b", "search-run-a", "search-run-b"],
        )
        self.assertEqual(
            [payload["elapsed_ms"] for payload in tool_events[2:]],
            [2000, 3000],
        )

    async def test_stream_chat_events_persists_run_messages_and_events(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_tool_start",
                    "name": "calculator",
                    "run_id": "tool-run-1",
                    "data": {"input": {"expression": "2+3"}},
                },
                {
                    "event": "on_tool_end",
                    "name": "calculator",
                    "run_id": "tool-run-1",
                    "data": {"output": "2+3 = 5"},
                },
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("答案")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="帮我算 2+3",
            user_id="user-stream",
            session_id="session-stream",
        )

        payloads = json_chunks(await collect_stream_with_store(req, fake_agent, store))
        run_id = payloads[0]["runId"]
        detail = store.get_run_detail("user-stream", run_id)
        messages = store.list_messages("user-stream", "session-stream")

        self.assertTrue(run_id.startswith("run_"))
        self.assertTrue(all(payload["runId"] == run_id for payload in payloads))
        self.assertEqual(payloads[3]["run_id"], "tool-run-1")
        self.assertEqual([message.role for message in messages], ["user", "agent"])
        self.assertEqual(messages[0].content, "帮我算 2+3")
        self.assertEqual(messages[1].content, "答案")
        self.assertEqual(messages[1].run_id, run_id)
        self.assertEqual(detail.run.status, "completed")
        self.assertEqual(
            [event.sequence for event in detail.events],
            list(range(1, len(detail.events) + 1)),
        )

    async def test_stream_chat_events_emits_safe_error_before_done(self):
        store = make_temp_store(self)
        raw_error = "provider https://secret.example failed for /private/agent_hub.db"
        fake_agent = FakeStreamAgent([], error=RuntimeError(raw_error))
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-error",
        )

        with mock.patch.object(api_server.logger, "exception") as log_exception:
            chunks = await collect_stream_with_store(req, fake_agent, store)
        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(
            payloads[-1],
            {
                "type": "error",
                "message": api_server.STREAM_ERROR_MESSAGE,
                "runId": run_id,
            },
        )
        self.assertNotIn(raw_error, "".join(chunks))
        log_exception.assert_called_once_with("Chat stream failed")

    async def test_stream_chat_events_marks_persisted_run_failed(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent([], error=RuntimeError("provider secret"))
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-error",
        )

        with mock.patch.object(api_server.logger, "exception"):
            payloads = json_chunks(await collect_stream_with_store(req, fake_agent, store))
        run_id = payloads[0]["runId"]
        detail = store.get_run_detail("user-stream", run_id)

        self.assertEqual(payloads[-1]["type"], "error")
        self.assertEqual(detail.run.status, "failed")
        self.assertEqual(detail.run.error_message, api_server.STREAM_ERROR_MESSAGE)

    async def test_stream_chat_events_marks_persisted_run_stopped_when_cancelled(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent([], error=asyncio.CancelledError())
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-cancelled",
        )

        chunks = []
        with self.assertRaises(asyncio.CancelledError):
            async for chunk in api_server.stream_chat_events(
                req,
                stream_agent=fake_agent,
                store=store,
            ):
                chunks.append(chunk)

        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]
        detail = store.get_run_detail("user-stream", run_id)
        messages = store.list_messages("user-stream", "session-cancelled")

        self.assertEqual([payload["type"] for payload in payloads], ["stage", "stage"])
        self.assertEqual(detail.run.status, "stopped")
        self.assertEqual(detail.run.error_message, api_server.STREAM_STOPPED_MESSAGE)
        self.assertEqual([message.role for message in messages], ["user", "agent"])
        self.assertEqual(messages[1].content, api_server.STREAM_STOPPED_ANSWER)
        self.assertEqual(messages[1].run_id, run_id)
        self.assertEqual(detail.run.agent_message_id, messages[1].message_id)
        self.assertEqual(detail.events[-1].event_type, "stopped")
        self.assertEqual(detail.events[-1].payload["type"], "stopped")

    async def test_stream_chat_events_marks_run_stopped_when_iterator_is_closed(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("late answer")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-closed",
        )
        stream = api_server.stream_chat_events(req, stream_agent=fake_agent, store=store)

        first_chunk = await stream.__anext__()
        await stream.aclose()

        run_id = parse_sse_payload(first_chunk)["runId"]
        detail = store.get_run_detail("user-stream", run_id)
        messages = store.list_messages("user-stream", "session-closed")

        self.assertEqual(parse_sse_payload(first_chunk)["type"], "stage")
        self.assertEqual(detail.run.status, "stopped")
        self.assertEqual(detail.run.error_message, api_server.STREAM_STOPPED_MESSAGE)
        self.assertEqual([message.role for message in messages], ["user", "agent"])
        self.assertEqual(messages[1].run_id, run_id)
        self.assertEqual(detail.events[-1].event_type, "stopped")

    async def test_successful_stream_without_text_marks_run_completed(self):
        store = make_temp_store(self)
        fake_agent = FakeStreamAgent([])
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-no-text",
        )

        payloads = json_chunks(await collect_stream_with_store(req, fake_agent, store))
        run_id = payloads[0]["runId"]
        detail = store.get_run_detail("user-stream", run_id)
        messages = store.list_messages("user-stream", "session-no-text")

        self.assertEqual(payloads[-1]["stage"], "completed")
        self.assertEqual(detail.run.status, "completed")
        self.assertEqual([message.role for message in messages], ["user", "agent"])
        self.assertEqual(messages[1].content, "")
        self.assertEqual(messages[1].run_id, run_id)

    async def test_history_setup_failure_does_not_break_stream_contract(self):
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("still answers")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-history-setup-fails",
        )

        with mock.patch.object(api_server.logger, "exception") as log_exception:
            chunks = await collect_stream_with_store(
                req,
                fake_agent,
                SetupFailingHistoryStore(),
            )
        payloads = json_chunks(chunks)

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(payloads[-2]["content"], "still answers")
        self.assertEqual(payloads[-1]["stage"], "completed")
        log_exception.assert_called_once_with("Chat history setup failed")

    async def test_history_event_append_failure_does_not_break_stream_contract(self):
        store = make_temp_store(self)
        append_failing_store = AppendFailingHistoryStore(store.db_path)
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk("answer survives")},
                },
            ]
        )
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="session-append-fails",
        )

        with mock.patch.object(api_server.logger, "exception") as log_exception:
            chunks = await collect_stream_with_store(req, fake_agent, append_failing_store)
        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]
        detail = store.get_run_detail("user-stream", run_id)

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(payloads[-2]["content"], "answer survives")
        self.assertEqual(payloads[-1]["stage"], "completed")
        self.assertEqual(detail.run.status, "completed")
        self.assertEqual(detail.events, [])
        log_exception.assert_any_call("Chat history event persistence failed")

    async def test_received_is_emitted_before_checkpoint_initialization_failure(self):
        store = make_temp_store(self)
        req = api_server.ChatRequest(
            message="hello",
            user_id="user-stream",
            session_id="context-error",
        )

        with (
            mock.patch.object(
                api_server.AsyncSqliteSaver,
                "from_conn_string",
                return_value=FailingAsyncSaverContext(),
            ),
            mock.patch.object(api_server.logger, "exception") as log_exception,
        ):
            chunks = [
                chunk
                async for chunk in api_server.stream_chat_events(req, store=store)
            ]

        payloads = json_chunks(chunks)
        run_id = payloads[0]["runId"]
        self.assertEqual(payloads[0]["stage"], "received")
        self.assertEqual(
            payloads[1],
            {
                "type": "error",
                "message": api_server.STREAM_ERROR_MESSAGE,
                "runId": run_id,
            },
        )
        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertFalse(any(payload.get("stage") == "planning" for payload in payloads))
        self.assertNotIn("agent_hub.db", "".join(chunks))
        log_exception.assert_called_once_with("Chat stream failed")


if __name__ == "__main__":
    unittest.main()
