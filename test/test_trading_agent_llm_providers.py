# coding: utf-8
import os
import unittest
from unittest.mock import patch

from curs.trading_agent.llm_providers import (
    JsonDecisionCompletion,
    LlmConfig,
    LlmProviderError,
)


DECISION_TEXT = (
    '{"signal_id":"s1","action":"HOLD","confidence":0.8,'
    '"reason_codes":["WAIT"],"summary":"wait","position_pct":0,'
    '"limit_price":null,"valid_for_seconds":60}'
)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.data)


class LlmProviderTest(unittest.TestCase):
    def test_openai_responses(self):
        session = FakeSession({'output_text': DECISION_TEXT})
        provider = JsonDecisionCompletion(
            LlmConfig('openai', 'gpt-test', 'TEST_LLM_KEY'), session
        )
        with patch.dict(os.environ, {'TEST_LLM_KEY': 'secret'}):
            result = provider({'signal': {'signal_id': 's1'}})
        self.assertEqual('HOLD', result['action'])
        self.assertTrue(session.calls[0][0].endswith('/v1/responses'))
        self.assertEqual(
            'json_schema',
            session.calls[0][1]['json']['text']['format']['type'],
        )

    def test_deepseek_openai_compatible(self):
        session = FakeSession({
            'choices': [{'message': {'content': DECISION_TEXT}}]
        })
        provider = JsonDecisionCompletion(
            LlmConfig('deepseek', 'deepseek-chat', 'TEST_LLM_KEY'), session
        )
        with patch.dict(os.environ, {'TEST_LLM_KEY': 'secret'}):
            result = provider({'signal': {'signal_id': 's1'}})
        self.assertEqual('s1', result['signal_id'])
        self.assertTrue(session.calls[0][0].endswith('/chat/completions'))

    def test_anthropic_messages(self):
        session = FakeSession({
            'content': [{'type': 'text', 'text': DECISION_TEXT}]
        })
        provider = JsonDecisionCompletion(
            LlmConfig('anthropic', 'claude-test', 'TEST_LLM_KEY'), session
        )
        with patch.dict(os.environ, {'TEST_LLM_KEY': 'secret'}):
            result = provider({'signal': {'signal_id': 's1'}})
        self.assertEqual('HOLD', result['action'])
        self.assertEqual(
            'json_schema',
            session.calls[0][1]['json']['output_config']['format']['type'],
        )

    def test_missing_api_key_fails_before_request(self):
        session = FakeSession({})
        provider = JsonDecisionCompletion(
            LlmConfig('openai', 'gpt-test', 'MISSING_LLM_KEY'), session
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LlmProviderError):
                provider({})
        self.assertEqual([], session.calls)


if __name__ == '__main__':
    unittest.main()
