# coding: utf-8
"""Trading Agent 的进程级生命周期和只读状态。"""

import logging
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional

from curs.trading_agent.bootstrap import build_runtime
from curs.trading_agent.qmt_bridge import QmtTradingAgentBridge

logger = logging.getLogger(__name__)


class TradingAgentService:
    _instance = None

    def __init__(self):
        self._lock = RLock()
        self._bridge = None
        self._runtime = None
        self._status = {
            'state': 'NOT_INITIALIZED',
            'enabled': False,
            'mode': 'observe',
            'provider': '',
            'model': '',
            'strategies': 0,
            'started_at': None,
            'error': '',
        }

    @classmethod
    def get_instance(cls) -> 'TradingAgentService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(
        self,
        config: Dict[str, Any],
        event_bus: Any,
        account: Optional[Any],
    ) -> bool:
        with self._lock:
            self.stop()
            agent_config = config.get('trading_agent', {})
            llm_config = agent_config.get('llm', {})
            self._status.update({
                'enabled': bool(agent_config.get('enabled', False)),
                'mode': str(agent_config.get('mode', 'observe')),
                'provider': str(llm_config.get('provider', '')),
                'model': str(llm_config.get('model', '')),
                'strategies': len(agent_config.get('strategies', ())),
                'started_at': None,
                'error': '',
            })
            if not self._status['enabled']:
                self._status['state'] = 'DISABLED'
                return False
            if str(config.get('broker', 'qmt')).lower() != 'qmt':
                self._fail('当前实时行情桥仅支持 QMT')
                return False
            if account is None:
                self._fail('没有可用交易账户；请检查 QMT 账户配置')
                return False
            try:
                self._runtime = build_runtime(config, account)
                self._bridge = QmtTradingAgentBridge(event_bus, self._runtime)
                self._bridge.start()
                self._status['state'] = 'RUNNING'
                self._status['started_at'] = datetime.now(
                    timezone.utc
                ).isoformat()
                logger.info(
                    'Trading Agent started: mode=%s strategies=%s',
                    self._status['mode'], self._status['strategies'],
                )
                return True
            except Exception as exc:
                logger.exception('Trading Agent startup failed')
                self._runtime = None
                self._bridge = None
                self._fail(str(exc))
                return False

    def stop(self) -> None:
        with self._lock:
            if self._bridge is not None:
                self._bridge.stop()
            self._bridge = None
            self._runtime = None
            if self._status['state'] == 'RUNNING':
                self._status['state'] = 'STOPPED'

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _fail(self, message: str) -> None:
        self._status['state'] = 'ERROR'
        self._status['error'] = message
