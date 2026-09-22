# coding: utf-8
import os
import unittest
from unittest.mock import patch

from trading_v2.agent.models import strategy_json_schema
from trading_v2.agent.providers import HttpModelProvider
from trading_v2.config.settings import AppSettings


class RecordingProvider(HttpModelProvider):
    def __init__(self, settings, response):
        super().__init__(settings)
        self.response = response
        self.requests = []

    async def _post(self, url, headers, body):
        self.requests.append((url, headers, body))
        return self.response


class ModelProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_deepseek_uses_chat_completions_and_includes_schema(self) -> None:
        settings = AppSettings(
            model_enabled=True,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_api_key_env="TEST_DEEPSEEK_KEY",
            _env_file=None,
        )
        provider = RecordingProvider(settings, {
            "choices": [{"message": {"content": "```json\n{\"ok\": true}\n```"}}],
        })
        with patch.dict(os.environ, {"TEST_DEEPSEEK_KEY": "secret"}):
            result = await provider.complete_json("system", "user", strategy_json_schema())

        self.assertEqual(result, {"ok": True})
        url, headers, body = provider.requests[0]
        self.assertEqual(url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertIn("entry_rules", body["messages"][0]["content"])
        self.assertEqual(body["response_format"], {"type": "json_object"})

    async def test_anthropic_uses_messages_api_and_schema_instruction(self) -> None:
        settings = AppSettings(
            model_enabled=True,
            model_provider="anthropic",
            model_name="claude-test",
            model_api_key_env="TEST_ANTHROPIC_KEY",
            _env_file=None,
        )
        provider = RecordingProvider(settings, {
            "content": [{"type": "text", "text": "{\"ok\": true}"}],
        })
        with patch.dict(os.environ, {"TEST_ANTHROPIC_KEY": "secret"}):
            result = await provider.complete_json("system", "user", strategy_json_schema())

        self.assertEqual(result, {"ok": True})
        url, headers, body = provider.requests[0]
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "secret")
        self.assertIn("entry_rules", body["system"])


if __name__ == "__main__":
    unittest.main()
