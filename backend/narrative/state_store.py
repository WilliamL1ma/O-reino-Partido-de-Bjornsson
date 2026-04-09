from __future__ import annotations

import json

from database import session_scope
from models import Character

_NARRATIVE_STATE_KEY = "narrative_runtime"


def _load_json_object(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_context_hint(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    hint: dict[str, object] = {}
    kind = str(value.get("kind", "")).strip()
    monster_name = str(value.get("monster_name", "")).strip()
    if kind:
        hint["kind"] = kind
    if monster_name:
        hint["monster_name"] = monster_name
    return hint or None


def _sanitize_recent_reward(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    reward: dict[str, object] = {}
    monster_name = str(value.get("monster_name", "")).strip()
    if monster_name:
        reward["monster_name"] = monster_name

    loot_names = value.get("loot_names")
    if isinstance(loot_names, list):
        sanitized_loot = [str(item).strip() for item in loot_names if str(item).strip()]
        reward["loot_names"] = sanitized_loot

    for numeric_key in ("xp_gain", "gold_gain"):
        try:
            reward[numeric_key] = int(value.get(numeric_key, 0))
        except (TypeError, ValueError):
            reward[numeric_key] = 0

    return reward or None


def _sanitize_suggested_actions(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    actions: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in actions:
            actions.append(text)
        if len(actions) == 5:
            break
    return actions or None


def _sanitize_string_list(value: object, *, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []

    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in items:
            items.append(text)
        if len(items) == limit:
            break
    return items


def _sanitize_pending_event_truth(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    payload: dict[str, object] = {}
    for key in ("type", "attribute", "monster_name"):
        text = str(value.get(key, "")).strip()
        if text:
            payload[key] = text
    return payload or None


def _sanitize_scene_state(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    scene_state: dict[str, object] = {}
    for key in ("scene_key", "scene_type", "scene_phase", "scene_title", "scene_lead", "context_hint_kind"):
        text = str(value.get(key, "")).strip()
        if text:
            scene_state[key] = text

    allowed_next_scenes = _sanitize_string_list(value.get("allowed_next_scenes"))
    if allowed_next_scenes:
        scene_state["allowed_next_scenes"] = allowed_next_scenes

    for key in ("has_pending_event", "has_recent_reward"):
        if key in value:
            scene_state[key] = bool(value.get(key))

    return scene_state or None


def _sanitize_authority_snapshot(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    snapshot: dict[str, object] = {}
    scene_key = str(value.get("scene_key", "")).strip()
    current_target = str(value.get("current_target", "")).strip()
    interaction_mode = str(value.get("interaction_mode", "")).strip()
    interaction_type = str(value.get("interaction_type", "")).strip()
    danger_level = str(value.get("danger_level", "")).strip()
    recent_outcome = str(value.get("recent_outcome", "")).strip()
    mode_transition_signal = str(value.get("mode_transition_signal", "")).strip()
    target_source = str(value.get("target_source", "")).strip()

    if scene_key:
        snapshot["scene_key"] = scene_key
    if current_target:
        snapshot["current_target"] = current_target
    if interaction_mode:
        snapshot["interaction_mode"] = interaction_mode
    if interaction_type:
        snapshot["interaction_type"] = interaction_type
    if danger_level:
        snapshot["danger_level"] = danger_level
    if recent_outcome:
        snapshot["recent_outcome"] = recent_outcome
    if mode_transition_signal:
        snapshot["mode_transition_signal"] = mode_transition_signal
    if target_source:
        snapshot["target_source"] = target_source
    if "target_locked" in value:
        snapshot["target_locked"] = bool(value.get("target_locked"))
    if "post_combat_pending_loot" in value:
        snapshot["post_combat_pending_loot"] = bool(value.get("post_combat_pending_loot"))

    allowed_action_kinds = _sanitize_string_list(value.get("allowed_action_kinds"), limit=8)
    if allowed_action_kinds:
        snapshot["allowed_action_kinds"] = allowed_action_kinds

    recent_reward_truth = _sanitize_recent_reward(value.get("recent_reward_truth"))
    if recent_reward_truth:
        snapshot["recent_reward_truth"] = recent_reward_truth

    pending_event_truth = _sanitize_pending_event_truth(value.get("pending_event_truth"))
    if pending_event_truth:
        snapshot["pending_event_truth"] = pending_event_truth

    current_scene_state = _sanitize_scene_state(value.get("current_scene_state"))
    if current_scene_state:
        snapshot["current_scene_state"] = current_scene_state
        if "scene_phase" in current_scene_state:
            snapshot["scene_phase"] = current_scene_state["scene_phase"]

    return snapshot or None


def _make_json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]

    if isinstance(value, set):
        items = [_make_json_safe(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=True, sort_keys=True))

    return str(value)


def _sanitize_pending_roll_resolution(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    event = _make_json_safe(value.get("event"))
    roll_result = _make_json_safe(value.get("roll_result"))
    if not isinstance(event, dict) or not isinstance(roll_result, dict):
        return None

    return {
        "event": event,
        "roll_result": roll_result,
    }


def _extract_narrative_state(character: Character) -> dict:
    flags = get_story_flags(character)
    narrative_state = flags.get(_NARRATIVE_STATE_KEY)
    return narrative_state if isinstance(narrative_state, dict) else {}


def _resolve_character(character_or_id: Character | int) -> Character | None:
    if isinstance(character_or_id, Character) or not isinstance(character_or_id, int):
        return character_or_id
    with session_scope() as db_session:
        return db_session.get(Character, character_or_id)


def _update_narrative_state(
    character_id: int,
    *,
    context_hint: dict | None | object = None,
    recent_reward: dict | None | object = None,
    suggested_actions: list[str] | None | object = None,
    authority_snapshot: dict | None | object = None,
    pending_roll_resolution: dict | None | object = None,
    clear_context_hint: bool = False,
    clear_recent_reward: bool = False,
    clear_suggested_actions: bool = False,
    clear_authority_snapshot: bool = False,
    clear_pending_roll_resolution: bool = False,
) -> None:
    with session_scope() as db_session:
        db_character = db_session.get(Character, character_id)
        if db_character is None:
            return

        flags = _load_json_object(db_character.story_flags)
        runtime_state = flags.get(_NARRATIVE_STATE_KEY)
        if not isinstance(runtime_state, dict):
            runtime_state = {}

        if clear_context_hint:
            runtime_state.pop("context_hint", None)
        elif context_hint is not None:
            sanitized = _sanitize_context_hint(context_hint)
            if sanitized:
                runtime_state["context_hint"] = sanitized
            else:
                runtime_state.pop("context_hint", None)

        if clear_recent_reward:
            runtime_state.pop("recent_reward", None)
        elif recent_reward is not None:
            sanitized = _sanitize_recent_reward(recent_reward)
            if sanitized:
                runtime_state["recent_reward"] = sanitized
            else:
                runtime_state.pop("recent_reward", None)

        if clear_suggested_actions:
            runtime_state.pop("suggested_actions", None)
        elif suggested_actions is not None:
            sanitized = _sanitize_suggested_actions(suggested_actions)
            if sanitized:
                runtime_state["suggested_actions"] = sanitized
            else:
                runtime_state.pop("suggested_actions", None)

        if clear_authority_snapshot:
            runtime_state.pop("authority_snapshot", None)
        elif authority_snapshot is not None:
            sanitized = _sanitize_authority_snapshot(authority_snapshot)
            if sanitized:
                runtime_state["authority_snapshot"] = sanitized
            else:
                runtime_state.pop("authority_snapshot", None)

        if clear_pending_roll_resolution:
            runtime_state.pop("pending_roll_resolution", None)
        elif pending_roll_resolution is not None:
            sanitized = _sanitize_pending_roll_resolution(pending_roll_resolution)
            if sanitized:
                runtime_state["pending_roll_resolution"] = sanitized
            else:
                runtime_state.pop("pending_roll_resolution", None)

        if runtime_state:
            flags[_NARRATIVE_STATE_KEY] = runtime_state
        else:
            flags.pop(_NARRATIVE_STATE_KEY, None)

        db_character.story_flags = json.dumps(flags, ensure_ascii=True)


def get_story_flags(character: Character) -> dict:
    return _load_json_object(character.story_flags)


def get_story_inventory(character: Character) -> list[dict]:
    if not character.story_inventory:
        return []
    try:
        parsed = json.loads(character.story_inventory)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def get_pending_event(character: Character) -> dict | None:
    if not character.pending_event:
        return None
    try:
        parsed = json.loads(character.pending_event)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def set_pending_event(character_id: int, event_data: dict | None) -> None:
    with session_scope() as db_session:
        db_character = db_session.get(Character, character_id)
        if db_character is None:
            return
        db_character.pending_event = json.dumps(event_data, ensure_ascii=True) if event_data else None


def clear_pending_event(character_id: int) -> None:
    set_pending_event(character_id, None)


def get_context_hint(character_or_id: Character | int) -> dict | None:
    character = _resolve_character(character_or_id)
    if character is None:
        return None
    return _sanitize_context_hint(_extract_narrative_state(character).get("context_hint"))


def set_context_hint(character_id: int, hint: dict | None) -> None:
    _update_narrative_state(
        character_id,
        context_hint=hint,
        clear_context_hint=hint is None,
    )


def get_recent_reward(character_or_id: Character | int) -> dict | None:
    character = _resolve_character(character_or_id)
    if character is None:
        return None
    return _sanitize_recent_reward(_extract_narrative_state(character).get("recent_reward"))


def set_recent_reward(character_id: int, reward: dict | None) -> None:
    _update_narrative_state(
        character_id,
        recent_reward=reward,
        clear_recent_reward=reward is None,
    )


def get_suggested_actions(character_or_id: Character | int) -> list[str] | None:
    character = _resolve_character(character_or_id)
    if character is None:
        return None
    return _sanitize_suggested_actions(_extract_narrative_state(character).get("suggested_actions"))


def store_suggested_actions(character_id: int, actions: list[str]) -> None:
    _update_narrative_state(character_id, suggested_actions=actions)


def get_authority_snapshot(character_or_id: Character | int) -> dict | None:
    character = _resolve_character(character_or_id)
    if character is None:
        return None
    return _sanitize_authority_snapshot(_extract_narrative_state(character).get("authority_snapshot"))


def set_authority_snapshot(character_id: int, snapshot: dict | None) -> None:
    _update_narrative_state(
        character_id,
        authority_snapshot=snapshot,
        clear_authority_snapshot=snapshot is None,
    )


def get_pending_roll_resolution(character_or_id: Character | int) -> dict | None:
    character = _resolve_character(character_or_id)
    if character is None:
        return None
    return _sanitize_pending_roll_resolution(_extract_narrative_state(character).get("pending_roll_resolution"))


def set_pending_roll_resolution(character_id: int, payload: dict | None) -> None:
    _update_narrative_state(
        character_id,
        pending_roll_resolution=payload,
        clear_pending_roll_resolution=payload is None,
    )


def clear_pending_roll_resolution(character_id: int) -> None:
    _update_narrative_state(character_id, clear_pending_roll_resolution=True)


def persist_story_state(
    character_id: int,
    *,
    scene: str | None = None,
    act: int | None = None,
    flags: dict | None = None,
    inventory: list[dict] | None = None,
    xp_delta: int = 0,
    gold_delta: int = 0,
) -> None:
    with session_scope() as db_session:
        db_character = db_session.get(Character, character_id)
        if db_character is None:
            return

        if scene is not None:
            db_character.story_scene = scene
        if act is not None:
            db_character.story_act = act
        if flags is not None:
            db_character.story_flags = json.dumps(flags, ensure_ascii=True)
        if inventory is not None:
            db_character.story_inventory = json.dumps(inventory, ensure_ascii=True)
        if xp_delta:
            db_character.experience += xp_delta
        if gold_delta:
            db_character.gold += gold_delta
