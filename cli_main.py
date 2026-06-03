import sys

from tools import get_all_tools
from agent import Agent
import config


PROVIDERS = {
    "1": {
        "name": "Ollama (本地)",
        "base": "http://localhost:11434/v1",
        "need_key": False,
        "models": [],  # 动态获取
    },
    "2": {
        "name": "OpenAI",
        "base": "https://api.openai.com/v1",
        "need_key": True,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "o3-mini"],
    },
    "3": {
        "name": "DeepSeek",
        "base": "https://api.deepseek.com",
        "need_key": True,
        "models": [
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-chat",
            "deepseek-reasoner",
        ],
    },
    "4": {
        "name": "通义千问",
        "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "need_key": True,
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-long"],
    },
}


def get_ollama_models():
    """从 Ollama 获取已安装的模型列表"""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return models
    except Exception:
        pass
    return []


def select_provider():
    """返回 (api_base, model, need_key) 或 (None, None, None) 表示退出"""
    print("\n选择 API 提供商 (输入 q 退出):")
    for key, p in PROVIDERS.items():
        print(f"  {key}. {p['name']}")
    print("  5. 自定义")
    choice = input("> ").strip().lower()

    if choice in ("q", "quit", "exit"):
        return None, None, None

    if choice == "5":
        api_base = input("API Base URL: ").strip()
        model = input("模型名称: ").strip()
        return api_base, model, True

    if choice not in PROVIDERS:
        choice = "1"
        print("默认使用 Ollama (本地)")

    provider = PROVIDERS[choice]
    api_base = provider["base"]
    need_key = provider["need_key"]
    models = provider["models"]

    # Ollama 动态获取模型列表
    if not models and choice == "1":
        print("\n正在获取 Ollama 已安装的模型...")
        models = get_ollama_models()
        if not models:
            print("⚠ 未检测到 Ollama 模型，请确认 Ollama 已启动并已拉取模型")
            model = input("请手动输入模型名称 (如 qwen3, llama3): ").strip()
            if not model:
                return None, None, None
            return api_base, model, need_key

    print(f"\n{provider['name']} 可用模型:")
    for i, m in enumerate(models, 1):
        suffix = " (推荐)" if i == 1 else ""
        print(f"  {i}. {m}{suffix}")
    print("  0. 自定义输入")

    m_choice = input("> ").strip()
    if m_choice == "0":
        model = input("模型名称: ").strip() or (models[0] if models else "")
    else:
        try:
            idx = int(m_choice) - 1
            model = models[idx] if 0 <= idx < len(models) else models[0]
        except (ValueError, IndexError):
            model = models[0] if models else ""

    return api_base, model, need_key


def main():
    print("🤖 AI Agent 简易版 (支持多 Agent 协作)\n")

    saved_key = config.API_KEY

    while True:
        api_base, model, need_key = select_provider()
        if api_base is None:
            print("再见!")
            break

        if need_key:
            api_key = saved_key
            if not api_key:
                api_key = input("API Key: ").strip()
                if not api_key:
                    print("需要 API Key")
                    continue
            saved_key = api_key
        else:
            # Ollama 不需要 API key，传一个占位符
            api_key = "ollama"

        print(f"\n模型: {model} | API: {api_base}")

        # --- 核心修改点：动态加载工具并注入子 Agent 配置 ---
        from tools import CalculatorTool, FileReadTool, FileWriteTool, ResearchAgentTool
        
        tools = [
            CalculatorTool(),
            FileReadTool(),
            FileWriteTool(),
            # 把当前选择的模型配置传给研究员 Agent
            ResearchAgentTool(api_key=api_key, api_base=api_base, model=model)
        ]

        print("\n已加载工具:")
        for tool in tools:
            print(f"  · {tool.name} — {tool.description}")

        # 实例化主 Agent
        agent = Agent(tools=tools, api_key=api_key, api_base=api_base, model=model)
        
        # 注入“项目经理”人设，启用多 Agent 协作
        agent.system_prompt = agent.system_prompt.replace(
            "你是一个智能 AI Agent",
            "你是一个全能的 AI 项目经理。遇到查资料的任务，请一定要调用 delegate_research 工具让研究员去办，你可以专心负责计算、读写文件和总结汇总。"
        )
        agent.messages[0]["content"] = agent.system_prompt

        print("\n  输入 quit 切换模型，reset 重置对话")
        print("═" * 50 + "\n")

        # 为了确保 reset 后人设不丢，这里重置时会自动使用修改后的 system_prompt
        agent.reset() 
        
        while True:
            try:
                user_input = input("你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if user_input.lower() == "reset":
                agent.reset()
                print("对话已重置\n")
                continue

            # 使用原来的 run 方法（非流式），verbose=True 可以在控制台打印详细的 Thought 过程
            result = agent.run(user_input, verbose=True)
            print(f"\nAgent: {result}\n")

if __name__ == "__main__":
    main()
