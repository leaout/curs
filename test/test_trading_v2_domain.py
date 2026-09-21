# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError

from trading_v2.domain import (
    AssetClass,
    Bar,
    Decision,
    DecisionAction,
    InstrumentId,
    MarketSnapshot,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Signal,
    SignalSide,
    TradingMode,
)


class TradingV2DomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.instrument = InstrumentId(
            symbol="600000",
            venue="xshg",
            asset_class=AssetClass.CN_EQUITY,
        )
        self.now = datetime.now(timezone.utc)

    def test_instrument_id_is_normalized_and_canonical(self) -> None:
        self.assertEqual(self.instrument.venue, "XSHG")
        self.assertEqual(
            self.instrument.canonical,
            "cn_equity:XSHG:600000",
        )

    def test_bar_validates_price_range_and_timezone(self) -> None:
        bar = Bar(
            instrument=self.instrument,
            timeframe="1m",
            open_time=self.now,
            close_time=self.now + timedelta(minutes=1),
            open=Decimal("10.00"),
            high=Decimal("10.20"),
            low=Decimal("9.90"),
            close=Decimal("10.10"),
            volume=Decimal("1000"),
            source="cpptdx",
        )
        self.assertTrue(bar.is_closed)

        with self.assertRaises(ValidationError):
            Bar(
                instrument=self.instrument,
                timeframe="1m",
                open_time=self.now,
                close_time=self.now + timedelta(minutes=1),
                open=Decimal("10.00"),
                high=Decimal("9.95"),
                low=Decimal("9.90"),
                close=Decimal("10.10"),
                source="cpptdx",
            )

        with self.assertRaises(ValidationError):
            Bar(
                instrument=self.instrument,
                timeframe="1m",
                open_time=datetime.now(),
                close_time=datetime.now() + timedelta(minutes=1),
                open=Decimal("10"),
                high=Decimal("10"),
                low=Decimal("10"),
                close=Decimal("10"),
                source="cpptdx",
            )

    def test_market_snapshot_rejects_crossed_quote(self) -> None:
        with self.assertRaises(ValidationError):
            MarketSnapshot(
                instrument=self.instrument,
                last=Decimal("10.10"),
                open=Decimal("10.00"),
                high=Decimal("10.20"),
                low=Decimal("9.90"),
                prev_close=Decimal("9.95"),
                bid=Decimal("10.12"),
                ask=Decimal("10.11"),
                market_time=self.now,
                source="cpptdx",
            )

    def test_signal_expiry_must_follow_creation(self) -> None:
        with self.assertRaises(ValidationError):
            Signal(
                session_id=uuid4(),
                strategy_version=1,
                instrument=self.instrument,
                timeframe="5m",
                side=SignalSide.BUY,
                strength=0.8,
                reason="breakout",
                bar_time=self.now,
                created_at=self.now,
                expires_at=self.now,
            )

    def test_decision_enforces_action_and_order_contract(self) -> None:
        common = {
            "signal_id": uuid4(),
            "session_id": uuid4(),
            "strategy_version": 1,
            "confidence": 0.8,
            "rationale": "wait for confirmation",
            "model_provider": "openai",
            "model_name": "test-model",
            "prompt_version": "v1",
        }
        decision = Decision(action=DecisionAction.HOLD, **common)
        self.assertEqual(decision.quantity, Decimal("0"))

        with self.assertRaises(ValidationError):
            Decision(
                action=DecisionAction.BUY,
                quantity=Decimal("100"),
                order_type=OrderType.LIMIT,
                **common,
            )

    def test_order_requires_limit_price_and_valid_fill(self) -> None:
        common = {
            "client_order_id": "client-1",
            "session_id": uuid4(),
            "signal_id": uuid4(),
            "decision_id": uuid4(),
            "instrument": self.instrument,
            "side": OrderSide.BUY,
            "quantity": Decimal("100"),
            "mode": TradingMode.PAPER,
        }
        order = Order(
            order_type=OrderType.LIMIT,
            limit_price=Decimal("10.10"),
            status=OrderStatus.CREATED,
            **common,
        )
        self.assertEqual(order.filled_quantity, Decimal("0"))

        with self.assertRaises(ValidationError):
            Order(
                order_type=OrderType.MARKET,
                filled_quantity=Decimal("101"),
                **common,
            )


if __name__ == "__main__":
    unittest.main()
