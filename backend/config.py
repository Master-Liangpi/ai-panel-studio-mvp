"""
AI Panel Studio — 配置中心
所有环境变量统一从此模块读取，杜绝硬编码。
DeepSeek 密钥绝对不对外暴露，仅在此模块加载供 services.llm 内部使用。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（优先级：系统环境变量 > .env）
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=False)

# ---- DeepSeek（仅后端内部使用，绝对不暴露给前端）----
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT: int = int(os.getenv("DEEPSEEK_TIMEOUT", "60"))
DEEPSEEK_STREAM_TIMEOUT: int = int(os.getenv("DEEPSEEK_STREAM_TIMEOUT", "120"))

BASE_DIR = Path(__file__).resolve().parent

# ---- 数据库 ----
_database_path = os.getenv("DATABASE_PATH", "./data/ai_panel_studio.db")
DATABASE_PATH: str = str((BASE_DIR / _database_path).resolve()) if not Path(_database_path).is_absolute() else _database_path

# ---- 服务 ----
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

# ---- SSE ----
SSE_HEARTBEAT_INTERVAL: int = int(os.getenv("SSE_HEARTBEAT_INTERVAL", "15"))

# ---- 业务约束 ----
SPEECH_MIN_CHARS: int = int(os.getenv("SPEECH_MIN_CHARS", "20"))
SPEECH_MAX_CHARS: int = int(os.getenv("SPEECH_MAX_CHARS", "200"))
PANELIST_MIN_COUNT: int = int(os.getenv("PANELIST_MIN_COUNT", "1"))
PANELIST_MAX_COUNT: int = int(os.getenv("PANELIST_MAX_COUNT", "10"))


def validate_config() -> list[str]:
    """启动时校验关键配置，返回错误列表。"""
    errors = []
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-your-"):
        errors.append("DEEPSEEK_API_KEY 未配置或仍为占位符，请在 .env 中设置有效的 API Key")
    if DEEPSEEK_API_KEY and len(DEEPSEEK_API_KEY) < 10:
        errors.append("DEEPSEEK_API_KEY 格式似乎不正确（长度过短）")
    return errors
