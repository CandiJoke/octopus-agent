import json
import os
import unittest

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

        start_event = api_server.make_tool_start_event("calculator", input_payload)
        end_event = api_server.make_tool_end_event(
            "calculator",
            output_payload,
            elapsed_ms=42,
        )

        self.assertEqual(start_event["type"], "tool_start")
        self.assertEqual(start_event["tool"], "calculator")
        self.assertLessEqual(len(start_event["input"]), api_server.STREAM_INPUT_LIMIT)
        self.assertEqual(end_event["type"], "tool_end")
        self.assertEqual(end_event["tool"], "calculator")
        self.assertEqual(end_event["elapsed_ms"], 42)
        self.assertLessEqual(len(end_event["output"]), api_server.STREAM_OUTPUT_LIMIT)

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
    async def test_stream_chat_events_emits_stages_tools_text_and_done(self):
        fake_agent = FakeStreamAgent(
            [
                {
                    "event": "on_tool_start",
                    "name": "calculator",
                    "data": {"input": {"expression": "2+3"}},
                },
                {
                    "event": "on_tool_end",
                    "name": "calculator",
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
        self.assertEqual(payloads[4]["tool"], "calculator")
        self.assertIn("elapsed_ms", payloads[4])
        self.assertEqual(payloads[5]["stage"], "answering")
        self.assertEqual(payloads[6]["content"], "答案")
        self.assertEqual(payloads[7]["stage"], "completed")
        self.assertEqual(
            fake_agent.config,
            {"configurable": {"thread_id": "session-test"}},
        )
        self.assertEqual(fake_agent.version, "v2")

    async def test_stream_chat_events_emits_error_event_before_done(self):
        fake_agent = FakeStreamAgent([], error=RuntimeError("model exploded"))
        req = api_server.ChatRequest(message="hello", session_id="session-error")

        chunks = await collect_stream(req, fake_agent)
        payloads = json_chunks(chunks)

        self.assertEqual(chunks[-1], api_server.done_event())
        self.assertEqual(payloads[-1], {"type": "error", "message": "model exploded"})


if __name__ == "__main__":
    unittest.main()
