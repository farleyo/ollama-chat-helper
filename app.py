"""Streamlit 网页 UI

用法:
    streamlit run app.py
    # 浏览器自动打开 http://localhost:8501

【UI 布局】
    ┌──────────┬─────────────────────────────────┐
    │          │  💬 ollama-chat-helper           │
    │ 侧边栏   │  ┌────────────────────────────┐  │
    │          │  │ 用户: ...                   │  │
    │ 模型选择 │  │ AI:  ...                    │  │
    │ 角色选择 │  │ 用户: ...                   │  │
    │ 服务状态 │  │ AI:  ... (流式打字效果)      │  │
    │ 清空按钮 │  └────────────────────────────┘  │
    │          │  [输入框________________] [发送] │
    └──────────┴─────────────────────────────────┘

【关键 Streamlit 概念】
- st.session_state: 跨重运行保留状态 (Streamlit 每次交互都从头跑)
- st.chat_message / st.chat_input: 1.30+ 内置聊天组件
- st.write_stream: 自动消费 generator + 流式打字效果
"""
from __future__ import annotations

import streamlit as st

from ollama_client import (
    DEFAULT_MODEL,
    OllamaClient,
    OllamaError,
    OllamaNotRunningError,
)
from prompts import ROLES, get_system_prompt


# ============================================================================
# 页面基础配置 (必须放在最前)
# ============================================================================
st.set_page_config(
    page_title="🤖 Ollama 本地 AI 助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# Session 状态初始化
# ============================================================================
def init_session_state():
    """初始化 session 状态 (只在第一次访问时跑)"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_role" not in st.session_state:
        st.session_state.current_role = "general"
    if "current_model" not in st.session_state:
        st.session_state.current_model = DEFAULT_MODEL


init_session_state()


# ============================================================================
# 客户端 (用 cache_resource 避免重复创建)
# ============================================================================
@st.cache_resource
def get_client() -> OllamaClient:
    """缓存 Ollama 客户端实例 (跨 session 共享)"""
    return OllamaClient()


client = get_client()


# ============================================================================
# 侧边栏: 配置 + 状态
# ============================================================================
with st.sidebar:
    st.title("⚙️ 配置")

    # ---- Ollama 服务状态 ----
    st.subheader("📡 服务状态")
    if client.is_alive():
        st.success(f"✅ Ollama 运行中\n\n`{client.base_url}`")
    else:
        st.error(
            f"❌ 服务未启动\n\n请在终端运行:\n```\nollama serve\n```"
        )
        st.stop()  # 服务挂了不让用户继续操作

    # ---- 模型选择 (从已安装列表) ----
    st.subheader("🧠 选择模型")
    try:
        available_models = client.list_models()
    except OllamaError as e:
        st.error(str(e))
        st.stop()

    if not available_models:
        st.warning("还没装任何模型. 运行: `ollama pull qwen3:8b`")
        st.stop()

    # 默认值: 优先 session 已选的, 否则用 .env 默认, 否则第一个
    default_idx = 0
    if st.session_state.current_model in available_models:
        default_idx = available_models.index(st.session_state.current_model)
    elif DEFAULT_MODEL in available_models:
        default_idx = available_models.index(DEFAULT_MODEL)

    selected_model = st.selectbox(
        "模型",
        available_models,
        index=default_idx,
        label_visibility="collapsed",
    )
    st.session_state.current_model = selected_model

    # ---- 角色选择 ----
    st.subheader("🎭 选择角色")
    role_keys = list(ROLES.keys())
    role_names = [f"{ROLES[k]['name']}" for k in role_keys]

    default_role_idx = role_keys.index(st.session_state.current_role)
    selected_role_idx = st.selectbox(
        "角色",
        range(len(role_keys)),
        format_func=lambda i: role_names[i],
        index=default_role_idx,
        label_visibility="collapsed",
    )
    new_role = role_keys[selected_role_idx]

    # 角色变了就清空历史
    if new_role != st.session_state.current_role:
        st.session_state.current_role = new_role
        st.session_state.messages = []
        st.toast(f"已切换角色: {ROLES[new_role]['name']}, 历史已清空", icon="🔄")

    # 显示角色描述
    st.caption(f"💡 {ROLES[st.session_state.current_role]['description']}")

    # ---- 操作按钮 ----
    st.divider()
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # ---- 信息展示 ----
    st.divider()
    st.caption("📊 当前会话")
    st.caption(f"消息数: {len(st.session_state.messages)}")
    st.caption(f"模型: `{st.session_state.current_model}`")


# ============================================================================
# 主区域: 聊天
# ============================================================================
st.title("🤖 Ollama 本地 AI 助手")
st.caption(
    f"角色: **{ROLES[st.session_state.current_role]['name']}**  "
    f"|  模型: **{st.session_state.current_model}**"
)


# ---- 渲染历史消息 ----
for msg in st.session_state.messages:
    avatar = "🧑" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])


# ---- 输入框 + 发送 ----
if user_input := st.chat_input("输入你的问题... (Shift+Enter 换行)"):
    # 1. 用户消息加到历史 + 显示
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    # 2. 构造发给 Ollama 的完整消息 (含 system prompt)
    api_messages = [
        {
            "role": "system",
            "content": get_system_prompt(st.session_state.current_role),
        }
    ]
    api_messages.extend(st.session_state.messages)

    # 3. 流式获取 AI 回复
    with st.chat_message("assistant", avatar="🤖"):
        try:
            # st.write_stream 自动消费 generator + 流式打字效果
            stream = client.chat_stream(
                api_messages,
                model=st.session_state.current_model,
            )
            full_reply = st.write_stream(stream)
        except OllamaNotRunningError as e:
            st.error(str(e))
            st.session_state.messages.pop()  # 回滚
            st.stop()
        except OllamaError as e:
            st.error(str(e))
            st.session_state.messages.pop()
            st.stop()

    # 4. AI 回复加到历史
    st.session_state.messages.append(
        {"role": "assistant", "content": full_reply}
    )
