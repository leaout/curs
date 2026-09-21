# coding: utf-8
"""Domain enumerations used at API and adapter boundaries."""

from enum import Enum


class AssetClass(str, Enum):
    CN_EQUITY = "cn_equity"
    US_EQUITY = "us_equity"
    CRYPTO = "crypto"
    FX = "fx"


class TradingMode(str, Enum):
    """Controls the maximum execution authority granted to a session."""

    OBSERVE = "observe"
    PAPER = "paper"
    LIVE = "live"


class SignalSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    EXIT = "exit"


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    CREATED = "created"
    RISK_APPROVED = "risk_approved"
    RISK_REJECTED = "risk_rejected"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    SUBMIT_FAILED = "submit_failed"
    UNKNOWN = "unknown"


class RuntimePhase(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ConnectionState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
