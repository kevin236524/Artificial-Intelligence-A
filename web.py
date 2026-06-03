import streamlit as st
import json
import os
import requests

# 导入你现有的核心模块
from tools import get_all_tools
from agent import Agent
import config

# --- 常量与配置 ---
HISTORY_FILE = "chat_history.json"

# 移植 main.py 中的配置，并调整为适合 UI 显示的格式
PROVIDERS = {
    "Ollama (本地)": {
        "base": "http://localhost:11434/v1",
        "need_key": False,
        "models": [], 
    },
    "OpenAI": {
        "base": "https://api.openai.com/v1",
        "need_key": True,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "o3-mini"],
    },
    "DeepSeek": {
        "base": "https://api.deepseek.com",
        "need_key": True,
        "models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"],
    },
    "通义千问": {
        "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "need_key": True,
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-long"],
    },
    "自定义 (Custom)": {
        "base": "",
        "need_key": True,
        "models": [],
    }
}

st.set_page_config(page_title="AI Agent Web UI", page_icon="🤖", layout="wide")

# --- 辅助函数 ---
@st.cache_data(ttl=60) # 缓存 60 秒，避免频繁请求本地接口卡顿
def get_ollama_models():
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []

def load_chat_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_chat_history(messages):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def clear_chat():
    st.session_state.messages = []
    if "agent" in st.session_state:
        st.session_state.agent.reset()
    save_chat_history([])

# --- 状态初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

if "agent" not in st.session_state:
    # 1. 局部导入需要的具体 Tool 类，而不是无脑加载所有工具
    from tools import CalculatorTool, FileReadTool, FileWriteTool, ResearchAgentTool
    
    # 获取 config.py 中的默认配置
    default_api_key = config.API_KEY or "ollama"
    default_api_base = config.API_BASE
    default_model = config.MODEL_NAME
    
    # 2. 为主 Agent (项目经理) 装备初始工具箱
    tools = [
        CalculatorTool(),
        FileReadTool(),
        FileWriteTool(),
        # 传入默认的配置给研究员，保证一开局就能正常工作
        ResearchAgentTool(api_key=default_api_key, api_base=default_api_base, model=default_model) 
    ]
    
    # 3. 实例化主 Agent
    initial_agent = Agent(
        tools=tools, 
        api_key=default_api_key, 
        api_base=default_api_base, 
        model=default_model
    )
    
    # 4. 修改系统人设为项目经理
    initial_agent.system_prompt = initial_agent.system_prompt.replace(
        "你是一个智能 AI Agent",
        "你是一个全能的 AI 项目经理。遇到查资料的任务，请一定要调用 delegate_research 工具让研究员去办，你可以专心负责计算、读写文件和总结汇总。"
    )
    # 同步更新 messages 列表里的第一条 system prompt
    initial_agent.messages[0]["content"] = initial_agent.system_prompt
    
    # 5. 存入 session_state
    st.session_state.agent = initial_agent

# --- UI 侧边栏：模型选择与设置 ---
with st.sidebar:
    st.header("⚙️ Agent 设置")
    
    # 1. 选择提供商
    provider_name = st.selectbox("1. 选择 API 提供商", list(PROVIDERS.keys()))
    provider_info = PROVIDERS[provider_name]
    
    # 2. 根据提供商动态渲染配置项
    if provider_name == "自定义 (Custom)":
        api_base = st.text_input("API Base URL", value="https://api.openai.com/v1")
        model_name = st.text_input("模型名称", value="gpt-3.5-turbo")
        need_key = True
    else:
        api_base = provider_info["base"]
        need_key = provider_info["need_key"]
        
        available_models = provider_info["models"]
        if provider_name == "Ollama (本地)":
            available_models = get_ollama_models()
            if not available_models:
                st.warning("⚠ 未检测到 Ollama 模型，请确认服务已启动。")
        
        # 允许用户选择内置模型或手动输入
        model_options = available_models + ["自定义输入..."] if available_models else ["自定义输入..."]
        model_selection = st.selectbox("2. 选择模型", model_options)
        
        if model_selection == "自定义输入...":
            model_name = st.text_input("手动输入模型名称", placeholder="例如: qwen3")
        else:
            model_name = model_selection

    # 3. API Key 输入 (如果需要)
    api_key = "ollama"
    if need_key:
        api_key = st.text_input("3. API Key", type="password", value=config.API_KEY, help="将优先使用 config.py 中的配置")

    # 4. 应用设置按钮
    if st.button("💾 应用参数 (保存当前对话)", use_container_width=True):
        if need_key and not api_key:
            st.error("请输入 API Key！")
        elif not model_name:
            st.error("请输入或选择模型名称！")
        else:
            # --- 多 Agent 架构改造点 ---
            # 引入特定的 Tool 类
            from tools import CalculatorTool, FileReadTool, FileWriteTool, ResearchAgentTool
            
            # 为主 Agent (项目经理) 装备工具
            # 注意：把子 Agent 当作工具塞给主 Agent！
            tools = [
                CalculatorTool(),
                FileReadTool(),
                FileWriteTool(),
                ResearchAgentTool(api_key=api_key, api_base=api_base, model=model_name) 
                # 你可以把 WikipediaSearchTool 从这里拿掉，逼迫主 Agent 必须叫研究员去查资料
            ]
            
            new_agent = Agent(tools=tools, api_key=api_key, api_base=api_base, model=model_name)
            
            # 保留历史对话上下文 (修改系统人设为项目经理)
            new_agent.system_prompt = new_agent.system_prompt.replace(
                "你是一个智能 AI Agent",
                "你是一个全能的 AI 项目经理。遇到查资料的任务，请一定要调用 delegate_research 工具让研究员去办，你可以专心负责计算、读写文件和总结汇总。"
            )
            new_agent.messages[0]["content"] = new_agent.system_prompt

            if len(st.session_state.agent.messages) > 1:
                new_agent.messages = [new_agent.messages[0]] + st.session_state.agent.messages[1:]
                
            st.session_state.agent = new_agent
            st.success(f"已切换至 {model_name}，且对话已保留。")
    
    # 5. 清除上下文操作
    st.button("🗑️ 清空当前对话与历史记录", on_click=clear_chat, type="primary", use_container_width=True)


# --- 主界面：聊天区域 ---
st.title("🤖 智能 AI Agent Web")
st.caption(f"当前运行中: `{st.session_state.agent.model}` @ `{st.session_state.agent.client.base_url}`")

# 渲染历史消息 (跳过索引 0 的 system prompt)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理用户输入
if prompt := st.chat_input("请输入你的指令..."):
    # 1. 显示用户输入
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 2. Agent 处理 (流式输出)
    with st.chat_message("assistant"):
        # 使用 st.status 创建一个可折叠的状态框，专门装载“内心戏”和“工具调用”
        status = st.status("🧠 Agent 正在思考...", expanded=True)
        thought_placeholder = status.empty()
        
        # 状态框外，用于打印最终回答的占位符
        final_placeholder = st.empty()
        
        final_response = ""
        current_thought = ""
        
        # 遍历生成器，接收实时状态
        for event in st.session_state.agent.run_stream(prompt):
            if event["type"] == "chunk":
                # 实时打字机效果显示 Thought
                current_thought = event["full_text"]
                thought_placeholder.markdown(f"```text\n{current_thought}\n```")
                
            elif event["type"] == "tool":
                # 记录使用了什么工具
                status.write(f"🛠️ **调用工具**: `{event['action']}`\n*参数*: `{event['params']}`")
                current_thought = "" # 清空当前 thought，准备显示下一轮思考
                thought_placeholder = status.empty() # 创建新的占位符防止覆盖
                
            elif event["type"] == "observation":
                # 记录工具返回的观察结果（截断以防太长撑爆屏幕）
                obs = str(event['content'])
                if len(obs) > 300: 
                    obs = obs[:300] + " ... (已截断)"
                status.write(f"👁️ **观察结果**: {obs}")
                
            elif event["type"] == "final_answer":
                # 拿到最终答案
                final_response = event["content"]
                status.update(label="✅ 任务完成", state="complete", expanded=False) # 自动折叠思考过程
                final_placeholder.markdown(final_response) # 在主聊天区打印最终答案
                
            elif event["type"] == "error":
                # 错误处理
                final_response = event["content"]
                status.update(label="❌ 发生错误", state="error")
                final_placeholder.error(final_response)
    
    # 3. 仅保存用户的问和 Agent 的“最终回答”到历史记录
    if final_response:
        st.session_state.messages.append({"role": "assistant", "content": final_response})
        save_chat_history(st.session_state.messages)