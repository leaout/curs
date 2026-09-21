# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from trading_v2.api import create_app
from trading_v2.config import AppSettings
from trading_v2.domain.market import Bar, MarketSnapshot
from trading_v2.market.provider import MarketDataHealth


class StubMarketData:
    def __init__(self) -> None:
        self.closed = False

    async def health(self) -> MarketDataHealth:
        return MarketDataHealth(healthy=True, source="stub", latency_ms=1.5)

    async def get_bars(self, instrument, timeframe, limit):
        opened = datetime(2026, 9, 21, 1, 30, tzinfo=timezone.utc)
        return [Bar(
            instrument=instrument,
            timeframe=timeframe,
            open_time=opened,
            close_time=opened + timedelta(minutes=5),
            open=Decimal("10.00"),
            high=Decimal("10.20"),
            low=Decimal("9.90"),
            close=Decimal("10.10"),
            volume=Decimal("1000"),
            source="stub",
        )][:limit]

    async def get_snapshots(self, instruments):
        now = datetime.now(timezone.utc)
        return [MarketSnapshot(
            instrument=instrument,
            last=Decimal("10.10"),
            open=None,
            high=None,
            low=None,
            prev_close=Decimal("10.00"),
            market_time=now,
            received_at=now,
            source="stub",
        ) for instrument in instruments]

    async def stream_snapshots(self, instruments):
        if False:
            yield instruments

    async def close(self) -> None:
        self.closed = True


class TradingV2ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = AppSettings(
            service_name="trading-v2-test",
            service_version="test",
            trading_mode="observe",
            _env_file=None,
        )

    def test_health_and_status_endpoints(self) -> None:
        with TestClient(create_app(settings=self.settings)) as client:
            live = client.get("/api/v2/health/live")
            ready = client.get("/api/v2/health/ready")
            status = client.get("/api/v2/status")

            self.assertEqual(live.status_code, 200)
            self.assertEqual(live.json()["service"], "trading-v2-test")
            self.assertEqual(ready.status_code, 200)
            self.assertTrue(ready.json()["ready"])
            self.assertEqual(ready.json()["phase"], "running")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["trading_mode"], "observe")
            self.assertIn("market_data", status.json()["components"])

    def test_root_and_openapi_are_standalone(self) -> None:
        with TestClient(create_app(settings=self.settings)) as client:
            root = client.get("/")
            schema = client.get("/openapi.json")

            self.assertEqual(root.status_code, 200)
            self.assertEqual(root.json()["api"], "/api/v2")
            self.assertEqual(schema.status_code, 200)
            self.assertIn("/api/v2/status", schema.json()["paths"])

    def test_market_endpoints_use_normalized_instruments(self) -> None:
        market = StubMarketData()
        with TestClient(create_app(settings=self.settings, market_data=market)) as client:
            health = client.get("/api/v2/market/status")
            bars = client.get(
                "/api/v2/market/bars",
                params={"instrument": "cn_equity:XSHG:600000", "timeframe": "5m"},
            )
            snapshots = client.post(
                "/api/v2/market/snapshots",
                json={"instruments": ["cn_equity:XSHG:600000"]},
            )

            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["source"], "stub")
            self.assertEqual(bars.status_code, 200)
            self.assertEqual(bars.json()[0]["instrument"]["venue"], "XSHG")
            self.assertEqual(snapshots.status_code, 200)
            self.assertIsNone(snapshots.json()[0]["open"])
        self.assertTrue(market.closed)

    def test_market_endpoint_rejects_invalid_instrument(self) -> None:
        with TestClient(
            create_app(settings=self.settings, market_data=StubMarketData())
        ) as client:
            response = client.get(
                "/api/v2/market/bars",
                params={"instrument": "600000"},
            )
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
