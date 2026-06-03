import os

# API 配置
# 支持 OpenAI / DeepSeek / 通义千问 等兼容 API
# 通过环境变量设置，或在运行时输入

API_KEY = os.environ.get("API_KEY", "")
API_BASE = os.environ.get("API_BASE", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")

# Ollama:    API_BASE="http://localhost:11434/v1"
#   无需 API Key，模型通过 ollama pull 拉取
#   常见模型: qwen3, llama3, deepseek-r1, mistral, gemma3, codellama
# DeepSeek:  API_BASE="https://api.deepseek.com"
#   模型: deepseek-v4-pro / deepseek-v4-flash / deepseek-chat / deepseek-reasoner
# 通义千问:  API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
#   模型: qwen-plus / qwen-max / qwen-turbo / qwen-long
# OpenAI:    API_BASE="https://api.openai.com/v1"
#   模型: gpt-4o / gpt-4o-mini / gpt-3.5-turbo / o3-mini

MAX_TOKENS = 4096
TEMPERATURE = 0.0
MAX_ITERATIONS = 30
CONTEXT_MAX_MESSAGES = 20

# 文件操作安全目录
WORKSPACE_DIR = os.path.abspath(os.environ.get("AGENT_WORKSPACE", "."))
