import contextlib
import io
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import agent_console


class AgentConsoleConfigTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_check_openai_setup_requires_api_key(self):
        ok, message = agent_console.check_openai_setup()

        self.assertFalse(ok)
        self.assertIn("OPENAI_API_KEY", message)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_selected_model_defaults_to_config_default(self):
        self.assertEqual(agent_console.selected_model(), agent_console.DEFAULT_MODEL)

    @patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test"},
        clear=True,
    )
    def test_selected_model_can_be_overridden(self):
        self.assertEqual(agent_console.selected_model(), "gpt-test")

    @patch.dict(os.environ, {}, clear=True)
    def test_load_app_env_reads_openai_config_from_env_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=sk-from-env-file",
                        "OPENAI_BASE_URL=https://example.com/v1",
                        "OPENAI_MODEL=gpt-from-env-file",
                        "AGENT_THREAD_ID=thread-from-env-file",
                    ]
                ),
                encoding="utf-8",
            )

            loaded = agent_console.load_app_env(env_file)

        self.assertTrue(loaded)
        self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-from-env-file")
        self.assertEqual(agent_console.selected_base_url(), ("OPENAI_BASE_URL", "https://example.com/v1"))
        self.assertEqual(agent_console.selected_model(), "gpt-from-env-file")
        self.assertEqual(agent_console.selected_thread_id(), "thread-from-env-file")

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-from-shell",
            "OPENAI_BASE_URL": "https://shell.example/v1",
        },
        clear=True,
    )
    def test_load_app_env_does_not_override_shell_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=sk-from-file",
                        "OPENAI_BASE_URL=https://file.example/v1",
                    ]
                ),
                encoding="utf-8",
            )

            agent_console.load_app_env(env_file)

        self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-from-shell")
        self.assertEqual(agent_console.selected_base_url(), ("OPENAI_BASE_URL", "https://shell.example/v1"))

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-test",
            "OPENAI_BASE_URL": "https://user:pass@example.com/v1",
        },
        clear=True,
    )
    def test_not_found_help_includes_safe_diagnostics(self):
        text = agent_console.not_found_help("404 from api")

        self.assertIn("404", text)
        self.assertIn("gpt-test", text)
        self.assertIn("OPENAI_MODEL", text)
        self.assertIn("OPENAI_BASE_URL", text)
        self.assertNotIn("user:pass", text)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_create_agent_does_not_emit_deprecation_warnings(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", Warning)
            agent = agent_console.create_agent()

        self.assertEqual(type(agent).__name__, "CompiledStateGraph")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_create_agent_uses_checkpointer(self):
        with patch.object(agent_console, "create_langchain_agent", return_value="agent") as create:
            agent = agent_console.create_agent()

        self.assertEqual(agent, "agent")
        self.assertIn("checkpointer", create.call_args.kwargs)
        self.assertIs(create.call_args.kwargs["checkpointer"], agent_console.checkpointer)
        self.assertIn("system_prompt", create.call_args.kwargs)
        self.assertIn("Math Problem Solver", create.call_args.kwargs["system_prompt"])

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://example.com/v1",
        },
        clear=True,
    )
    def test_create_agent_passes_base_url_to_chat_openai(self):
        with (
            patch.object(agent_console, "ChatOpenAI", return_value="llm") as chat_openai,
            patch.object(agent_console, "create_langchain_agent", return_value="agent"),
        ):
            agent_console.create_agent()

        self.assertEqual(chat_openai.call_args.kwargs["base_url"], "https://example.com/v1")

    @patch.dict(os.environ, {"AGENT_THREAD_ID": "lesson-thread"}, clear=True)
    def test_ask_agent_invokes_with_thread_id(self):
        class AIMessage:
            tool_calls = []
            content = "ok"

        class FakeAgent:
            def __init__(self):
                self.config = None

            def invoke(self, payload, config=None):
                self.config = config
                return {"messages": [AIMessage()]}

        agent = FakeAgent()

        with contextlib.redirect_stdout(io.StringIO()):
            agent_console.ask_agent("hello", agent)

        self.assertEqual(
            agent.config,
            {"configurable": {"thread_id": "lesson-thread"}},
        )


if __name__ == "__main__":
    unittest.main()
