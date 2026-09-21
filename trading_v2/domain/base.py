# coding: utf-8
"""Shared validation helpers for immutable domain models."""

from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_aware_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value
