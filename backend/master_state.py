from __future__ import annotations

from typing import Literal, TypedDict

from narrative.authority import build_narrative_authority, build_scene_fallback_actions


class MasterState(TypedDict, total=False):
    mode: Literal["intro", "turn", "resolution"]
    scene: dict
    scene_title: str
    scene_lead: str
    current_scene: str
    allowed_next_scenes: list[str]
    available_monsters: list[str]
    lore_packet: dict
    character_state: dict
    inventory: list[dict]
    pending_event: dict | None
    context_hint: dict | None
    recent_reward: dict | None
    recent_messages: list[dict]
    player_message: str
    roll_resolution: dict
    fallback_actions: list[str]
    persisted_authority: dict | None
    authoritative_state: dict


class MasterGraphState(MasterState, total=False):
    mechanics_event: dict | None
    narrative_draft: str
    narrative_next_scene: str | None
    narrative_story_event: dict | None
    narrative_review_valid: bool
    narrative_review_feedback: str
    narrative_revision_attempts: int
    narrative_force_fallback: bool
    narrative_error: str
    narrative_used_fallback: bool
    approved_narration: str
    approved_next_scene: str | None
    approved_story_event: dict | None
    suggestion_draft: list[str]
    suggestion_review_valid: bool
    suggestion_review_feedback: str
    suggestion_revision_attempts: int
    suggestion_force_fallback: bool
    suggestion_error: str
    suggestion_used_fallback: bool
    suggestions_blocked: bool
    approved_suggested_actions: list[str]
    execution_trace: list[str]
    pipeline_diagnostics: list[str]
    result_narration: str
    result_event: dict | None
    result_next_scene: str | None
    result_story_event: dict | None
    result_suggested_actions: list[str]


def _parser_list(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _parser_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_scene(raw_state: dict) -> dict:
    scene = _parser_dict(raw_state.get("scene"))
    scene_key = str(raw_state.get("current_scene", "")).strip() or str(scene.get("key", "")).strip()
    scene_title = str(raw_state.get("scene_title", "")).strip() or str(scene.get("title", "")).strip()
    scene_lead = str(raw_state.get("scene_lead", "")).strip() or str(scene.get("lead", "")).strip()
    normalized_scene = {
        "key": scene_key,
        "title": scene_title,
        "lead": scene_lead,
        "type": scene.get("type"),
        "options": _parser_list(scene.get("options")),
    }
    return {key: value for key, value in normalized_scene.items() if value not in ("", None, [])}


def _normalize_state_input(state: MasterState | dict | None) -> MasterGraphState:
    raw_state = dict(state or {})
    mode = str(raw_state.get("mode", "turn")).strip().lower()
    if mode not in {"intro", "turn", "resolution"}:
        mode = "turn"

    scene = _normalize_scene(raw_state)
    current_scene = str(raw_state.get("current_scene", "")).strip() or str(scene.get("key", "")).strip()
    scene_title = str(raw_state.get("scene_title", "")).strip() or str(scene.get("title", "")).strip()
    scene_lead = str(raw_state.get("scene_lead", "")).strip() or str(scene.get("lead", "")).strip()
    normalized: MasterGraphState = {
        "mode": mode,  # type: ignore[assignment]
        "scene": scene,
        "scene_title": scene_title,
        "scene_lead": scene_lead,
        "current_scene": current_scene,
        "allowed_next_scenes": _parser_list(raw_state.get("allowed_next_scenes")),
        "available_monsters": _parser_list(raw_state.get("available_monsters")),
        "lore_packet": _parser_dict(raw_state.get("lore_packet")),
        "character_state": _parser_dict(raw_state.get("character_state")),
        "inventory": _parser_list(raw_state.get("inventory")),
        "pending_event": raw_state.get("pending_event") if isinstance(raw_state.get("pending_event"), dict) else None,
        "context_hint": raw_state.get("context_hint") if isinstance(raw_state.get("context_hint"), dict) else None,
        "recent_reward": raw_state.get("recent_reward") if isinstance(raw_state.get("recent_reward"), dict) else None,
        "persisted_authority": raw_state.get("persisted_authority")
        if isinstance(raw_state.get("persisted_authority"), dict)
        else None,
        "authoritative_state": _parser_dict(raw_state.get("authoritative_state")),
        "recent_messages": _parser_list(raw_state.get("recent_messages")),
        "player_message": str(raw_state.get("player_message", "")).strip(),
        "roll_resolution": _parser_dict(raw_state.get("roll_resolution")),
        "fallback_actions": _parser_list(raw_state.get("fallback_actions")),
        "pipeline_diagnostics": _parser_list(raw_state.get("pipeline_diagnostics")),
    }
    return normalized


def _derive_authoritative_state(state: MasterGraphState) -> dict:
    provided_authority = _parser_dict(state.get("authoritative_state"))
    if provided_authority:
        return provided_authority

    scene = _parser_dict(state.get("scene"))
    scene_key = str(state.get("current_scene", "")).strip() or str(scene.get("key", "")).strip()
    return build_narrative_authority(
        scene_key=scene_key,
        scene=scene,
        allowed_next_scenes=_parser_list(state.get("allowed_next_scenes")),
        recent_messages=_parser_list(state.get("recent_messages")),
        pending_event=state.get("pending_event") if isinstance(state.get("pending_event"), dict) else None,
        context_hint=state.get("context_hint") if isinstance(state.get("context_hint"), dict) else None,
        recent_reward=state.get("recent_reward") if isinstance(state.get("recent_reward"), dict) else None,
        inventory=_parser_list(state.get("inventory")),
        persisted_authority=state.get("persisted_authority")
        if isinstance(state.get("persisted_authority"), dict)
        else None,
    )


def _derive_fallback_actions(state: MasterGraphState, authority: dict) -> list[str]:
    provided_actions = _parser_list(state.get("fallback_actions"))
    if provided_actions:
        return provided_actions

    scene = _parser_dict(state.get("scene"))
    scene_key = str(state.get("current_scene", "")).strip() or str(scene.get("key", "")).strip()
    context_hint = state.get("context_hint") if isinstance(state.get("context_hint"), dict) else None
    return build_scene_fallback_actions(scene_key, authority, context_hint)


def prepare_master_graph_state(state: MasterState | dict | None) -> MasterGraphState:
    normalized = _normalize_state_input(state)
    authority = _derive_authoritative_state(normalized)
    fallback_actions = _derive_fallback_actions(normalized, authority)
    return {
        **normalized,
        "authoritative_state": authority,
        "fallback_actions": fallback_actions,
    }

