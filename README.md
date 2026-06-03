# 🤖 智能 AI Agent (多智能体协作版)

这是一个基于 ReAct (Reasoning and Acting) 架构的本地化 AI Agent 框架。本项目不仅支持工具调用，还引入了**多智能体协作 (Multi-Agent)** 机制，并提供终端 (CLI) 与现代化网页端 (Web UI) 两种交互形态。

## ✨ 核心特性

* **🖥️ 双轨交互界面**
  * **Web 端**：基于 Streamlit 打造，支持精美的聊天 UI、流式输出 (Streaming)、内部思考过程折叠展示以及历史记录持久化保存。
  * **CLI 端**：原汁原味的命令行界面，适合极客开发、调试测试与日志查看。
* **🧠 多模型与多平台支持**
  * 无缝兼容云端大模型（OpenAI、DeepSeek、通义千问等）。
  * 完美支持本地离线部署（基于 Ollama，无需 API Key 即可调用 qwen、llama3 等本地模型）。
  * 支持在侧边栏热切换模型，且**保留上下文记忆**。
* **🤝 多智能体协作 (Multi-Agent)**
  * **项目经理 Agent**：负责任务统筹、数学计算、文件读写与最终总结。
  * **研究员 Agent**：作为“内部工具”被项目经理唤醒，专注负责维基百科检索与深度资料整合。
* **🛠️ 丰富的内置工具**
  * `calculator`: 安全的数学表达式计算器。
  * `file_read` / `file_write`: 本地工作区文件读写。
  * `delegate_research`: 派发深度检索任务给子 Agent。

---

## 📦 快速安装

1. 确保你已安装 Python 3.8+ 环境。
2. 克隆或下载本项目到本地。
3. 在项目根目录下，安装依赖包：

```bash
pip install -r requirements.txt
```

*(依赖包含 `openai`, `requests`, `streamlit` 等)*

---

## 🚀 使用指南

### 方式一：启动 Web 网页版 (推荐)
提供现代化的可视化界面和极佳的用户体验。在终端中运行以下命令：

```bash
streamlit run web.py
```
*运行后会自动在浏览器中打开网址（通常是 `http://localhost:8501`）。你可以在左侧边栏配置 API 提供商和模型。*

### 方式二：启动纯命令行版
适合快速调试或服务器后台运行。在终端中运行以下命令：

```bash
python cli_main.py
```
*根据命令行提示选择模型配置，输入 `quit` 退出，输入 `reset` 重置对话。*

---

## ⚙️ 配置说明

项目的默认配置可以通过修改根目录下的 `config.py` 文件来实现：
* `API_KEY`: 你的默认 API 密钥（如使用本地 Ollama 则填入 `"ollama"`）。
* `API_BASE`: API 的基础 URL。
* `MODEL_NAME`: 默认使用的模型名称。
* `WORKSPACE_DIR`: Agent 允许读写文件的安全沙箱目录。

*提示：在 Web UI 中修改的配置会实时生效，无需重启服务。*
