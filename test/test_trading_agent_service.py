# coding: utf-8
import unittest

from curs.trading_agent.execution import PaperBrokerAdapter
from curs.trading_agent.service import TradingAgentService


class TradingAgentServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = TradingAgentService()

    def test_disabled_configuration_is_safe(self):
        started = self.service.start(
            {'trading_agent': {'enabled': False}}, object(), None
        )
        self.assertFalse(started)
        self.assertEqual('DISABLED', self.service.status()['state'])

    def test_enabled_configuration_requires_account(self):
        started = self.service.start(
            {
                'broker': 'qmt',
                'trading_agent': {
                    'enabled': True,
                    'mode': 'observe',
                    'strategies': [],
                },
            },
            object(),
            None,
        )
        self.assertFalse(started)
        status = self.service.status()
        self.assertEqual('ERROR', status['state'])
        self.assertIn('账户配置', status['error'])

    def test_observe_mode_starts_qmt_bridge(self):
        class FakeBus:
            def __init__(self):
                self.listeners = []

            def add_listener(self, event_type, listener):
                self.listeners.append((event_type, listener))

            def del_listener(self, event_type, listener):
                self.listeners.remove((event_type, listener))

        bus = FakeBus()
        config = {
            'broker': 'qmt',
            'trading_agent': {
                'enabled': True,
                'mode': 'observe',
                'llm': {'enabled': False},
                'strategies': [{
                    'id': 'smoke',
                    'timeframe': '5m',
                    'market': {'asset_classes': ['CN_EQUITY']},
                    'trigger': {'all': [{
                        'field': 'close', 'operator': 'gt', 'value': 0,
                    }]},
                }],
            },
        }
        self.assertTrue(self.service.start(config, bus, object()))
        self.assertEqual('RUNNING', self.service.status()['state'])
        self.assertEqual(1, len(bus.listeners))
        self.service.stop()
        self.assertEqual([], bus.listeners)

    def test_status_does_not_contain_api_key(self):
        self.service.start(
            {
                'trading_agent': {
                    'enabled': False,
                    'llm': {
                        'provider': 'openai',
                        'model': 'test-model',
                        'api_key': 'must-not-leak',
                    },
                }
            },
            object(),
            None,
        )
        self.assertNotIn('api_key', self.service.status())
        self.assertNotIn('must-not-leak', str(self.service.status()))

    def test_paper_broker_never_needs_real_account(self):
        broker = PaperBrokerAdapter()
        self.assertEqual([], broker.orders)


if __name__ == '__main__':
    unittest.main()
