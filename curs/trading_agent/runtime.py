# coding: utf-8
"""候选信号 → AI 决策 → 风控 → 执行的实时编排器。"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from queue import Empty, Queue
from threading import Thread
from typing import Callable, Dict, Iterable, List, Optional

from curs.domain.models import Action, Bar, Decision
from curs.markets.profiles import MarketRegistry
from curs.trading_agent.ai_decision import (
    DecisionProvider,
    build_decision_context,
    validate_decision,
)
from curs.trading_agent.allocator import CapitalAllocator
from curs.trading_agent.deduplicator import SignalDeduplicator
from curs.trading_agent.execution import ExecutionEngine, ExecutionResult
from curs.trading_agent.indicator_engine import IndicatorEngine
from curs.trading_agent.journal import TradingJournal
from curs.trading_agent.risk import RiskContext, RiskGate, RiskResult
from curs.trading_agent.signal_detector import SignalDetector
from curs.trading_agent.strategy_spec import StrategySpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeOutcome:
    strategy_id: str
    signal_id: str
    decision: Optional[Decision] = None
    risk_result: Optional[RiskResult] = None
    execution_result: Optional[ExecutionResult] = None
    status: str = ''


class TradingAgentRuntime:
    def __init__(
        self,
        specs: Iterable[StrategySpec],
        decision_provider: DecisionProvider,
        risk_context_provider: Callable[[str], RiskContext],
        execution_engine: ExecutionEngine,
        account_id: str,
        market_registry: MarketRegistry = None,
        risk_gate: RiskGate = None,
        journal: TradingJournal = None,
    ):
        self._specs = tuple(specs)
        self._decision_provider = decision_provider
        self._risk_context_provider = risk_context_provider
        self._execution_engine = execution_engine
        self._account_id = account_id
        self._market_registry = market_registry or MarketRegistry.defaults()
        self._risk_gate = risk_gate or RiskGate()
        self._journal = journal or TradingJournal()
        self._indicators = IndicatorEngine()
        self._detector = SignalDetector()
        self._deduplicator = SignalDeduplicator()
        self._allocator = CapitalAllocator()

    def on_bar(self, bar: Bar) -> List[RuntimeOutcome]:
        """处理一根闭合 K 线；任何异常都不会越过风控直接下单。"""
        try:
            features = self._indicators.update(bar)
        except Exception:
            logger.exception('Trading Agent indicator update failed')
            return []

        outcomes = []
        for spec in self._specs:
            try:
                outcome = self._process_spec(spec, bar, features)
            except Exception as exc:
                logger.exception('Trading Agent strategy runtime failed: %s', spec.strategy_id)
                self._journal.append('RUNTIME_ERROR', {
                    'strategy_id': spec.strategy_id,
                    'instrument': str(bar.instrument),
                    'error': str(exc),
                })
                outcome = RuntimeOutcome(
                    strategy_id=spec.strategy_id,
                    signal_id='',
                    status='RUNTIME_ERROR',
                )
            if outcome is not None:
                outcomes.append(outcome)
        return outcomes

    def _process_spec(
        self,
        spec: StrategySpec,
        bar: Bar,
        features: Dict[str, Decimal],
    ) -> Optional[RuntimeOutcome]:
        signal = self._detector.detect(spec, bar, features)
        if signal is None:
            return None
        if not self._deduplicator.accept(signal, spec.ai_decision.cooldown_seconds):
            return RuntimeOutcome(spec.strategy_id, signal.signal_id, status='DEDUPLICATED')

        self._journal.append('CANDIDATE_SIGNAL', signal)
        risk_context = self._risk_context_provider(str(signal.instrument))
        try:
            decision = self._make_decision(spec, signal, risk_context)
            validate_decision(decision, signal, spec, datetime.now(timezone.utc))
        except Exception as exc:
            logger.exception('Trading Agent AI decision rejected')
            self._journal.append('DECISION_ERROR', {
                'signal_id': signal.signal_id,
                'error': str(exc),
            })
            return RuntimeOutcome(spec.strategy_id, signal.signal_id, status='DECISION_ERROR')

        self._journal.append('AI_DECISION', decision)
        if decision.action in (Action.HOLD, Action.CANCEL):
            return RuntimeOutcome(
                spec.strategy_id,
                signal.signal_id,
                decision=decision,
                status=decision.action.value,
            )

        market = self._market_registry.get(signal.instrument)
        intent = self._allocator.create_intent(
            decision,
            signal,
            spec,
            market,
            risk_context,
            self._account_id,
        )
        if intent is None:
            self._journal.append('INTENT_REJECTED', {
                'signal_id': signal.signal_id,
                'reason': 'NO_EXECUTABLE_QUANTITY',
            })
            return RuntimeOutcome(
                spec.strategy_id,
                signal.signal_id,
                decision=decision,
                status='NO_EXECUTABLE_QUANTITY',
            )

        risk_result = self._risk_gate.evaluate(intent, risk_context)
        self._journal.append('RISK_DECISION', {
            'intent': intent,
            'result': risk_result,
        })
        if not risk_result.approved:
            return RuntimeOutcome(
                spec.strategy_id,
                signal.signal_id,
                decision=decision,
                risk_result=risk_result,
                status='RISK_REJECTED',
            )

        execution_result = self._execution_engine.execute(intent)
        self._journal.append('EXECUTION_RESULT', {
            'intent': intent,
            'result': execution_result,
        })
        return RuntimeOutcome(
            spec.strategy_id,
            signal.signal_id,
            decision=decision,
            risk_result=risk_result,
            execution_result=execution_result,
            status='ORDER_SUBMITTED' if execution_result.accepted else 'ORDER_REJECTED',
        )

    def _make_decision(self, spec, signal, risk_context) -> Decision:
        if not spec.ai_decision.enabled:
            return Decision(
                signal_id=signal.signal_id,
                action=Action.BUY,
                confidence=Decimal('1'),
                position_pct=spec.position.allocation_pct,
                reason_codes=('RULE_ONLY_STRATEGY',),
                valid_for_seconds=spec.ai_decision.decision_ttl_seconds,
            )
        account_context = {
            'total_equity': str(risk_context.total_equity),
            'available_cash': str(risk_context.available_cash),
            'total_exposure': str(risk_context.total_exposure),
            'daily_pnl': str(risk_context.daily_pnl),
            'positions_count': risk_context.positions_count,
        }
        context = build_decision_context(signal, spec, account_context)
        result_queue = Queue(maxsize=1)

        def request_decision():
            try:
                result_queue.put((True, self._decision_provider.decide(context)))
            except Exception as exc:
                result_queue.put((False, exc))

        worker = Thread(
            target=request_decision,
            name=f'ai-decision-{spec.strategy_id}',
            daemon=True,
        )
        worker.start()
        try:
            success, result = result_queue.get(timeout=spec.ai_decision.timeout_seconds)
        except Empty as exc:
            raise TimeoutError(
                f'AI decision timed out after {spec.ai_decision.timeout_seconds}s'
            ) from exc
        if not success:
            raise result
        return result
