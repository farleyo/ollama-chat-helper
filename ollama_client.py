"""Ollama HTTP API 客户端封装

【封装目的】
1. 把 Ollama REST 细节藏起来 (URL / JSON schema / 流式解析)
2. 统一中文错误处理 (服务未启动 / 模型不存在 / 超时)
3. CLI 和 Streamlit 都能复用 (DRY)

【Ollama API 参考】
官方文档: https://github.com/ollama/ollama/blob/main/docs/api.md

主要端点:
    GET  /api/tags          列出已安装模型
    POST /api/chat          多轮对话 (本文件主要用这个)
    POST /api/generate      单轮生成 (旧 API, 不用)
    POST /api/pull          下载模型

/api/chat 请求格式:
    {
        "model": "qwen3:8b",
        "messages": [
            {"role": "system", "content": "你是助手"},
            {"role": "user",   "content": "你好"}
        ],
        "stream": true              # 流式输出
    }

流式响应 (每行一个 JSON):
    {"message": {"role": "assistant", "content": "你"}, "done": false}
    {"message": {"role": "assistant", "content": "好"}, "done": false}
    {"message": {"role": "assistant", "content": ""}, "done": true, ...统计字段}
"""
from __future__ import annotations

import json
import os
from typing import Generator, Iterable

import requests

# python-dotenv 是可选依赖, 没装也能跑 (用环境变量/默认值兜底)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 用户没 pip install python-dotenv, 静默跳过
    pass


# ============================================================================
# 默认配置 (从 .env 或环境变量读, 都没有用硬编码默认值)
# ============================================================================
DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3:8b")
DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))


# ============================================================================
# 自定义异常 (让调用方可以分类捕获 + 给用户友好提示)
# ============================================================================
class OllamaError(Exception):
    """Ollama 相关错误的基类"""


class OllamaNotRunningError(OllamaError):
    """Ollama 服务未启动 (11434 端口连不上)"""


class OllamaModelNotFoundError(OllamaError):
    """模型不存在 (本地没 pull)"""


class OllamaTimeoutError(OllamaError):
    """请求超时"""


# ============================================================================
# 客户端类 (有状态: base_url + 默认模型 + 超时)
# ============================================================================
class OllamaClient:
    """Ollama API 客户端

    用法:
        client = OllamaClient()
        if not client.is_alive():
            print("请先启动 ollama serve")
            return
        # 单轮 (一次性返回)
        reply = client.chat([{"role": "user", "content": "你好"}])
        # 流式 (字符增量)
        for chunk in client.chat_stream([{"role": "user", "content": "你好"}]):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        # rstrip 防用户配 'http://localhost:11434/' 带尾斜杠
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    # ------------------------------------------------------------------------
    # 健康检查 + 模型列表
    # ------------------------------------------------------------------------
    def is_alive(self) -> bool:
        """检查 Ollama 服务是否运行中

        快速 ping /api/tags (3 秒超时, 不用全局 timeout 防卡住).

        Returns:
            True: 服务正常
            False: 任何异常 (端口不通 / DNS 错 / 服务挂了)
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            # 包括 ConnectionError / Timeout / 其他网络问题
            return False

    def list_models(self) -> list[str]:
        """获取本地已安装的模型名列表

        Returns:
            ['qwen3:8b', 'deepseek-r1:8b', ...]

        Raises:
            OllamaNotRunningError: 服务未启动
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            # 响应格式: {"models": [{"name": "qwen3:8b", ...}, ...]}
            return [m["name"] for m in data.get("models", [])]
        except requests.ConnectionError:
            raise OllamaNotRunningError(
                f"❌ 无法连接 Ollama 服务 ({self.base_url})\n"
                f"   请先启动: ollama serve"
            )
        except requests.RequestException as e:
            raise OllamaError(f"❌ 调用 /api/tags 失败: {e}")

    # ------------------------------------------------------------------------
    # 对话 (单次 + 流式)
    # ------------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        """单次对话 (一次性返回完整回复, 不流式)

        适合: 简单脚本 / 测试 / 不需要实时反馈的场景

        Args:
            messages: ChatML 消息列表 [{"role": "user", "content": "..."}, ...]
            model:    模型名, 默认用 self.default_model

        Returns:
            助手的回复字符串

        Raises:
            OllamaNotRunningError / OllamaModelNotFoundError / OllamaTimeoutError
        """
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,           # 一次性返回
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
        except requests.ConnectionError:
            raise OllamaNotRunningError(
                f"❌ 无法连接 Ollama 服务 ({self.base_url})\n"
                f"   请先启动: ollama serve"
            )
        except requests.Timeout:
            raise OllamaTimeoutError(
                f"❌ 请求超时 ({self.timeout}s). "
                f"大模型首次加载较慢, 可调大 OLLAMA_TIMEOUT 重试"
            )

        # 处理 HTTP 错误码
        self._check_response(resp, model)

        data = resp.json()
        # 响应格式: {"message": {"role": "assistant", "content": "..."}, "done": true, ...}
        return data["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> Generator[str, None, None]:
        """流式对话 (字符增量返回)

        适合: CLI 实时打印 / Streamlit st.write_stream

        Args:
            messages: ChatML 消息列表
            model:    模型名

        Yields:
            每次产出一个文本片段 (单字 / 多字, 取决于模型分词)

        Example:
            for chunk in client.chat_stream(msgs):
                print(chunk, end="", flush=True)
        """
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,            # 流式
        }
        try:
            # stream=True: requests 不一次性下完, 让我们能逐行处理
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
        except requests.ConnectionError:
            raise OllamaNotRunningError(
                f"❌ 无法连接 Ollama 服务 ({self.base_url})\n"
                f"   请先启动: ollama serve"
            )
        except requests.Timeout:
            raise OllamaTimeoutError(
                f"❌ 连接 Ollama 超时. 请检查服务状态."
            )

        self._check_response(resp, model)

        # 流式响应: 服务端每输出一段就推一行 JSON
        # iter_lines: 按 \n 切分, 解码 utf-8
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # 偶尔出现部分 chunk, 跳过
                    continue
                # 关键路径: obj.message.content 是新增的文本片段
                msg = obj.get("message") or {}
                chunk = msg.get("content", "")
                if chunk:
                    yield chunk
                # done=true 表示流结束 (附带 token 统计, 这里不用)
                if obj.get("done"):
                    break
        except requests.exceptions.ChunkedEncodingError:
            # 服务端中途断流, 已经 yield 的部分用户能看到, 这里温和结束
            return

    # ------------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------------
    def _check_response(self, resp: requests.Response, model: str) -> None:
        """统一检查 HTTP 响应状态码, 转成中文异常

        Ollama 错误响应示例:
            404: {"error": "model 'xxx' not found, try pulling it first"}
            500: {"error": "..."}
        """
        if resp.status_code == 200:
            return
        # 尝试解析错误体
        try:
            err_msg = resp.json().get("error", resp.text)
        except json.JSONDecodeError:
            err_msg = resp.text

        if resp.status_code == 404 or "not found" in err_msg.lower():
            # 列出可用模型给用户看
            try:
                available = ", ".join(self.list_models()[:10])
            except Exception:
                available = "(获取失败)"
            raise OllamaModelNotFoundError(
                f"❌ 模型 '{model}' 不存在\n"
                f"   可用模型: {available}\n"
                f"   下载新模型: ollama pull {model}"
            )

        raise OllamaError(
            f"❌ Ollama API 错误 (HTTP {resp.status_code}): {err_msg}"
        )


# ============================================================================
# 快捷函数 (无需创建实例直接用)
# ============================================================================
def quick_chat(message: str, model: str | None = None) -> str:
    """一行调用: 单条用户消息 → 助手回复

    Example:
        from ollama_client import quick_chat
        reply = quick_chat("你好")
    """
    client = OllamaClient()
    return client.chat([{"role": "user", "content": message}], model=model)
