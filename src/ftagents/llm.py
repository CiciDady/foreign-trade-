"""可插拔 LLM 层(OpenAI 兼容,默认指向 DeepSeek)。

设计原则:LLM 仅用于"锦上添花"的自然语言总结,核心决策由确定性规则负责。
因此当没有配置 API key 时,``LLMClient.available`` 返回 False,
上层会自动降级为模板化摘要,整个闭环依然可以完整跑通。

支持的环境变量:
- ``FTAGENTS_LLM_API_KEY`` 或 ``DEEPSEEK_API_KEY`` 或 ``OPENAI_API_KEY``
- ``FTAGENTS_LLM_BASE_URL`` (默认 ``https://api.deepseek.com/v1``)
- ``FTAGENTS_LLM_MODEL``    (默认 ``deepseek-chat``)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_API_KEY_ENVS = ("FTAGENTS_LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")
_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


class LLMClient:
    def __init__(self) -> None:
        self.api_key = next(
            (os.environ[e] for e in _API_KEY_ENVS if os.environ.get(e)), None
        )
        self.base_url = os.environ.get("FTAGENTS_LLM_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
        self.model = os.environ.get("FTAGENTS_LLM_MODEL", _DEFAULT_MODEL)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, *, timeout: float = 30.0) -> str | None:
        """调用 chat completions;失败或未配置时返回 None(触发降级)。"""

        if not self.available:
            return None
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是资深跨境外贸顾问,输出简洁、务实的中文结论。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "stream": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
            return None
