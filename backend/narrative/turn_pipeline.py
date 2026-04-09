from __future__ import annotations

from narrative.authority import build_narrative_authority, build_scene_fallback_actions, sanitize_suggested_actions


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
    authority = build_narrative_authority(
        scene_key=scene_key,
        scene=scene,
        allowed_next_scenes=allowed_next_scenes,
        recent_messages=recent_messages,
        pending_event=pending_event,
        context_hint=context_hint,
        recent_reward=recent_reward,
        inventory=inventory,
        persisted_authority=persisted_authority,
    )
    fallback_actions = build_scene_fallback_actions(scene_key, authority, context_hint)

    return {
        "mode": mode,
        "scene_title": scene["title"],
        "scene_lead": scene["lead"],
        "current_scene": scene_key,
        "allowed_next_scenes": allowed_next_scenes,
        "available_monsters": available_monsters,
        "lore_packet": lore_packet,
        "fallback_actions": fallback_actions,
        "character_state": character_state,
        "authoritative_state": authority,
        "recent_messages": recent_messages[-6:],
        "player_message": player_message,
        "roll_resolution": roll_resolution or {},
    }


def finalize_master_output(graph_output: dict, authority: dict, fallback_actions: list[str]) -> dict:
    return {
        "narration": str(graph_output.get("result_narration", "")).strip(),
        "event": graph_output.get("result_event"),
        "next_scene": graph_output.get("result_next_scene"),
        "story_event": graph_output.get("result_story_event"),
        "suggested_actions": sanitize_suggested_actions(
            graph_output.get("result_suggested_actions"),
            authority,
            fallback_actions,
        ),
    }
