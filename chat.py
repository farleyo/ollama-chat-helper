#!/usr/bin/env python3
"""Ollama 命令行问答工具

【4 种用法】
    1. 单轮 (流式输出):
        python chat.py "用一句话介绍 Python"

    2. 指定模型 + 角色:
        python chat.py "怎么写 Hello World" --model qwen3:8b --role python-tutor

    3. 多轮交互 (推荐, 体验最好):
        python chat.py --interactive
        python chat.py -i --role english-teacher

    4. 列出可用资源:
        python chat.py --list-models
        python chat.py --list-roles

【交互式特殊命令】
    /quit, /q, /exit    退出
    /reset              清空当前对话历史
    /save               手动保存历史到磁盘
    /role <name>        切换角色 (会重置历史)
    /help, /?           显示帮助
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from ollama_client import (
    DEFAULT_MODEL,
    OllamaClient,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaNotRunningError,
)
from prompts import ROLES, get_system_prompt, list_roles


# ============================================================================
# 历史记录持久化 (~/.ollama_chat/history.json)
# ============================================================================
HISTORY_PATH = Path(
    os.path.expanduser(os.getenv("HISTORY_PATH", "~/.ollama_chat/history.json"))
)


def save_history(messages: list[dict], role: str, model: str) -> None:
    """把对话保存到本地 JSON

    格式:
        {
          "sessions": [
            {"timestamp": "...", "role": "...", "model": "...", "messages": [...]},
            ...
          ]
        }
    """
    if len(messages) <= 1:
        # 只有 system prompt, 没有真实对话, 不存
        return

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 读已有 → 追加 → 写回 (简单但够用; 大量数据时应该用追加模式)
    if HISTORY_PATH.exists():
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"sessions": []}
    else:
        data = {"sessions": []}

    data.setdefault("sessions", []).append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "role": role,
            "model": model,
            "messages": messages,
        }
    )
    HISTORY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================================
# 终端配色 (零依赖, 用 ANSI escape codes)
# ============================================================================
class Color:
    """简单的终端颜色封装 (Windows 现代终端也支持)"""
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def cprint(text: str, color: str = "", end: str = "\n") -> None:
    """带颜色打印 (color="" 即无色)"""
    print(f"{color}{text}{Color.RESET}", end=end)


# ============================================================================
# 单轮模式 (一次性问答)
# ============================================================================
def run_single(
    client: OllamaClient,
    message: str,
    role: str,
    model: str,
    no_stream: bool = False,
) -> int:
    """单轮模式: 接受一条消息, 流式打印回复, 退出

    Returns:
        进程退出码 (0 成功, 1 失败)
    """
    messages = [
        {"role": "system", "content": get_system_prompt(role)},
        {"role": "user", "content": message},
    ]

    cprint(f"🤖 [{ROLES[role]['name']} · {model}]", Color.CYAN)
    cprint("─" * 60, Color.DIM)

    try:
        if no_stream:
            # 非流式 (适合脚本管道)
            reply = client.chat(messages, model=model)
            print(reply)
        else:
            # 流式 (默认, 体验更好)
            full_reply = ""
            for chunk in client.chat_stream(messages, model=model):
                print(chunk, end="", flush=True)
                full_reply += chunk
            print()  # 换行收尾
            messages.append({"role": "assistant", "content": full_reply})

        cprint("─" * 60, Color.DIM)
        # 保存这次单轮对话到历史
        save_history(messages, role, model)
        return 0
    except OllamaError as e:
        cprint(str(e), Color.RED)
        return 1


# ============================================================================
# 交互模式 (多轮对话)
# ============================================================================
INTERACTIVE_HELP = """
可用命令:
  /quit, /q, /exit    退出程序
  /reset              清空当前对话历史
  /save               立即保存历史到磁盘
  /role <name>        切换角色 (会重置历史) 例: /role python-tutor
  /roles              列出所有角色
  /model <name>       切换模型 例: /model deepseek-r1:8b
  /help, /?           显示本帮助

直接输入文字即可开始对话.
"""


def run_interactive(
    client: OllamaClient,
    role: str,
    model: str,
    no_stream: bool = False,
) -> int:
    """交互模式: 多轮对话循环, 直到用户退出"""
    messages: list[dict] = [
        {"role": "system", "content": get_system_prompt(role)}
    ]

    cprint("=" * 60, Color.CYAN)
    cprint(
        f"🤖 ollama-chat-helper · 交互模式",
        Color.BOLD + Color.CYAN,
    )
    cprint(f"   角色: {ROLES[role]['name']}  |  模型: {model}", Color.CYAN)
    cprint(f"   输入 /help 看命令, /quit 退出", Color.DIM)
    cprint("=" * 60, Color.CYAN)

    while True:
        try:
            user_input = input(f"\n{Color.GREEN}你 > {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D / Ctrl+C 优雅退出
            cprint("\n👋 已退出, 历史已保存", Color.YELLOW)
            save_history(messages, role, model)
            return 0

        if not user_input:
            continue

        # ---- 处理命令 ----
        if user_input.startswith("/"):
            action = _handle_command(user_input, messages, role, model)
            if action == "quit":
                save_history(messages, role, model)
                return 0
            if isinstance(action, tuple):
                # ('role', new_role) 或 ('model', new_model)
                key, value = action
                if key == "role":
                    role = value
                    # 切换角色 → 重置 messages (新 system prompt)
                    messages = [
                        {"role": "system", "content": get_system_prompt(role)}
                    ]
                    cprint(f"✓ 已切换角色: {ROLES[role]['name']} (历史已重置)",
                           Color.YELLOW)
                elif key == "model":
                    model = value
                    cprint(f"✓ 已切换模型: {model}", Color.YELLOW)
            elif action == "reset":
                messages = [
                    {"role": "system", "content": get_system_prompt(role)}
                ]
                cprint("✓ 已清空对话历史", Color.YELLOW)
            elif action == "save":
                save_history(messages, role, model)
                cprint(f"✓ 已保存到 {HISTORY_PATH}", Color.YELLOW)
            continue

        # ---- 普通对话 ----
        messages.append({"role": "user", "content": user_input})
        cprint(f"\n{Color.BLUE}AI > {Color.RESET}", end="")

        try:
            full_reply = ""
            if no_stream:
                full_reply = client.chat(messages, model=model)
                print(full_reply)
            else:
                for chunk in client.chat_stream(messages, model=model):
                    print(chunk, end="", flush=True)
                    full_reply += chunk
                print()  # 换行
            messages.append({"role": "assistant", "content": full_reply})
        except OllamaError as e:
            cprint(f"\n{e}", Color.RED)
            # 错误时回滚最后一条 user, 让用户重试
            messages.pop()
        except KeyboardInterrupt:
            cprint("\n⚠ 已中断当前回复", Color.YELLOW)
            messages.pop()  # 回滚


def _handle_command(
    cmd: str,
    messages: list[dict],
    role: str,
    model: str,
):
    """处理交互模式的 / 命令

    Returns:
        'quit' / 'reset' / 'save' / ('role', name) / ('model', name) / None
    """
    parts = cmd.split(maxsplit=1)
    op = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if op in ("/quit", "/q", "/exit"):
        cprint("👋 已退出", Color.YELLOW)
        return "quit"

    if op in ("/help", "/?"):
        cprint(INTERACTIVE_HELP, Color.CYAN)
        return None

    if op == "/reset":
        return "reset"

    if op == "/save":
        return "save"

    if op == "/roles":
        cprint("\n可用角色:", Color.CYAN)
        for r in list_roles():
            cprint(f"  {r['key']:<20} - {r['description']}", Color.DIM)
        return None

    if op == "/role":
        if not arg:
            cprint("❌ 用法: /role <name>, 例: /role python-tutor", Color.RED)
            return None
        if arg not in ROLES:
            cprint(f"❌ 未知角色 '{arg}'. 可用: {', '.join(ROLES.keys())}",
                   Color.RED)
            return None
        return ("role", arg)

    if op == "/model":
        if not arg:
            cprint("❌ 用法: /model <name>, 例: /model deepseek-r1:8b",
                   Color.RED)
            return None
        return ("model", arg)

    cprint(f"❌ 未知命令 '{op}'. 输入 /help 看可用命令.", Color.RED)
    return None


# ============================================================================
# 命令行参数解析
# ============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chat.py",
        description="本地 Ollama AI 助手 (CLI 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python chat.py \"你好\"\n"
            "  python chat.py \"翻译 hello\" --role english-teacher\n"
            "  python chat.py -i --role python-tutor\n"
        ),
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="要问的问题 (单轮模式必填; 交互模式不需要)",
    )
    parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"模型名 (默认: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "-r", "--role",
        default="general",
        choices=list(ROLES.keys()),
        help="角色预设 (默认: general)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="进入交互式多轮对话模式",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="关闭流式输出 (一次性返回完整回复)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="列出本地已安装的 Ollama 模型",
    )
    parser.add_argument(
        "--list-roles",
        action="store_true",
        help="列出所有可用角色预设",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    # ---- 列表型命令 (不需要 Ollama 连接) ----
    if args.list_roles:
        cprint("可用角色:", Color.CYAN + Color.BOLD)
        for r in list_roles():
            cprint(f"  {r['key']:<20}", Color.GREEN, end="")
            cprint(f"{r['name']}: {r['description']}", Color.DIM)
        return 0

    # ---- 创建客户端 + 健康检查 ----
    client = OllamaClient()
    if not client.is_alive():
        cprint("❌ Ollama 服务未运行", Color.RED + Color.BOLD)
        cprint(f"   服务地址: {client.base_url}", Color.DIM)
        cprint("   解决方法: 在另一个终端运行 'ollama serve'", Color.YELLOW)
        return 1

    # ---- list-models (需要连接) ----
    if args.list_models:
        try:
            models = client.list_models()
        except OllamaError as e:
            cprint(str(e), Color.RED)
            return 1
        cprint(f"本地已安装 {len(models)} 个模型:", Color.CYAN + Color.BOLD)
        for m in models:
            marker = " ⭐" if m == DEFAULT_MODEL else ""
            cprint(f"  {m}{marker}", Color.GREEN)
        return 0

    # ---- 验证模型存在 (避免请求失败再报错) ----
    try:
        installed = client.list_models()
        if args.model not in installed:
            cprint(f"❌ 模型 '{args.model}' 未安装", Color.RED)
            cprint(f"   已安装: {', '.join(installed[:8])}", Color.DIM)
            cprint(f"   下载: ollama pull {args.model}", Color.YELLOW)
            return 1
    except OllamaNotRunningError as e:
        cprint(str(e), Color.RED)
        return 1

    # ---- 分发到对应模式 ----
    if args.interactive:
        return run_interactive(
            client, role=args.role, model=args.model, no_stream=args.no_stream
        )

    if not args.message:
        cprint("❌ 单轮模式需要传入问题. 例:", Color.RED)
        cprint("   python chat.py \"你好\"", Color.YELLOW)
        cprint("   python chat.py -i        (进入交互模式)", Color.YELLOW)
        return 1

    return run_single(
        client,
        message=args.message,
        role=args.role,
        model=args.model,
        no_stream=args.no_stream,
    )


if __name__ == "__main__":
    sys.exit(main())
