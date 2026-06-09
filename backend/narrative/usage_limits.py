from __future__ import annotations

import math
import os
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone


DEFAULT_PLAYER_MESSAGE_MAX_CHARS = 500
DEFAULT_GROQ_MAX_INPUT_TOKENS = 4000
DEFAULT_PLAYER_DAILY_MASTER_TURN_LIMIT = 40
_ESTIMATED_CHARS_PER_TOKEN = 4


def _parse_positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def get_player_message_max_chars() -> int:
    return _parse_positive_int_env("PLAYER_MESSAGE_MAX_CHARS", DEFAULT_PLAYER_MESSAGE_MAX_CHARS)


def get_groq_max_input_tokens() -> int:
    return _parse_positive_int_env("GROQ_MAX_INPUT_TOKENS", DEFAULT_GROQ_MAX_INPUT_TOKENS)


def get_player_daily_master_turn_limit() -> int:
    return _parse_positive_int_env("PLAYER_DAILY_MASTER_TURN_LIMIT", DEFAULT_PLAYER_DAILY_MASTER_TURN_LIMIT)


def estimate_text_tokens(value: object) -> int:
    text = "" if value is None else str(value)
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _ESTIMATED_CHARS_PER_TOKEN))


def _message_role(message: object) -> object:
    if isinstance(message, dict):
        return message.get("role", "")
    return getattr(message, "role", "")


def _message_content(message: object) -> object:
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def estimate_messages_tokens(messages: Iterable[object]) -> int:
    total = 0
    for message in messages:
        total += 4
        total += estimate_text_tokens(_message_role(message))
        total += estimate_text_tokens(_message_content(message))
    return total + 2 if total else 0


def daily_usage_window_start(now: datetime | None = None) -> datetime:
    resolved_now = now or datetime.now(timezone.utc)
    return resolved_now - timedelta(days=1)
