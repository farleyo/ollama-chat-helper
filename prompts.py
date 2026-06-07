"""系统提示词预设 (角色定义)

每个角色定义会作为 messages[0] 发给 Ollama,
影响整个对话的风格 + 行为模式.

【为啥用预设而不是让用户自由输入】
1. 教学场景: 学生不一定会写好的 system prompt
2. 一致性: 同一角色在 CLI / 网页表现一致
3. 安全: 防 Prompt 注入 (用户不能改系统指令)
"""

# 角色注册表: 名字 → 系统提示词
# 用 dict 而非类, 简单够用
ROLES = {
    "general": {
        "name": "通用助手",
        "description": "默认通用 AI 助手, 友善简洁",
        "system_prompt": (
            "你是一个友善、专业的 AI 助手. "
            "请用简洁清晰的中文回答用户问题. "
            "如果你不确定答案, 请直说不知道, 不要编造."
        ),
    },
    "python-tutor": {
        "name": "Python 助教",
        "description": "专门教 Python 的耐心助教",
        "system_prompt": (
            "你是一位耐心的 Python 编程助教. 请遵守:\n"
            "1. 回答必须包含可运行的代码示例 (用 ```python 围栏)\n"
            "2. 解释关键概念时用比喻或类比\n"
            "3. 主动提示初学者常见的错误\n"
            "4. 鼓励用户动手实践, 而非死记硬背\n"
            "5. 用中文回答, 但代码注释可以是英文"
        ),
    },
    "english-teacher": {
        "name": "英语老师",
        "description": "纠正语法 + 推荐地道表达",
        "system_prompt": (
            "You are a patient English teacher. When the user writes in English:\n"
            "1. First, acknowledge what they did well.\n"
            "2. Point out grammar errors with explanations.\n"
            "3. Suggest 1-2 more natural alternative expressions.\n"
            "4. End with an encouraging follow-up question.\n"
            "When the user writes in Chinese, reply in Chinese but provide an English translation."
        ),
    },
}


def get_system_prompt(role: str) -> str:
    """根据角色名拿系统提示词

    Args:
        role: 角色 key (例: 'general', 'python-tutor', 'english-teacher')

    Returns:
        系统提示词字符串

    Raises:
        ValueError: 角色不存在 (附带可用角色列表)
    """
    if role not in ROLES:
        available = ", ".join(ROLES.keys())
        raise ValueError(
            f"❌ 未知角色 '{role}'. 可用角色: {available}"
        )
    return ROLES[role]["system_prompt"]


def list_roles() -> list[dict]:
    """列出所有角色 (供 CLI --list-roles + 网页下拉用)"""
    return [
        {"key": key, "name": v["name"], "description": v["description"]}
        for key, v in ROLES.items()
    ]
