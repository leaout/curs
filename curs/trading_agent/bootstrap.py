# coding: utf-8
"""根据 Curs 配置组装 Trading Agent 运行时。"""

from dataclasses import replace
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from curs.trading_agent.ai_decision import (
    HoldDecisionProvider,
    StructuredDecisionProvider,
)
from curs.trading_agent.execution import (
    ExecutionEngine,
    LegacyAccountBrokerAdapter,
    PaperBrokerAdapter,
)
from curs.trading_agent.journal import TradingJournal
from curs.trading_agent.legacy_account import LegacyAccountRiskContextProvider
from curs.trading_agent.llm_providers import build_llm_completion
from curs.trading_agent.risk import RiskGate, RiskLimits
from curs.trading_agent.runtime import TradingAgentRuntime
from curs.trading_agent.strategy_spec import StrategySpec


def build_runtime(
    config: Dict[str, Any],
    account: Any,
    ai_completion: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> TradingAgentRuntime:
    agent_config = config.get('trading_agent', {})
    raw_specs = agent_config.get('strategies', ())
    specs = [StrategySpec.from_dict(item) for item in raw_specs]
    if not specs:
        raise ValueError('trading_agent.strategies requires at least one strategy')

    if ai_completion:
        decision_provider = StructuredDecisionProvider(ai_completion)
    elif agent_config.get('llm', {}).get('enabled', False):
        decision_provider = StructuredDecisionProvider(
            build_llm_completion(agent_config['llm'])
        )
    else:
        decision_provider = HoldDecisionProvider()
    limits_config = agent_config.get('risk', {})
    risk_limits = RiskLimits(
        max_single_order_value=Decimal(str(
            limits_config.get('max_single_order_value', '10000')
        )),
        max_symbol_exposure_pct=Decimal(str(
            limits_config.get('max_symbol_exposure_pct', '0.15')
        )),
        max_total_exposure_pct=Decimal(str(
            limits_config.get('max_total_exposure_pct', '0.50')
        )),
        max_positions=int(limits_config.get('max_positions', 5)),
        max_daily_loss_pct=Decimal(str(
            limits_config.get('max_daily_loss_pct', '0.02')
        )),
        max_market_data_age_seconds=int(
            limits_config.get('max_market_data_age_seconds', 90)
        ),
    )
    mode = str(agent_config.get('mode', 'observe')).strip().lower()
    if mode not in ('observe', 'paper', 'live'):
        raise ValueError('trading_agent.mode must be observe, paper, or live')
    risk_context_provider = LegacyAccountRiskContextProvider(account)
    if mode != 'live':
        risk_context_provider = _ModeRiskContextProvider(
            risk_context_provider, trading_enabled=(mode == 'paper')
        )
    broker = (
        LegacyAccountBrokerAdapter(account)
        if mode == 'live' else PaperBrokerAdapter()
    )
    account_id = _account_id(account)
    return TradingAgentRuntime(
        specs=specs,
        decision_provider=decision_provider,
        risk_context_provider=risk_context_provider,
        execution_engine=ExecutionEngine(broker),
        account_id=account_id,
        risk_gate=RiskGate(risk_limits),
        journal=TradingJournal(agent_config.get(
            'journal_file', 'data/trading_agent/events.jsonl'
        )),
    )


class _ModeRiskContextProvider:
    def __init__(self, provider, trading_enabled: bool):
        self._provider = provider
        self._trading_enabled = trading_enabled

    def __call__(self, instrument_value: str):
        context = self._provider(instrument_value)
        return replace(context, trading_enabled=self._trading_enabled)


def _account_id(account: Any) -> str:
    if getattr(account, 'account_no', None):
        return str(account.account_no)
    native_account = getattr(account, 'account', None)
    if getattr(native_account, 'account_id', None):
        return str(native_account.account_id)
    return 'default'
