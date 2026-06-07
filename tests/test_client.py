"""ollama_client 最小测试套件

用法:
    pytest tests/                 # 跑全部
    pytest tests/ -v              # 详细输出
    pytest tests/ -k healthcheck  # 跑特定测试

【测试策略】
不真连 Ollama (CI 环境通常没装), 用 unittest.mock 伪造响应.
真实集成测试由用户手跑 `python chat.py "你好"` 完成.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# 让 pytest 能找到上级目录的模块 (chat.py / ollama_client.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from ollama_client import (  # noqa: E402
    OllamaClient,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaNotRunningError,
)


# ============================================================================
# 健康检查
# ============================================================================
class TestHealthcheck:
    """is_alive() 测试"""

    @patch("ollama_client.requests.get")
    def test_alive_when_ollama_running(self, mock_get):
        """Ollama 正常: GET /api/tags 返回 200 → True"""
        mock_get.return_value = MagicMock(status_code=200)
        client = OllamaClient()
        assert client.is_alive() is True

    @patch("ollama_client.requests.get")
    def test_dead_when_connection_refused(self, mock_get):
        """Ollama 没启动: 连接被拒 → False (不抛异常)"""
        mock_get.side_effect = requests.ConnectionError()
        client = OllamaClient()
        assert client.is_alive() is False

    @patch("ollama_client.requests.get")
    def test_dead_when_timeout(self, mock_get):
        """Ollama 卡住: 超时 → False"""
        mock_get.side_effect = requests.Timeout()
        client = OllamaClient()
        assert client.is_alive() is False


# ============================================================================
# 模型列表
# ============================================================================
class TestListModels:
    @patch("ollama_client.requests.get")
    def test_list_models_returns_names(self, mock_get):
        """正常情况: 返回模型名字列表"""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen3:8b", "size": 5200000000},
                {"name": "deepseek-r1:8b", "size": 4900000000},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = OllamaClient()
        models = client.list_models()
        assert models == ["qwen3:8b", "deepseek-r1:8b"]

    @patch("ollama_client.requests.get")
    def test_list_models_raises_when_offline(self, mock_get):
        """Ollama 不在: 抛 OllamaNotRunningError"""
        mock_get.side_effect = requests.ConnectionError()
        client = OllamaClient()
        with pytest.raises(OllamaNotRunningError):
            client.list_models()


# ============================================================================
# 单次对话 chat()
# ============================================================================
class TestChat:
    @patch("ollama_client.requests.post")
    def test_chat_returns_reply(self, mock_post):
        """正常对话: 拿到 message.content 字符串"""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "你好!"},
            "done": True,
        }
        mock_post.return_value = mock_resp

        client = OllamaClient()
        reply = client.chat([{"role": "user", "content": "hi"}])
        assert reply == "你好!"

    @patch("ollama_client.requests.get")
    @patch("ollama_client.requests.post")
    def test_chat_raises_model_not_found(self, mock_post, mock_get):
        """模型不存在: 抛 OllamaModelNotFoundError"""
        # /api/chat 返回 404
        mock_chat_resp = MagicMock(status_code=404, text="model not found")
        mock_chat_resp.json.return_value = {
            "error": "model 'unknown' not found"
        }
        mock_post.return_value = mock_chat_resp
        # /api/tags 返回空 (异常处理里会再调一次)
        mock_tags_resp = MagicMock(status_code=200)
        mock_tags_resp.json.return_value = {"models": []}
        mock_tags_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_tags_resp

        client = OllamaClient()
        with pytest.raises(OllamaModelNotFoundError) as exc:
            client.chat(
                [{"role": "user", "content": "x"}], model="unknown"
            )
        # 错误消息应该含模型名
        assert "unknown" in str(exc.value)

    @patch("ollama_client.requests.post")
    def test_chat_raises_not_running(self, mock_post):
        """Ollama 不在: 抛 OllamaNotRunningError"""
        mock_post.side_effect = requests.ConnectionError()
        client = OllamaClient()
        with pytest.raises(OllamaNotRunningError):
            client.chat([{"role": "user", "content": "x"}])


# ============================================================================
# 流式对话 chat_stream()
# ============================================================================
class TestChatStream:
    @patch("ollama_client.requests.post")
    def test_stream_yields_chunks(self, mock_post):
        """流式: 逐行 JSON, 累积成完整回复"""
        # 模拟 Ollama 流式响应 (3 个 chunk)
        lines = [
            json.dumps({"message": {"content": "你"}, "done": False}),
            json.dumps({"message": {"content": "好"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]
        mock_resp = MagicMock(status_code=200)
        mock_resp.iter_lines.return_value = iter(lines)
        mock_post.return_value = mock_resp

        client = OllamaClient()
        chunks = list(
            client.chat_stream([{"role": "user", "content": "x"}])
        )
        assert chunks == ["你", "好"]
        assert "".join(chunks) == "你好"


# ============================================================================
# 角色提示词
# ============================================================================
class TestPrompts:
    def test_get_system_prompt_known_role(self):
        from prompts import get_system_prompt

        prompt = get_system_prompt("python-tutor")
        assert "Python" in prompt or "python" in prompt.lower()

    def test_get_system_prompt_unknown_role(self):
        from prompts import get_system_prompt

        with pytest.raises(ValueError):
            get_system_prompt("非法角色")

    def test_list_roles_has_general(self):
        from prompts import list_roles

        roles = list_roles()
        assert any(r["key"] == "general" for r in roles)
        assert all(
            "key" in r and "name" in r and "description" in r for r in roles
        )
