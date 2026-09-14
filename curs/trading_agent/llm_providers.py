# coding: utf-8
"""主流大模型的统一 JSON 决策调用层。"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:  # pragma: no cover - 生产依赖缺失时由构造器给出明确错误
    requests = None


DECISION_JSON_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'signal_id': {'type': 'string'},
        'action': {
            'type': 'string',
            'enum': ['BUY', 'SELL', 'REDUCE', 'HOLD', 'CANCEL'],
        },
        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'reason_codes': {
            'type': 'array',
            'items': {'type': 'string'},
            'maxItems': 8,
        },
        'summary': {'type': 'string'},
        'position_pct': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'limit_price': {'type': ['number', 'null']},
        'valid_for_seconds': {'type': 'integer', 'minimum': 1},
    },
    'required': [
        'signal_id', 'action', 'confidence', 'reason_codes', 'summary',
        'position_pct', 'limit_price', 'valid_for_seconds',
    ],
}

SYSTEM_PROMPT = """You are the decision component of an automated trading system.
Return only one JSON object matching the supplied schema. Evaluate only the given
candidate signal and account context. Never invent prices, positions, or market
facts. Use HOLD when data is insufficient, stale, conflicting, or uncertain.
Risk controls outside the model have final authority. Keep the explanation short.
"""


class LlmProviderError(RuntimeError):
    """模型配置、网络或响应解析错误。"""


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key_env: str
    base_url: str = ''
    timeout_seconds: float = 8.0
    max_retries: int = 1
    max_output_tokens: int = 800
    temperature: float = 0.0

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> 'LlmConfig':
        provider = str(raw.get('provider', '')).strip().lower()
        model = str(raw.get('model', '')).strip()
        if not provider or not model:
            raise ValueError('trading_agent.llm requires provider and model')
        default_key_env = {
            'openai': 'OPENAI_API_KEY',
            'deepseek': 'DEEPSEEK_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'claude': 'ANTHROPIC_API_KEY',
        }.get(provider, 'LLM_API_KEY')
        return cls(
            provider=provider,
            model=model,
            api_key_env=str(raw.get('api_key_env', default_key_env)),
            base_url=str(raw.get('base_url', '')).rstrip('/'),
            timeout_seconds=float(raw.get('timeout_seconds', 8)),
            max_retries=int(raw.get('max_retries', 1)),
            max_output_tokens=int(raw.get('max_output_tokens', 800)),
            temperature=float(raw.get('temperature', 0)),
        )


class JsonDecisionCompletion:
    """供 StructuredDecisionProvider 使用的可调用对象。"""

    def __init__(
        self,
        config: LlmConfig,
        session: Optional[Any] = None,
    ):
        self.config = config
        if session is not None:
            self._session = session
        elif requests is not None:
            self._session = requests.Session()
        else:
            raise LlmProviderError(
                'requests is required for live LLM calls; install requirements.txt'
            )

    def __call__(self, context: Dict[str, Any]) -> Dict[str, Any]:
        api_key = os.environ.get(self.config.api_key_env, '').strip()
        if not api_key:
            raise LlmProviderError(
                f'missing API key environment variable: {self.config.api_key_env}'
            )
        if self.config.provider == 'openai':
            return self._openai_responses(context, api_key)
        if self.config.provider in ('anthropic', 'claude'):
            return self._anthropic_messages(context, api_key)
        if self.config.provider in ('deepseek', 'openai_compatible'):
            return self._openai_compatible(context, api_key)
        raise LlmProviderError(f'unsupported LLM provider: {self.config.provider}')

    def _openai_responses(
        self, context: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        base_url = self.config.base_url or 'https://api.openai.com/v1'
        body = {
            'model': self.config.model,
            'instructions': SYSTEM_PROMPT,
            'input': json.dumps(context, ensure_ascii=False),
            'max_output_tokens': self.config.max_output_tokens,
            'store': False,
            'text': {
                'format': {
                    'type': 'json_schema',
                    'name': 'trading_decision',
                    'strict': True,
                    'schema': DECISION_JSON_SCHEMA,
                }
            },
        }
        data = self._post(
            f'{base_url}/responses',
            {'Authorization': f'Bearer {api_key}'},
            body,
        )
        text = data.get('output_text') or _openai_output_text(data)
        return _parse_json_object(text)

    def _openai_compatible(
        self, context: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        default_url = 'https://api.deepseek.com' if (
            self.config.provider == 'deepseek'
        ) else ''
        base_url = self.config.base_url or default_url
        if not base_url:
            raise LlmProviderError('openai_compatible provider requires base_url')
        body = {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': 'Return JSON for this context:\n' + json.dumps(
                        context, ensure_ascii=False
                    ),
                },
            ],
            'response_format': {'type': 'json_object'},
            'max_tokens': self.config.max_output_tokens,
            'temperature': self.config.temperature,
        }
        data = self._post(
            f'{base_url}/chat/completions',
            {'Authorization': f'Bearer {api_key}'},
            body,
        )
        try:
            text = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError('invalid OpenAI-compatible response') from exc
        return _parse_json_object(text)

    def _anthropic_messages(
        self, context: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        base_url = self.config.base_url or 'https://api.anthropic.com/v1'
        body = {
            'model': self.config.model,
            'system': SYSTEM_PROMPT,
            'messages': [{
                'role': 'user',
                'content': json.dumps(context, ensure_ascii=False),
            }],
            'max_tokens': self.config.max_output_tokens,
            'temperature': self.config.temperature,
            'output_config': {
                'format': {
                    'type': 'json_schema',
                    'schema': DECISION_JSON_SCHEMA,
                }
            },
        }
        data = self._post(
            f'{base_url}/messages',
            {'x-api-key': api_key, 'anthropic-version': '2023-06-01'},
            body,
        )
        try:
            text = next(
                item['text'] for item in data['content']
                if item.get('type') == 'text'
            )
        except (KeyError, StopIteration, TypeError) as exc:
            raise LlmProviderError('invalid Anthropic response') from exc
        return _parse_json_object(text)

    def _post(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        headers = {'Content-Type': 'application/json', **headers}
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._session.post(
                    url, headers=headers, json=body,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise LlmProviderError('LLM response must be a JSON object')
                return data
            except Exception as exc:
                if isinstance(exc, LlmProviderError):
                    raise
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
        raise LlmProviderError(f'LLM request failed: {last_error}') from last_error


def build_llm_completion(
    raw_config: Dict[str, Any],
    session: Optional[Any] = None,
) -> JsonDecisionCompletion:
    return JsonDecisionCompletion(LlmConfig.from_dict(raw_config), session)


def _parse_json_object(value: Any) -> Dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise LlmProviderError('LLM returned empty content')
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise LlmProviderError('LLM returned invalid JSON') from exc
    if not isinstance(data, dict):
        raise LlmProviderError('LLM decision must be a JSON object')
    return data


def _openai_output_text(data: Dict[str, Any]) -> str:
    """兼容 Responses REST 返回的 output/content 结构。"""
    try:
        for output in data.get('output', ()):
            for content in output.get('content', ()):
                if content.get('type') == 'output_text':
                    return content['text']
    except (KeyError, TypeError):
        pass
    raise LlmProviderError('invalid OpenAI Responses response')
