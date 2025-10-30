import requests
import json
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
)  # 引入重试机制


class StreamingAgent:

    def __init__(
            self,
            role: str,
            api_key: str = "f61ov1gbo76awnl3z4rz1a8ltiykrg6c",
            model: str = "gemini-1.5-pro",
            api_base: str = "https://autobak.zaiwen.top/api/v1/chat/completions"
    ):
        """
        初始化Agent
        
        参数:
            role (str): 系统角色提示（用于设置system prompt）
            api_key (str): API访问密钥
            model (str): 使用的模型名称（默认Claude模型）
            api_base (str): API接口地址（默认用户提供的地址）
        """
        self.role = role
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    @retry(
        wait=wait_random_exponential(min=1, max=30),  # 指数退避等待
        stop=stop_after_attempt(5),  # 最大重试5次
        reraise=True  # 重新抛出最终异常
    )
    def chat(self, user_message: str) -> str:
        """
        发送聊天请求并获取流式响应内容
        
        参数:
            user_message (str): 用户输入的消息
        
        返回:
            str: 完整的模型响应内容
        """
        # 构造完整对话消息（包含系统角色）
        messages = [{
            "role": "system",
            "content": self.role
        }, {
            "role": "user",
            "content": user_message
        }]

        # 构造请求体
        payload = {
            "messages": messages,
            "model": self.model,
            "stream": True  # 强制启用流式响应
        }

        full_response = ""  # 累积完整回答

        while True:
            try:
                # 发送流式请求
                with requests.post(self.api_base,
                                   headers=self.headers,
                                   json=payload,
                                   stream=True) as response:
                    response.raise_for_status()  # 检查HTTP错误状态码

                    # 逐行解析SSE流式响应
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data_str = line[len("data: "):]

                            # 处理结束标记
                            if data_str == "[DONE]":
                                break

                            # 解析JSON数据块
                            try:
                                chunk = json.loads(data_str)
                                content = self._extract_content(chunk)

                                if content:
                                    full_response += content

                            except json.JSONDecodeError as e:
                                print(f"JSON解析错误: {e} | 原始数据: {data_str}")
                                continue

            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}")
                continue
                # raise  # 重新抛出异常以触发重试机制

            if full_response == 'null':
                print('通讯异常')
                full_response = ""  # 累积完整回答

            if full_response != "":
                break

        return full_response

    def _extract_content(self, chunk: dict) -> str:
        """
        从响应块中提取有效内容（可根据API返回结构调整）
        """
        if "choices" in chunk and len(chunk["choices"]) > 0:
            delta = chunk["choices"][0].get("delta", {})
            return delta.get("content", "")
        return ""


# 示例用法
if __name__ == "__main__":
    # 配置参数
    SYSTEM_PROMPT = "你是一个专业的智能助手，回答需简洁明了"
    API_KEY = "f61ov1gbo76awnl3z4rz1a8ltiykrg6c"
    MODEL_NAME = "llama-3.1-405b-instruct"

    # 初始化Agent
    agent = StreamingAgent(role=SYSTEM_PROMPT,
                           api_key=API_KEY,
                           model=MODEL_NAME)

    # 发送请求并获取响应
    try:
        response = agent.chat("请介绍一下大语言模型的发展历程")
        print("\n完整响应:\n", response)
    except Exception as e:
        print(f"最终错误: {e}")
