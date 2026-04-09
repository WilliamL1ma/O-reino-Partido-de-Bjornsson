from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from game_content import MONSTERS
from lore import build_lore_packet
from models import Character, GameMessage

from .authority import build_narrative_authority, build_scene_fallback_actions
from .scene_flow import allowed_next_scenes
from .state_store import (
    get_authority_snapshot,
    get_context_hint,
    get_pending_event,
    get_recent_reward,
    get_story_flags,
    get_story_inventory,
)
from .turn_pipeline import build_master_graph_payload
from .turn_pipeline import finalize_master_output


@dataclass(frozen=True)
class MasterTurnResult:
    graph_state: dict
    graph_output: dict
    payload: dict


ATTRIBUTE_FIELDS = [
    ("strength", "FOR"),
    ("dexterity", "DEX"),
    ("constitution", "CON"),
    ("intelligence", "INT"),
    ("wisdom", "SAB"),
    ("charisma", "CAR"),
    ("perception", "PER"),
]


def _compact_mapping(value: object, *, max_items: int = 8) -> dict:
    if not isinstance(value, dict):
        return {}

    compacted: dict = {}
    for key, item in value.items():
        if item in (None, "", [], {}, "nenhum"):
            continue
        compacted[str(key)] = item
        if len(compacted) >= max_items:
            break
    return compacted


def build_default_suggested_actions(
    *,
    scene_key: str,
    scene: dict,
    allowed_next_scenes: list[str],
    recent_messages: list[dict] | None = None,
    pending_event: dict | None = None,
    context_hint: dict | None = None,
    recent_reward: dict | None = None,
    inventory: list[dict] | None = None,
    persisted_authority: dict | None = None,
) -> list[str]:
    authority = build_narrative_authority(
        scene_key=scene_key,
        scene=scene,
        allowed_next_scenes=allowed_next_scenes,
        recent_messages=recent_messages or [],
        pending_event=pending_event,
        context_hint=context_hint,
        recent_reward=recent_reward,
        inventory=inventory,
        persisted_authority=persisted_authority,
    )
    return build_scene_fallback_actions(scene_key, authority, context_hint)


def _format_inventory_for_prompt(inventory: list[dict]) -> str:
    if not inventory:
        return "nenhum item relevante"
    names = [item.get("name", "item sem nome") for item in inventory[-8:]]
    return ", ".join(names)


def _truncate_text(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def build_character_state_for_master(character: Character, scene: dict, memory_summary: str | None) -> dict:
    flags = get_story_flags(character)
    inventory = get_story_inventory(character)
    pending_event = get_pending_event(character)
    context_hint = get_context_hint(character)
    recent_reward = get_recent_reward(character)
    return {
        "character_name": character.name,
        "race": character.race_name,
        "class": character.class_name,
        "personality": _truncate_text(character.personality or "", 140),
        "objective": _truncate_text(character.objective or "", 140),
        "fear": _truncate_text(character.fear or "", 140),
        "attributes": {label: getattr(character, field_name) for field_name, label in ATTRIBUTE_FIELDS},
        "xp": character.experience,
        "gold": character.gold,
        "scene": character.story_scene,
        "act": character.story_act,
        "scene_title": scene["title"],
        "scene_lead": _truncate_text(scene["lead"], 180),
        "flags": list(_compact_mapping(flags).keys())[:8],
        "inventory": _format_inventory_for_prompt(inventory),
        "memory_summary": _truncate_text(memory_summary or "Nenhum resumo consolidado ainda.", 260),
        "pending_event": _compact_mapping(pending_event, max_items=5) or "nenhum",
        "situation_hint": _compact_mapping(context_hint, max_items=5) or "nenhum",
        "recent_reward": _compact_mapping(recent_reward, max_items=5) or "nenhum",
    }


def build_master_graph_state(
    character: Character,
    scene: dict,
    recent_messages: list[GameMessage],
    memory_summary: str | None,
    *,
    mode: str,
    player_message: str = "",
    roll_resolution: dict | None = None,
) -> dict:
    current_scene = character.story_scene or "chapter_entry"
    return build_master_graph_payload(
        mode=mode,
        scene=scene,
        scene_key=current_scene,
        allowed_next_scenes=allowed_next_scenes(current_scene),
        available_monsters=list(MONSTERS.keys()),
        lore_packet=build_lore_packet(current_scene),
        character_state=build_character_state_for_master(character, scene, memory_summary),
        recent_messages=[{"role": msg.role, "content": _truncate_text(msg.content, 280)} for msg in recent_messages[-4:]],
        pending_event=get_pending_event(character),
        context_hint=get_context_hint(character),
        recent_reward=get_recent_reward(character),
        inventory=get_story_inventory(character),
        persisted_authority=get_authority_snapshot(character),
        player_message=player_message,
        roll_resolution=roll_resolution or {},
    )


def invoke_and_finalize_master_graph(
    graph_state: dict,
    graph_runner: Callable[[dict], dict],
) -> MasterTurnResult:
    graph_output = graph_runner(graph_state)
    payload = finalize_master_output(
        graph_output,
        graph_state.get("authoritative_state", {}),
        graph_state.get("fallback_actions", []),
    )
    return MasterTurnResult(
        graph_state=graph_state,
        graph_output=graph_output,
        payload=payload,
    )
