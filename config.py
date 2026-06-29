"""
剧本拆解大师 v2.49 — 配置文件
"""
import os
import hashlib
from utils import get_user_path

# 应用配置
def _load_secret_key():
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')
    try:
        with open(key_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        key = __import__('hashlib').sha256(os.urandom(64)).hexdigest()
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key

SECRET_KEY = _load_secret_key()

# 服务器绑定地址 — 生产环境应设置为 127.0.0.1
BIND_HOST = os.environ.get('BIND_HOST', '127.0.0.1')

# 允许的 base_url 白名单（防止 SSRF）
_ALLOWED = os.environ.get('ALLOWED_BASE_URLS', '')
ALLOWED_BASE_URLS = [u.strip() for u in _ALLOWED.split(',') if u.strip()] if _ALLOWED else None

# 上传目录和输出目录（用户可写）
UPLOAD_FOLDER = get_user_path('uploads')
OUTPUT_DIR = get_user_path('outputs')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

# AI API 配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
DEEPSEEK_API_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# 模型参数（种子固定保证输出可复现）
SEED = 8012
MAX_TOKENS = 384000       # 最大输出 384K
CONTEXT_LENGTH = 1000000  # 上下文窗口 1M

DEEPSEEK_KNOWN_MODELS = [
    {"id": "deepseek-v4-pro",   "name": "DeepSeek V4 Pro（专业，并发500）",     "ctx": "1M"},
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash（快速，并发2500）",  "ctx": "1M"},
    {"id": "deepseek-v4-flash-thinking", "name": "DeepSeek V4 Flash（思考模式）", "ctx": "1M"},
    {"id": "deepseek-chat",     "name": "DeepSeek Chat（即将弃用）",            "ctx": "64K"},
    {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner（即将弃用）",        "ctx": "64K"},
]

AI_PROVIDERS = {
    "ollama": {
        "name": "Ollama（本地）",
        "base_url": OLLAMA_BASE_URL,
        "default_model": OLLAMA_MODEL,
        "api_type": "ollama",
    },
    "deepseek": {
        "name": "DeepSeek API",
        "base_url": DEEPSEEK_API_URL,
        "default_model": DEEPSEEK_MODEL,
        "api_type": "openai",
    },
}
