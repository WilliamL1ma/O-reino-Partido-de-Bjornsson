from __future__ import annotations

from flask import session


def suggestion_session_key(character_id: int) -> str:
    return f"game_suggested_actions_{character_id}"


def context_hint_session_key(character_id: int) -> str:
    return f"game_context_hint_{character_id}"


def recent_reward_session_key(character_id: int) -> str:
    return f"game_recent_reward_{character_id}"


def set_context_hint(character_id: int, hint: dict | None) -> None:
    key = context_hint_session_key(character_id)
    if hint:
        session[key] = hint
    else:
        session.pop(key, None)


def get_context_hint(character_id: int) -> dict | None:
    hint = session.get(context_hint_session_key(character_id))
    return hint if isinstance(hint, dict) else None


def set_recent_reward(character_id: int, reward: dict | None) -> None:
    key = recent_reward_session_key(character_id)
    if reward:
        session[key] = reward
    else:
        session.pop(key, None)


def get_recent_reward(character_id: int) -> dict | None:
    reward = session.get(recent_reward_session_key(character_id))
    return reward if isinstance(reward, dict) else None


def store_suggested_actions(character_id: int, actions: list[str]) -> None:
    session[suggestion_session_key(character_id)] = actions[:5]


def get_suggested_actions(character_id: int) -> list[str] | None:
    actions = session.get(suggestion_session_key(character_id))
    if not isinstance(actions, list):
        return None
    sanitized = [str(item).strip() for item in actions if str(item).strip()]
    return sanitized[:5] if sanitized else None
