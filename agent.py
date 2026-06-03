import json
import re

from openai import OpenAI

import config


class Agent:
    """ReAct Agent"""

    def __init__(self, tools, api_key=None, api_base=None, model=None):
        self.tools = {tool.name: tool for tool in tools}
        self.client = OpenAI(
            api_key=api_key or config.API_KEY,
            base_url=api_base or config.API_BASE,
        )
        self.model = model or config.MODEL_NAME
        self.messages = []
        self._consecutive_parse_failures = 0

        self.system_prompt = self._build_system_prompt()
        self.messages.append({"role": "system", "content": self.system_prompt})

    def _build_system_prompt(self):
        tool_descriptions = []
        for tool in self.tools.values():
            params_str = json.dumps(tool.parameters, ensure_ascii=False, indent=2)
            tool_descriptions.append(
                f"- {tool.name}: {tool.description}"
                f"\n  参数规格: {params_str}"
            )

        tools_text = "\n".join(tool_descriptions)
        tool_names = ", ".join(self.tools.keys())

        prompt = f"""你是一个智能 AI Agent，配备了以下工具来完成任务:

{tools_text}

你必须严格按照以下格式进行每一轮的输出:

Thought: <用中文写下你的推理过程，分析当前状态，决定下一步做什么>
Action: <工具名称，必须是 [{tool_names}] 之一>
Action Input: <JSON 格式的参数，一行或多行均可>

调用工具后，你会收到一个 Observation（观察结果）。你可以重复 Thought → Action → Action Input 的过程多次，直到获得足够的信息。

当你认为任务已完成后，输出:
Final Answer: <你的最终回答>

【重要规则】
1. 每次只能调用一个工具，输出一个 Action。
2. Action Input 必须是有效的 JSON。
3. 只能使用上面列出的工具，不能凭空编造。
4. 如果工具返回错误，尝试其他方法解决问题。
5. 对于多步任务，请一步步来，不要跳步。
6. 严禁在你的回复中写"示例"或"比如"后跟 Thought/Action/Final Answer——系统会把它们当真并执行。
7. 读取文件等简单任务完成后，直接输出 Final Answer 回复用户，不要继续输出 Action。
8. 如果文件被截断未读完，用 offset 参数继续读取剩余部分。"""
        return prompt

    def _extract_json(self, text):
        """从文本中提取 JSON 对象（支持嵌套和多行）"""
        # 先找 json 代码块
        code_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if code_match:
            return code_match.group(1)

        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def _parse_action(self, text):
        """解析 LLM 输出，提取 Action 和参数"""
        # 检查 Final Answer
        final_match = re.search(
            r"Final\s*Answer\s*[:：]\s*(.*)", text, re.DOTALL | re.IGNORECASE
        )
        if final_match:
            return "final_answer", final_match.group(1).strip()

        # 提取 Action
        action_match = re.search(r"Action\s*[:：]\s*(\w+)", text, re.IGNORECASE)
        if not action_match:
            return None, None

        action = action_match.group(1).strip()

        # 提取 Action Input (JSON) — 从整段文本中找
        json_str = self._extract_json(text)
        if json_str:
            try:
                params = json.loads(json_str)
                return action, params
            except json.JSONDecodeError:
                pass

        # 尝试从 "Action Input:" 后面提取
        input_match = re.search(
            r"Action\s*Input\s*[:：]\s*(.+)", text, re.DOTALL | re.IGNORECASE
        )
        if input_match:
            raw = input_match.group(1).strip()
            inner_json = self._extract_json(raw)
            if inner_json:
                try:
                    return action, json.loads(inner_json)
                except json.JSONDecodeError:
                    pass
            return action, raw.strip('"').strip("'")

        return action, {}

    def _execute_tool(self, action, params):
        """执行工具调用"""
        if action not in self.tools:
            available = ", ".join(self.tools.keys())
            return f"错误: 未知工具 '{action}'。可用工具: {available}"

        tool = self.tools[action]
        try:
            if isinstance(params, dict):
                result = tool.execute(**params)
            elif isinstance(params, str):
                # 单参数回退：使用第一个参数名
                param_names = list(tool.parameters.get("properties", {}).keys())
                if param_names:
                    result = tool.execute(**{param_names[0]: params})
                else:
                    result = tool.execute(params)
            else:
                result = tool.execute(params)
            return str(result)
        except TypeError as e:
            return f"参数错误: {e}。工具 {action} 需要参数: {json.dumps(tool.parameters, ensure_ascii=False)}"
        except Exception as e:
            return f"执行 {action} 时出错: {e}"

    def run(self, query, verbose=True):
        """运行 Agent 处理用户查询"""
        self.messages.append({"role": "user", "content": query})
        self._consecutive_parse_failures = 0
        final_answer = None

        for iteration in range(1, config.MAX_ITERATIONS + 1):
            if verbose:
                print(f"\n{'─' * 50}")
                print(f"第 {iteration} 轮")
                print(f"{'─' * 50}")

            # 调用 LLM
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=config.TEMPERATURE,
                    max_tokens=config.MAX_TOKENS,
                )
            except Exception as e:
                print(f"[错误] API 调用失败: {e}")
                return f"API 调用失败: {e}"

            assistant_message = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": assistant_message})

            if verbose:
                print(f"\nLLM 输出:\n{assistant_message}")

            # 解析动作
            action, params = self._parse_action(assistant_message)

            if action == "final_answer":
                final_answer = params
                if verbose:
                    print(f"\n任务完成!")
                break

            if action is None:
                self._consecutive_parse_failures += 1
                if self._consecutive_parse_failures >= 1:
                    final_answer = assistant_message
                    if verbose:
                        print(f"\n未检测到 Action，当作最终回答。")
                    break
                continue

            self._consecutive_parse_failures = 0

            # 执行工具
            if verbose:
                params_str = (
                    json.dumps(params, ensure_ascii=False)
                    if isinstance(params, dict)
                    else str(params)
                )
                print(f"\n调用工具: {action}\n参数: {params_str}")

            observation = self._execute_tool(action, params)

            if verbose:
                truncated = observation[:500] + (
                    "..." if len(observation) > 500 else ""
                )
                print(f"结果: {truncated}")

            # 将观察结果反馈给 LLM
            self.messages.append(
                {"role": "user", "content": f"Observation: {observation}"}
            )

            # 管理上下文长度
            self._truncate_context()

        if final_answer is None:
            final_answer = "抱歉，我在最大迭代次数内未能完成任务。"

        return final_answer
    
    def run_stream(self, query):
        """流式运行 Agent，使用 yield 向前端抛出实时状态（生成器函数）"""
        self.messages.append({"role": "user", "content": query})
        self._consecutive_parse_failures = 0

        for iteration in range(1, config.MAX_ITERATIONS + 1):
            try:
                # 开启 stream=True
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=config.TEMPERATURE,
                    max_tokens=config.MAX_TOKENS,
                    stream=True  
                )
            except Exception as e:
                yield {"type": "error", "content": f"API 调用失败: {e}"}
                return

            full_message = ""
            # 1. 实时流式抛出 Thought 过程
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    full_message += delta
                    # 抛出当前累积的文本
                    yield {"type": "chunk", "full_text": full_message}

            self.messages.append({"role": "assistant", "content": full_message})

            # 2. 解析完整句子中的 Action
            action, params = self._parse_action(full_message)

            # 3. 任务完成
            if action == "final_answer":
                yield {"type": "final_answer", "content": params}
                break

            # 容错处理
            if action is None:
                self._consecutive_parse_failures += 1
                if self._consecutive_parse_failures >= 1:
                    yield {"type": "final_answer", "content": full_message}
                    break
                continue

            self._consecutive_parse_failures = 0

            # 4. 抛出工具调用事件
            yield {"type": "tool", "action": action, "params": params}
            
            # 执行工具
            observation = self._execute_tool(action, params)
            
            # 5. 抛出观察结果事件
            yield {"type": "observation", "content": observation}

            # 将观察结果反馈给 LLM
            self.messages.append({"role": "user", "content": f"Observation: {observation}"})
            self._truncate_context()
            
        else:
            yield {"type": "error", "content": "抱歉，我在最大迭代次数内未能完成任务。"}

    def _truncate_context(self):
        """当对话历史过长时进行裁剪，保留 system prompt + 最近的消息"""
        if len(self.messages) > config.CONTEXT_MAX_MESSAGES:
            keep = config.CONTEXT_MAX_MESSAGES - 1
            self.messages = [self.messages[0]] + self.messages[-keep:]

    def reset(self):
        """重置对话历史"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._consecutive_parse_failures = 0
