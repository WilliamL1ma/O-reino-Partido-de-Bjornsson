from __future__ import annotations

# Thin request/response adapters around the canonical master graph.

from .authority import sanitize_suggested_actions


def build_master_graph_payload(
    *,
    character_state: dict,
    scene: dict,
    scene_key: str,
    mode: str,
    lore_packet: dict,
    allowed_next_scenes: list[str],
    available_monsters: list[str],
    recent_messages: list[dict],
    pending_event: dict | None,
    context_hint: dict | None,
    recent_reward: dict | None,
    inventory: list[dict] | None = None,
    persisted_authority: dict | None = None,
    player_message: str = "",
    roll_resolution: dict | None = None,
) -> dict:
    return {
        "mode": mode,
        "scene": {
            "key": scene_key,
            "title": scene["title"],
            "lead": scene["lead"],
            "type": scene.get("type"),
            "options": scene.get("options", []),
        },
        "scene_title": scene["title"],
        "scene_lead": scene["lead"],
        "current_scene": scene_key,
        "allowed_next_scenes": allowed_next_scenes,
        "available_monsters": available_monsters,
        "lore_packet": lore_packet,
        "character_state": character_state,
        "inventory": inventory or [],
        "pending_event": pending_event,
        "context_hint": context_hint,
        "recent_reward": recent_reward,
        "persisted_authority": persisted_authority,
        "recent_messages": recent_messages[-6:],
        "player_message": player_message,
        "roll_resolution": roll_resolution or {},
    }


def finalize_master_output(graph_output: dict, authority: dict, fallback_actions: list[str]) -> dict:
    result_actions = graph_output.get("result_suggested_actions")
    preserve_empty_actions = (
        isinstance(result_actions, list)
        and not result_actions
        and (
            bool(graph_output.get("suggestions_blocked"))
            or graph_output.get("result_event") is not None
            or graph_output.get("result_story_event") is not None
        )
    )

    return {
        "narration": str(graph_output.get("result_narration", "")).strip(),
        "event": graph_output.get("result_event"),
        "next_scene": graph_output.get("result_next_scene"),
        "story_event": graph_output.get("result_story_event"),
        "suggested_actions": []
        if preserve_empty_actions
        else sanitize_suggested_actions(
            result_actions,
            authority,
            fallback_actions,
        ),
    }
