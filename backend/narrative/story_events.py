from __future__ import annotations

from dataclasses import dataclass

from game_content import CHAPTER_SCENES, MONSTERS
from models import Character

from .action_rolls import ATTRIBUTE_LABELS, choose_roll_attribute, class_prefers_magic_combat
from .scene_flow import get_encounter_transition


@dataclass(frozen=True)
class AppliedStoryEvent:
    scene_key: str
    act: int
    pending_event: dict
    authority_snapshot: dict | None


def _build_authority_snapshot(authority: dict, event: dict) -> dict | None:
    if not isinstance(authority, dict):
        authority = {}

    snapshot = dict(authority)
    monster_name = str(event.get("monster_name", "")).strip()
    if monster_name:
        snapshot["current_target"] = monster_name
        snapshot["target_source"] = "pending_event"

    snapshot["interaction_mode"] = "roll_pending"
    snapshot["interaction_type"] = "roll_pending"
    snapshot["recent_outcome"] = "awaiting_roll"
    snapshot["mode_transition_signal"] = "pending_roll"
    snapshot["danger_level"] = "high"
    snapshot["allowed_action_kinds"] = ["combat", "defend", "escape", "observe"]
    snapshot["target_locked"] = bool(monster_name)
    snapshot["post_combat_pending_loot"] = False
    snapshot["pending_event_truth"] = {
        "type": event.get("type"),
        "attribute": event.get("attribute"),
        "monster_name": monster_name,
    }

    current_scene_state = snapshot.get("current_scene_state")
    if not isinstance(current_scene_state, dict):
        current_scene_state = {}
    current_scene_state["has_pending_event"] = True
    current_scene_state["has_recent_reward"] = False
    current_scene_state["scene_phase"] = "roll_pending"
    snapshot["current_scene_state"] = current_scene_state
    snapshot["scene_phase"] = "roll_pending"
    return snapshot or None


def sanitize_story_event(
    raw_story_event: object,
    *,
    allowed_next_scenes: list[str],
    available_monsters: list[str],
) -> dict | None:
    if not isinstance(raw_story_event, dict):
        return None

    event_type = str(raw_story_event.get("type", "")).strip().lower()
    if event_type != "forced_encounter":
        return None

    scene_key = str(raw_story_event.get("scene", "")).strip()
    if not scene_key or scene_key not in allowed_next_scenes:
        return None

    transition = get_encounter_transition(scene_key)
    if not transition:
        return None

    inferred_monster = str(transition.get("monster", "")).strip().lower()
    monster_slug = str(raw_story_event.get("monster_slug", "")).strip().lower() or inferred_monster
    if not monster_slug or monster_slug not in available_monsters or monster_slug != inferred_monster:
        return None

    trigger_text = str(raw_story_event.get("trigger_text", "")).strip()
    payload = {
        "type": "forced_encounter",
        "scene": scene_key,
        "monster_slug": monster_slug,
    }
    if trigger_text:
        payload["trigger_text"] = trigger_text[:260]
    return payload


def story_event_from_next_scene(
    next_scene: str | None,
    *,
    allowed_next_scenes: list[str],
    available_monsters: list[str],
) -> dict | None:
    scene_key = str(next_scene or "").strip()
    if not scene_key.startswith("encounter_"):
        return None
    return sanitize_story_event(
        {"type": "forced_encounter", "scene": scene_key},
        allowed_next_scenes=allowed_next_scenes,
        available_monsters=available_monsters,
    )


def apply_story_event(
    character: Character,
    story_event: dict | None,
    authority: dict,
) -> AppliedStoryEvent | None:
    if not isinstance(story_event, dict):
        return None

    event_type = str(story_event.get("type", "")).strip().lower()
    if event_type != "forced_encounter":
        return None

    scene_key = str(story_event.get("scene", "")).strip()
    transition = get_encounter_transition(scene_key)
    if not transition:
        return None

    monster_slug = str(story_event.get("monster_slug", "")).strip().lower() or str(transition.get("monster", "")).strip().lower()
    if monster_slug not in MONSTERS:
        return None

    monster = MONSTERS[monster_slug]
    action_kind = "combat_magic" if class_prefers_magic_combat(character) else "combat"
    attribute = choose_roll_attribute(character, action_kind)
    difficulty = max(8, min(int(monster.get("dc", 13)), 20))
    pending_event = {
        "type": "encounter",
        "attribute": attribute,
        "difficulty": difficulty,
        "roll_type": f"{'ataque magico' if action_kind == 'combat_magic' else 'ataque'} ({ATTRIBUTE_LABELS[attribute]})",
        "label": ATTRIBUTE_LABELS[attribute],
        "stakes": f"O choque com {monster['name']} precisa ser resolvido no dado antes de definir quem toma o controle da cena.",
        "action_kind": action_kind,
        "player_intent": "reagir ao encontro repentino",
        "monster_slug": monster_slug,
        "monster_name": monster["name"],
    }
    authority_snapshot = _build_authority_snapshot(authority, pending_event)
    return AppliedStoryEvent(
        scene_key=scene_key,
        act=CHAPTER_SCENES.get(scene_key, {}).get("act", character.story_act),
        pending_event=pending_event,
        authority_snapshot=authority_snapshot,
    )
