import math
import re
import os

import requests

import config


class Tool:
    """工具基类"""

    def __init__(self, name, description, parameters=None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    def execute(self, **kwargs) -> str:
        raise NotImplementedError


class CalculatorTool(Tool):
    """安全计算器 - 支持基本数学运算和 math 函数"""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="安全计算数学表达式。支持 + - * / ** sqrt sin cos tan log abs round 等运算。",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的数学表达式",
                    }
                },
                "required": ["expression"],
            },
        )

    def execute(self, expression: str) -> str:
        allowed_names = {
            k: v
            for k, v in math.__dict__.items()
            if not k.startswith("__")
        }
        allowed_names.update(
            {
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
                "pow": pow,
                "pi": math.pi,
                "e": math.e,
            }
        )

        expression = expression.replace("^", "**")

        if not re.match(r"^[\d\s+\-*/().,%eEpi\w]+$", expression):
            return f"错误: 表达式包含不允许的字符: {expression}"

        try:
            code = compile(expression, "<calculator>", "eval")
            for name in code.co_names:
                if name not in allowed_names:
                    return f"错误: 不允许使用 '{name}'"
            result = eval(code, {"__builtins__": {}}, allowed_names)
            if isinstance(result, float):
                result = round(result, 10)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"


class WikipediaSearchTool(Tool):
    """维基百科搜索"""

    def __init__(self):
        super().__init__(
            name="wikipedia_search",
            description="搜索维基百科，返回相关文章标题和摘要片段。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    }
                },
                "required": ["query"],
            },
        )

    def execute(self, query: str) -> str:
        try:
            url = "https://zh.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 5,
            }
            headers = {"User-Agent": "AI-Agent-Framework/1.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("query", {}).get("search", [])
            if not results:
                # 回退到英文维基
                url = "https://en.wikipedia.org/w/api.php"
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("query", {}).get("search", [])

            if not results:
                return f"未找到与 '{query}' 相关的维基百科条目。"

            lines = []
            for i, r in enumerate(results, 1):
                snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
                lines.append(f"{i}. {r['title']}\n   {snippet}")

            return "\n".join(lines)

        except requests.RequestException as e:
            return f"维基百科搜索失败: {e}"


class WikipediaSummaryTool(Tool):
    """维基百科文章摘要"""

    def __init__(self):
        super().__init__(
            name="wikipedia_summary",
            description="获取维基百科文章的摘要内容。需要提供精确的文章标题。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "维基百科文章的精确标题",
                    }
                },
                "required": ["title"],
            },
        )

    def execute(self, title: str) -> str:
        try:
            # 先尝试中文维基
            result = self._fetch_summary("zh.wikipedia.org", title)
            if result and "未找到" not in result:
                return result
            # 回退到英文维基
            return self._fetch_summary("en.wikipedia.org", title)
        except Exception as e:
            return f"获取摘要失败: {e}"

    def _fetch_summary(self, domain: str, title: str) -> str:
        url = f"https://{domain}/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json",
        }
        headers = {"User-Agent": "AI-Agent-Framework/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                return f"未找到标题为 '{title}' 的维基百科文章。"
            extract = page_data.get("extract", "")
            if len(extract) > 2000:
                extract = extract[:2000] + "\n...(已截断)"
            return extract

        return f"未找到标题为 '{title}' 的维基百科文章。"


class FileReadTool(Tool):
    """读取本地文件"""

    def __init__(self):
        super().__init__(
            name="file_read",
            description="读取本地文件内容。大文件可分段读取：指定 offset(起始字符位置,默认0) 和 limit(最大字符数,默认8000)。返回时会附带文件总长度和当前已读范围。",
            parameters={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "从第几个字符开始读取，默认0",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多读取的字符数，默认8000",
                    },
                },
                "required": ["filepath"],
            },
        )

    def execute(self, filepath: str, offset: int = 0, limit: int = 8000) -> str:
        full_path = self._resolve_path(filepath)
        if not os.path.exists(full_path):
            return f"错误: 文件不存在: {filepath}"
        if not os.path.isfile(full_path):
            return f"错误: 路径不是文件: {filepath}"
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                content = f.read(limit)
                f.seek(0, 2)
                total = f.tell()
            header = f"[文件总长 {total} 字符，当前读取范围: {offset}-{offset+len(content)}]\n"
            if offset + len(content) < total:
                header += f"[未读完，继续读取请设 offset={offset+len(content)}]\n"
            return header + content
        except Exception as e:
            return f"读取文件失败: {e}"

    def _resolve_path(self, filepath: str) -> str:
        if os.path.isabs(filepath):
            # 安全检查: 确保在 workspace 内
            abs_path = os.path.abspath(filepath)
            workspace = os.path.abspath(config.WORKSPACE_DIR)
            if not abs_path.startswith(workspace):
                return os.path.join(workspace, os.path.basename(filepath))
            return abs_path
        return os.path.join(config.WORKSPACE_DIR, filepath)


class FileWriteTool(Tool):
    """写入本地文件"""

    def __init__(self):
        super().__init__(
            name="file_write",
            description="将内容写入本地文件。如果文件已存在则覆盖，不存在则创建。",
            parameters={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "要写入的文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的内容",
                    },
                },
                "required": ["filepath", "content"],
            },
        )

    def execute(self, filepath: str, content: str) -> str:
        full_path = self._resolve_path(filepath)
        try:
            parent_dir = os.path.dirname(full_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"成功写入 {len(content)} 个字符到 {filepath}"
        except Exception as e:
            return f"写入文件失败: {e}"

    def _resolve_path(self, filepath: str) -> str:
        if os.path.isabs(filepath):
            abs_path = os.path.abspath(filepath)
            workspace = os.path.abspath(config.WORKSPACE_DIR)
            if not abs_path.startswith(workspace):
                return os.path.join(workspace, os.path.basename(filepath))
            return abs_path
        return os.path.join(config.WORKSPACE_DIR, filepath)


def get_all_tools():
    """获取所有可用工具"""
    return [
        CalculatorTool(),
        WikipediaSearchTool(),
        WikipediaSummaryTool(),
        FileReadTool(),
        FileWriteTool(),
    ]
class ResearchAgentTool(Tool):
    """分配任务给【研究员 Agent】"""

    def __init__(self, api_key, api_base, model):
        super().__init__(
            name="delegate_research",
            description="将需要信息检索、查阅维基百科和深度总结的任务派发给专业的【研究员 Agent】。请在参数中给出详细的任务描述。",
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "详细描述你需要研究员去搜索和总结的具体任务",
                    }
                },
                "required": ["task"],
            },
        )
        # 接收并保存从外部传入的模型配置
        self.api_key = api_key
        self.api_base = api_base
        self.model = model

    def execute(self, task: str) -> str:
        # 【关键】局部导入 Agent，防止 tools.py 和 agent.py 发生循环依赖
        from agent import Agent 
        
        # 1. 给研究员 Agent 分配专属的工具包（只给查资料的工具，不给写文件的工具）
        research_tools = [WikipediaSearchTool(), WikipediaSummaryTool()]
        
        # 2. 实例化子 Agent
        researcher = Agent(
            tools=research_tools, 
            api_key=self.api_key, 
            api_base=self.api_base, 
            model=self.model
        )
        
        # 3. 魔改子 Agent 的系统提示词，让它专注做研究
        researcher.system_prompt = researcher.system_prompt.replace(
            "你是一个智能 AI Agent", 
            "你是一个极其严谨的 AI 研究员。你的唯一任务是使用工具查阅客观事实，并输出结构化、详细的研究报告。不要和用户寒暄。"
        )
        # 同步更新 messages 列表里的 system prompt
        researcher.messages[0]["content"] = researcher.system_prompt
        
        # 4. 执行任务（使用你原本写好的非流式 run 方法），拿到结果
        try:
            # verbose=False 不在终端打印啰嗦的过程
            result = researcher.run(task, verbose=False) 
            return f"【研究员 Agent 的报告】:\n{result}"
        except Exception as e:
            return f"研究员 Agent 执行任务时崩溃了: {e}"