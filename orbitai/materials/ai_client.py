"""AI 服务客户端。"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from orbitai.core.config import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_MAX_TOKENS,
)


def create_ai_client():
    """
    创建 AI 客户端配置。
    目前使用 DeepSeek REST API，不依赖 SDK。
    """
    if not AI_API_KEY:
        return None

    return {
        "api_key": AI_API_KEY,
        "base_url": AI_BASE_URL.rstrip("/"),
    }


def request_chat_completion(client, messages):
    """
    向 DeepSeek Chat Completions API 发起请求。
    返回模型 message.content 文本。
    """
    request_url = f"{client['base_url']}/chat/completions"

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "max_tokens": AI_MAX_TOKENS,
        "stream": False,
    }

    request_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = Request(
        request_url,
        data=request_data,
        method="POST",
        headers={
            "Authorization": f"Bearer {client['api_key']}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=60) as response:
            response_text = response.read().decode("utf-8")

    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP 错误：{error.code}，{error_body}") from error

    except URLError as error:
        raise RuntimeError(f"DeepSeek 连接错误：{error}") from error

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"DeepSeek 返回内容不是合法 JSON：{response_text}") from error

    try:
        return response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"DeepSeek 返回结构异常：{response_json}") from error
