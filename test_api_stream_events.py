import json
import os
import unittest
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import api_server


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


async def collect_stream(req: api_server.ChatRequest, fake_agent: FakeStreamAgent):
    chunks = []
    async for chunk in api_server.stream_chat_events(req, stream_agent=fake_agent):
        chunks.append(chunk)
    return chunks


def json_chunks(chunks: list[str]) -> list[dict]:
    return [
        parse_sse_payload(chunk)
        for chunk in chunks
        if chunk != api_server.done_event()
    ]


class StreamChatEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_chat_events_creates_agent_with_async_sqlite_saver(self):
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
        req = api_server.ChatRequest(message="hello", session_id="async-saver-test")

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
            chunks = [chunk async for chunk in api_server.stream_chat_events(req)]

        payloads = json_chunks(chunks)
        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(
            [payload["type"] for payload in payloads],
            ["stage", "stage", "stage", "text", "stage"],
        )
        self.assertEqual(payloads[2]["stage"], "answering")
        self.assertEqual(payloads[3], {"type": "text", "content": "流式回答"})
        self.assertEqual(payloads[4]["stage"], "completed")
        self.assertFalse(any(payload["type"] == "error" for payload in payloads))
        create_saver.assert_called_once_with(str(api_server.DB_PATH))
        create_agent.assert_called_once_with(
            api_server.llm,
            tools=api_server.tools,
            checkpointer=async_saver,
        )
        self.assertTrue(saver_context.entered)
        self.assertTrue(saver_context.exited)

    async def test_stream_chat_events_emits_stages_tools_text_and_done(self):
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
        req = api_server.ChatRequest(message="帮我算 2+3", session_id="session-test")

        chunks = await collect_stream(req, fake_agent)
        payloads = json_chunks(chunks)

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
            {"configurable": {"thread_id": "session-test"}},
        )
        self.assertEqual(fake_agent.version, "v2")

    async def test_parallel_same_name_tools_keep_run_ids_and_timings(self):
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
        req = api_server.ChatRequest(message="search", session_id="parallel-tools")

        with mock.patch.object(
            api_server.time,
            "perf_counter",
            side_effect=[1.0, 2.0, 3.0, 5.0],
        ):
            payloads = json_chunks(await collect_stream(req, fake_agent))

        tool_events = [
            payload
            for payload in payloads
            if payload["type"] in {"tool_start", "tool_end"}
        ]
        self.assertEqual(
            [payload["run_id"] for payload in tool_events],
            ["search-run-a", "search-run-b", "search-run-a", "search-run-b"],
        )
        self.assertEqual(
            [payload["elapsed_ms"] for payload in tool_events[2:]],
            [2000, 3000],
        )

    async def test_stream_chat_events_emits_safe_error_before_done(self):
        raw_error = "provider https://secret.example failed for /private/agent_hub.db"
        fake_agent = FakeStreamAgent([], error=RuntimeError(raw_error))
        req = api_server.ChatRequest(message="hello", session_id="session-error")

        with mock.patch.object(api_server.logger, "exception") as log_exception:
            chunks = await collect_stream(req, fake_agent)
        payloads = json_chunks(chunks)

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(
            payloads[-1],
            {"type": "error", "message": api_server.STREAM_ERROR_MESSAGE},
        )
        self.assertNotIn(raw_error, "".join(chunks))
        log_exception.assert_called_once_with("Chat stream failed")

    async def test_received_is_emitted_before_checkpoint_initialization_failure(self):
        req = api_server.ChatRequest(message="hello", session_id="context-error")

        with (
            mock.patch.object(
                api_server.AsyncSqliteSaver,
                "from_conn_string",
                return_value=FailingAsyncSaverContext(),
            ),
            mock.patch.object(api_server.logger, "exception") as log_exception,
        ):
            chunks = [chunk async for chunk in api_server.stream_chat_events(req)]

        payloads = json_chunks(chunks)
        self.assertEqual(payloads[0]["stage"], "received")
        self.assertEqual(
            payloads[1],
            {"type": "error", "message": api_server.STREAM_ERROR_MESSAGE},
        )
        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertFalse(any(payload.get("stage") == "planning" for payload in payloads))
        self.assertNotIn("agent_hub.db", "".join(chunks))
        log_exception.assert_called_once_with("Chat stream failed")


if __name__ == "__main__":
    unittest.main()
