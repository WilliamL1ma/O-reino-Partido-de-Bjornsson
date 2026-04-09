from __future__ import annotations

from typing import Literal, TypedDict

from master_pipeline import invoke_master_pipeline


class MasterState(TypedDict, total=False):
    mode: Literal["intro", "turn", "resolution"]
    scene_title: str
    scene_lead: str
    current_scene: str
    allowed_next_scenes: list[str]
    available_monsters: list[str]
    lore_packet: dict
    character_state: dict
    recent_messages: list[dict]
    player_message: str
    roll_resolution: dict
    fallback_actions: list[str]
    authoritative_state: dict


def invoke_master_graph(state: MasterState) -> dict:
    return invoke_master_pipeline(state)
