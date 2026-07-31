"""
Agent Console：带工具调用和会话记忆的交互式命令行入口。
"""

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import openai
from dotenv import load_dotenv
from langchain.agents import create_agent as create_langchain_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from tools import tools

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_THREAD_ID = "default"
DEFAULT_ENV_FILE = Path(__file__).with_name(".env")
checkpointer = InMemorySaver()


def load_app_env(env_path: str | Path = DEFAULT_ENV_FILE) -> bool:
    """读取 .env 配置；已导出的 shell 环境变量优先级更高。"""
    return load_dotenv(env_path, override=False)


load_app_env()


# ========== 配置 ==========

# 这里需要你的 OpenAI API Key
# 方式1：环境变量 export OPENAI_API_KEY="sk-xxx"
# 方式2：直接传入 api_key 参数

def selected_model() -> str:
    """读取当前要调用的模型。"""
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def selected_thread_id() -> str:
    """读取当前对话线程 ID；同一个 ID 会共享 Checkpointer 记忆。"""
    return os.getenv("AGENT_THREAD_ID", DEFAULT_THREAD_ID)


def selected_base_url() -> tuple[str | None, str | None]:
    """返回 LangChain/OpenAI SDK 实际会优先使用的 base URL 环境变量。"""
    if os.getenv("OPENAI_API_BASE"):
        return "OPENAI_API_BASE", os.getenv("OPENAI_API_BASE")
    if os.getenv("OPENAI_BASE_URL"):
        return "OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL")
    return None, None


def selected_base_url_value() -> str | None:
    """读取实际传给 ChatOpenAI 的 base_url。"""
    _, base_url = selected_base_url()
    return base_url


def redact_url(url: str | None) -> str:
    """隐藏 URL 里的用户名/密码，避免诊断信息泄露凭据。"""
    if not url:
        return "未设置，使用 OpenAI 官方默认地址"
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<已设置，但 URL 格式无法解析>"

    if not parts.username and not parts.password:
        return url

    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def openai_diagnostics() -> list[str]:
    """生成不会泄露 API key 的 OpenAI 配置诊断信息。"""
    base_url_name, base_url = selected_base_url()
    base_url_label = base_url_name or "OPENAI_API_BASE / OPENAI_BASE_URL"
    return [
        f"模型: {selected_model()}（可用 OPENAI_MODEL 覆盖）",
        f"OPENAI_API_KEY: {'已设置' if os.getenv('OPENAI_API_KEY') else '未设置'}",
        f"{base_url_label}: {redact_url(base_url)}",
    ]


def check_openai_setup() -> tuple[bool, str]:
    """运行前检查必需配置，避免直接抛 SDK 栈。"""
    if os.getenv("OPENAI_API_KEY"):
        return True, ""

    return (
        False,
        "\n".join(
            [
                "❌ 缺少 OPENAI_API_KEY。",
                "",
                "先在当前终端设置你的 OpenAI API key：",
                '  export OPENAI_API_KEY="sk-..."',
                "",
                "然后重新运行：",
                "  python3 agent_console.py",
            ]
        ),
    )


def not_found_help(error_text: str) -> str:
    """解释 OpenAI 404，并给出最短排查路径。"""
    diagnostics = "\n".join(f"  - {line}" for line in openai_diagnostics())
    return "\n".join(
        [
            "❌ OpenAI 返回 404 NotFoundError。",
            f"原始信息: {error_text}",
            "",
            "最常见原因：",
            f"1. 当前 API key 所属项目没有模型 `{selected_model()}` 的权限，或模型名不在该项目可用列表。",
            "2. OPENAI_API_BASE / OPENAI_BASE_URL 指到了代理或第三方地址，但该地址不支持当前模型或 endpoint。",
            "",
            "当前配置诊断：",
            diagnostics,
            "",
            "如果你想直连 OpenAI 官方 API，可以先取消自定义 base URL 后重试：",
            "  unset OPENAI_API_BASE OPENAI_BASE_URL",
            "  python3 agent_console.py",
            "",
            "如果你必须使用代理/第三方兼容接口，请把 OPENAI_MODEL 改成那个服务实际支持的模型名。",
        ]
    )


# ========== Agent 构建 ==========


def create_agent():
    llm = ChatOpenAI(
        model=selected_model(),
        temperature=0,          # 温度0 = 最稳定输出
        base_url=selected_base_url_value(),
        # api_key="sk-xxx"      # 或直接放这里（不推荐，容易泄露）
    )
    # 创建 ReAct Agent（Reasoning + Acting）
    # ReAct = 先思考 → 再行动（调工具）→ 观察结果 → 再思考 → 最终回答
    return create_langchain_agent(llm, tools=tools, checkpointer=checkpointer)


# ========== 交互式运行 ==========

def ask_agent(question: str, agent=None, thread_id: str | None = None):
    """向 Agent 提问，打印完整思考过程"""
    if agent is None:
        agent = create_agent()
    if thread_id is None:
        thread_id = selected_thread_id()

    print(f"\n{'='*60}")
    print(f"👤 用户: {question}")
    print(f"{'='*60}")

    # agent.invoke() 返回一个字典，messages 包含完整对话
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({"messages": [("user", question)]}, config=config)

    # 打印每一步（包括工具调用）
    for msg in result["messages"]:
        role = type(msg).__name__
        if role == "HumanMessage":
            pass  # 用户消息已打印
        elif role == "AIMessage":
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"🤔 Agent 决定: 调用 {tc['name']}({tc['args']})")
            if msg.content:
                print(f"🤖 Agent: {msg.content}")
        elif role == "ToolMessage":
            preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"🔧 工具返回: {preview}")

    # 最终回答
    final = result["messages"][-1].content
    print(f"\n✅ 最终答案: {final}")
    return final


# ========== CLI 入口 ==========
def main() -> int:
    print("🚀 Agent Hub 启动！\n")

    ok, message = check_openai_setup()
    if not ok:
        print(message)
        return 1

    print("当前 OpenAI 配置：")
    for line in openai_diagnostics():
        print(f"  - {line}")

    agent = create_agent()
    thread_id = selected_thread_id()

    print(f"💡 输入问题开始对话，输入 quit 退出（thread_id: {thread_id}）\n")
    try:
        while True:
            try:
                question = input("👤 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见！")
                break
            if not question:
                continue
            if question.lower() in ("quit", "exit", "q"):
                print("👋 再见！")
                break
            ask_agent(question, agent, thread_id=thread_id)
    except openai.NotFoundError as e:
        print(not_found_help(str(e)))
        return 1
    except openai.AuthenticationError as e:
        print("❌ OpenAI 认证失败，请检查 OPENAI_API_KEY 是否正确。")
        print(f"原始信息: {e}")
        return 1
    except openai.RateLimitError as e:
        print("❌ OpenAI 调用被限流或额度不足，请检查账户额度、速率限制或项目 spend limit。")
        print(f"原始信息: {e}")
        return 1
    except openai.OpenAIError as e:
        print("❌ OpenAI 调用失败。")
        print(f"原始信息: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
