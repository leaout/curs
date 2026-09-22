# coding: utf-8
"""Small HTTP model clients for OpenAI, DeepSeek, Claude and compatible APIs."""

import json
import os
from typing import Any, Protocol

import aiohttp

from trading_v2.config.settings import AppSettings


class ModelProviderError(RuntimeError):
    """A safe, user-displayable model request failure."""


class ModelProvider(Protocol):
    provider_name: str
    model_name: str

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    async def close(self) -> None:
        ...


class DisabledModelProvider:
    provider_name = "disabled"
    model_name = "disabled"

    async def complete_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise ModelProviderError("决策模型尚未配置；策略已保存为草稿")

    async def close(self) -> None:
        return None


class HttpModelProvider:
    def __init__(self, settings: AppSettings) -> None:
        self.provider_name = settings.model_provider
        self.model_name = settings.model_name
        self._api_key_env = settings.model_api_key_env
        self._base_url = settings.model_base_url.strip().rstrip("/")
        self._timeout = settings.model_timeout_seconds
        self._max_tokens = settings.model_max_tokens
        self._session: aiohttp.ClientSession | None = None

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        api_key = os.getenv(self._api_key_env, "").strip()
        if not api_key:
            raise ModelProviderError(f"环境变量 {self._api_key_env} 未设置")
        if self.provider_name == "anthropic":
            payload = await self._anthropic(api_key, system_prompt, user_prompt, schema)
        else:
            payload = await self._openai_compatible(
                api_key, system_prompt, user_prompt, schema
            )
        try:
            return json.loads(_strip_json_fence(payload))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ModelProviderError("模型没有返回有效 JSON") from exc

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            )
        try:
            async with self._session.post(url, headers=headers, json=body) as response:
                text = await response.text()
                if response.status >= 400:
                    raise ModelProviderError(f"模型服务返回 HTTP {response.status}")
                return json.loads(text)
        except ModelProviderError:
            raise
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelProviderError(f"模型服务请求失败: {exc}") from exc

    async def _openai_compatible(
        self,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> str:
        base_url = self._base_url or {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }.get(self.provider_name)
        if not base_url:
            raise ModelProviderError("openai_compatible 必须配置 MODEL_BASE_URL")
        response = await self._post(
            f"{base_url}/chat/completions",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"{system_prompt}\n必须只输出符合以下 JSON Schema 的 JSON："
                            f"{json.dumps(schema, ensure_ascii=False)}"
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": self._max_tokens,
            },
        )
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError("模型响应缺少 message.content") from exc

    async def _anthropic(
        self,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> str:
        base_url = self._base_url or "https://api.anthropic.com/v1"
        schema_instruction = json.dumps(schema, ensure_ascii=False)
        response = await self._post(
            f"{base_url}/messages",
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            {
                "model": self.model_name,
                "system": f"{system_prompt}\n必须只输出符合以下 JSON Schema 的 JSON：{schema_instruction}",
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": self._max_tokens,
                "temperature": 0,
            },
        )
        try:
            return "".join(
                block["text"] for block in response["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ModelProviderError("Claude 响应缺少文本内容") from exc


def _strip_json_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def build_model_provider(settings: AppSettings) -> ModelProvider:
    if not settings.model_enabled:
        return DisabledModelProvider()
    return HttpModelProvider(settings)
