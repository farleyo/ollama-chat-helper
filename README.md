# 🤖 ollama-chat-helper · 本地 AI 小助手

> **一个 2-3 小时打造的本地 AI 命令行 + 网页双形态问答工具**
> 基于本机 [Ollama](https://ollama.com), 完全离线, 数据不出本地.

---

## ✨ 项目简介

`ollama-chat-helper` 是一个轻量级的本地 AI 助手, 专为已经安装 Ollama 的开发者设计:

- 🚀 **CLI 命令行**: 一条命令直接问答, 适合脚本 / Shell 集成
- 💬 **流式输出**: 字符级实时打印, 体验如 ChatGPT
- 🎭 **角色预设**: 通用助手 / Python 助教 / 英语老师 三种内置角色
- 🌐 **Streamlit 网页**: 30 秒搭起的可视化对话界面
- 💾 **历史持久化**: 对话自动保存到 `~/.ollama_chat/history.json`
- 🛡️ **零依赖关键功能**: 只用 `requests` 标准网络库, 其他全是可选

### 适合谁

- 已经装了 Ollama 想找趁手工具的开发者
- 教学场景需要"看得见的本地 AI"演示
- Vibe Coding 学员的实战起点项目

### 不适合谁

- 没有本机 Ollama (请先 [安装](https://ollama.com/download))
- 需要多用户 / 联网模型 / RAG / 多模态 (本项目刻意保持简单)

---

## 🎬 演示截图

### CLI 单轮模式

```bash
$ python chat.py "用一句话介绍 Python"
🤖 [通用助手 · qwen3:8b]
────────────────────────────────────────────────────────────
Python 是一种简洁易读的高级编程语言, 广泛用于数据分析、Web 开发和人工智能.
────────────────────────────────────────────────────────────
```

### CLI 交互模式

```bash
$ python chat.py -i --role python-tutor
============================================================
🤖 ollama-chat-helper · 交互模式
   角色: Python 助教  |  模型: qwen3:8b
   输入 /help 看命令, /quit 退出
============================================================

你 > 怎么写 Hello World

AI > 在 Python 里, 一行就能搞定:

```python
print("Hello, World!")
```

保存为 hello.py, 运行 `python hello.py` 即可...
```

### Streamlit 网页

```
streamlit run app.py
# 浏览器自动打开 http://localhost:8501
```

侧边栏可切换模型/角色, 主区域是聊天窗口, 流式打字效果.

---

## 📦 功能列表

| 功能 | CLI | 网页 |
|---|---|---|
| 单轮问答 | ✅ | — |
| 多轮对话 | ✅ `-i` | ✅ 默认 |
| 流式输出 | ✅ | ✅ |
| 角色预设 | ✅ `--role` | ✅ 下拉 |
| 模型切换 | ✅ `--model` | ✅ 下拉 |
| 健康检查 | ✅ 启动时 | ✅ 实时 |
| 中文友好错误 | ✅ | ✅ |
| 历史持久化 | ✅ JSON | ✅ Session |
| 列模型/角色 | ✅ `--list-*` | ✅ 侧边栏 |
| 单元测试 | ✅ 12 个 | — |

---

## 🛠️ 环境要求

| 项目 | 要求 | 验证命令 |
|---|---|---|
| Python | ≥ 3.10 | `python --version` |
| Ollama | 已安装 + 运行中 | `curl http://localhost:11434` |
| 至少 1 个模型 | 任意 | `ollama list` |

### 没装 Ollama?

```bash
# macOS
brew install ollama
ollama serve &        # 后台启动
ollama pull qwen3:8b  # 拉默认模型 (5.2GB)

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 🚀 快速开始 (4 步)

### 1. 克隆 + 进入目录

```bash
cd Week19/ollama-chat-helper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单:
- `requests` - HTTP 客户端 (核心必需)
- `python-dotenv` - 配置文件读取 (可选, 没装也能跑)
- `streamlit` - 网页 UI (只用 CLI 可不装)
- `pytest` - 测试框架 (只跑代码可不装)

### 3. (可选) 配置

```bash
cp .env.example .env
# 编辑 .env 改默认模型 / Ollama 地址等
# 不改也行, 默认值已经够跑
```

### 4. 跑起来

```bash
# 方式 A: CLI 单轮
python chat.py "你好"

# 方式 B: CLI 交互
python chat.py -i

# 方式 C: 网页
streamlit run app.py
```

---

## 📚 完整使用示例

### CLI 单轮

```bash
# 基础
python chat.py "什么是装饰器"

# 指定角色
python chat.py "Translate 'Hello' to French" --role english-teacher

# 指定模型
python chat.py "1+1=?" --model deepseek-r1:8b

# 关闭流式 (适合管道处理)
python chat.py "返回 JSON: {a:1}" --no-stream

# 查询资源
python chat.py --list-models
python chat.py --list-roles
```

### CLI 交互式 (推荐!)

```bash
python chat.py -i --role python-tutor
```

进入后可用命令:

| 命令 | 作用 |
|---|---|
| `/help` `/?` | 显示帮助 |
| `/quit` `/q` `/exit` | 退出 |
| `/reset` | 清空当前对话历史 |
| `/save` | 立即保存历史到磁盘 |
| `/role <name>` | 切换角色 (重置历史) |
| `/roles` | 列出所有角色 |
| `/model <name>` | 切换模型 |

### Streamlit 网页

```bash
streamlit run app.py
```

特性:
- 侧边栏: 模型选择 / 角色选择 / 服务状态 / 清空按钮
- 主区域: 聊天窗口 (用户头像 🧑 / AI 头像 🤖)
- 流式打字: 字符级实时显示
- 服务挂了立即提示 (没法发消息)

---

## 🎭 内置角色

| 角色 key | 名称 | 用途 |
|---|---|---|
| `general` | 通用助手 | 默认, 友善简洁回答任何问题 |
| `python-tutor` | Python 助教 | 教学, 必带代码示例 + 比喻 + 易错点提示 |
| `english-teacher` | 英语老师 | 纠语法 + 推荐地道表达 + 鼓励互动 |

想加新角色? 编辑 `prompts.py` 的 `ROLES` 字典即可:

```python
ROLES["sql-mentor"] = {
    "name": "SQL 导师",
    "description": "教 SQL 的耐心导师",
    "system_prompt": "你是 SQL 教学专家, 用真实场景举例...",
}
```

---

## 🧪 跑测试

```bash
pytest tests/ -v
```

测试覆盖:
- ✅ 健康检查 (运行 / 连接拒绝 / 超时)
- ✅ 模型列表 (正常 / 服务挂)
- ✅ 单次对话 (成功 / 模型不存在 / 服务挂)
- ✅ 流式对话 (chunk 累积)
- ✅ 角色提示词 (已知 / 未知 / 列表)

不需要真实 Ollama (用 mock 模拟), 12 个测试 < 1 秒跑完.

---

## 📁 项目结构

```
ollama-chat-helper/
├── README.md                  ← 你正在看
├── requirements.txt           ← 依赖清单
├── .gitignore                 ← Git 忽略规则
├── .env.example               ← 配置模板
├── LICENSE                    ← MIT 协议
├── chat.py                    ← CLI 主入口 (~370 行)
├── app.py                     ← Streamlit 网页 (~180 行)
├── ollama_client.py           ← Ollama API 封装 (~250 行)
├── prompts.py                 ← 角色预设 (~70 行)
├── data/
│   └── history.example.json   ← 历史记录格式示例
└── tests/
    └── test_client.py         ← 12 个单元测试
```

---

## 🔧 配置说明 (.env)

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `OLLAMA_DEFAULT_MODEL` | `qwen3:8b` | 默认使用的模型 |
| `OLLAMA_TIMEOUT` | `60` | 单次请求超时秒数 |
| `HISTORY_PATH` | `~/.ollama_chat/history.json` | 历史保存路径 |

---

## 🆘 常见问题 (FAQ)

### Q1: 报错 `❌ Ollama 服务未运行`

```bash
# 方法 1: 前台启动 (能看日志)
ollama serve

# 方法 2: 后台启动 (推荐日常用)
ollama serve > /tmp/ollama.log 2>&1 &
```

### Q2: 报错 `❌ 模型 'xxx' 未安装`

```bash
ollama pull qwen3:8b
ollama list   # 验证是否安装成功
```

### Q3: 流式输出有时卡住

第一次跑某个模型时, Ollama 要把模型从磁盘加载到内存 (3-30 秒). 之后跑就秒回. 如果一直卡, 调大 `OLLAMA_TIMEOUT=120`.

### Q4: 想用其他端口的 Ollama (例如远程服务器)

修改 `.env`:
```
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

### Q5: 历史文件能 commit 到 Git 吗?

**不要!** 可能含敏感对话. `.gitignore` 已经把 `data/history.json` 排除. 只有示例文件 `data/history.example.json` 入库.

### Q6: ARM Mac (M1/M2/M3) 能跑吗?

完全能. Ollama 原生支持 Apple Silicon, 跑 7B-13B 模型流畅. 30B+ 建议用 32GB 内存机器.

### Q7: 想加 RAG / 文件上传 / 多模态怎么做?

本项目刻意保持简单 (Vibe Coding 2-3 小时实战范围). 想升级:
- **RAG**: 集成 `langchain` + `chromadb` 加文档检索
- **文件上传**: Streamlit `st.file_uploader` + `PyPDF2`
- **多模态**: 模型换成 `qwen3-vl` 系列, API 加 `images` 字段

可以参考课程 Week11+ (RAG) 和 Week16 (多模态 Agent) 的实现.

---

## 🛣️ 进阶路线 (本项目之后能做什么)

| 方向 | 加什么 | 工作量 |
|---|---|---|
| **多用户** | FastAPI 后端 + JWT 鉴权 | +2 天 |
| **RAG** | LangChain + Chroma + 文档上传 | +3 天 |
| **语音** | OpenAI Whisper (本地) + edge-tts | +1 天 |
| **桌面 App** | Tauri 打包成 macOS/Windows 安装包 | +2 天 |
| **WebSocket** | 真正的实时双向通信 | +1 天 |
| **Function Calling** | Ollama Tool Use API | +2 天 |

---

## 🎓 这个项目教你什么

学完这个项目, 你会掌握:

1. **本地 LLM 调用**: Ollama REST API 的 chat / stream 端点
2. **流式响应处理**: `requests.iter_lines` + Server-Sent Events 思路
3. **CLI 工程化**: argparse 子命令 / 中文错误 / 历史持久化
4. **Streamlit 速成**: `st.chat_message` / `st.write_stream` / `session_state`
5. **可选依赖模式**: try/except ImportError 让 dotenv 等成可选
6. **测试模拟**: unittest.mock 测网络 API 的标准套路
7. **优雅降级**: Ollama 服务挂、模型不存在、超时 都给中文 actionable 提示

---

## 📜 License

MIT - 自由使用 / 修改 / 商用. 详见 [LICENSE](LICENSE).

---

## 🙏 致谢

- [Ollama](https://ollama.com) - 让本地 LLM 一行命令搞定
- [Streamlit](https://streamlit.io) - 让 Python 写 UI 不再难
- 课程 Vibe Coding 实战任务方案 - 提供项目设计指南

---

**Vibe Coding 实战 · Week19 方向 A 交付**
**作者**: ollama-chat-helper
**完成日期**: 2026-06-07
**实际耗时**: ~2.3 小时 (含方案讨论 + 编码 + 测试 + 文档)
