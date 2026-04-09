from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import asdict, dataclass

from game_content import MONSTERS
from models import Character

from .game_master_service import build_default_actions_for_character, build_live_view_state
from .memory_service import get_latest_memory_summary, get_recent_game_messages, store_game_messages
from .scene_flow import build_scene_context
from .state_store import (
    clear_pending_event,
    clear_pending_roll_resolution,
    get_pending_roll_resolution,
    get_story_flags,
    get_story_inventory,
    persist_story_state,
    set_authority_snapshot,
    set_context_hint,
    set_pending_roll_resolution,
    set_recent_reward,
    store_suggested_actions,
)
from .turn_service import build_master_graph_state, invoke_and_finalize_master_graph


@dataclass(frozen=True)
class RollStartSnapshot:
    roll: int
    attribute_label: str
    attribute_bonus: int
    total: int
    difficulty: int
    success: bool
    partial: bool
    decisive: bool
    crítical_failure: bool
    crítical_success: bool
    outcome_label: str

    def to_response(self) -> dict:
        payload = asdict(self)
        payload["ok"] = True
        return payload


@dataclass(frozen=True)
class RollResolutionSnapshot:
    roll: int
    attribute_label: str
    attribute_bonus: int
    total: int
    difficulty: int
    success: bool
    partial: bool
    decisive: bool
    crítical_failure: bool
    crítical_success: bool
    outcome_label: str
    gm_message: str
    suggested_actions: list[str]
    xp_gain: int
    gold_gain: int
    loot: list[dict]
    loot_names: list[str]
    monster_name: str | None
    view_state: dict

    def to_response(self) -> dict:
        payload = asdict(self)
        payload["ok"] = True
        return payload


def _critical_flag(roll_result: dict, key: str) -> bool:
    return bool(roll_result.get(key, roll_result.get(key.replace("í", "i"), False)))


def _safe_get_pending_roll_resolution(character: Character) -> dict | None:
    try:
        return get_pending_roll_resolution(character)
    except AttributeError:
        return None


def _build_post_roll_authority_snapshot(character: Character, roll_result: dict) -> dict | None:
    monster = roll_result.get("monster")
    if not monster:
        return None

    success = bool(roll_result.get("success"))
    loot_names = [item["name"] for item in roll_result.get("loot", []) if isinstance(item, dict) and item.get("name")]
    interaction_mode = "post_combat" if success else "combat"
    scene_key = character.story_scene or "chapter_entry"
    scene_phase = interaction_mode if success else "active_threat"

    return {
        "scene_key": scene_key,
        "current_target": monster["name"],
        "target_source": "roll_resolution",
        "interaction_mode": interaction_mode,
        "interaction_type": interaction_mode,
        "danger_level": "medium" if success else "elevated",
        "recent_outcome": "victory" if success else "ongoing",
        "mode_transition_signal": "post_combat_loot_window" if success and loot_names else "active_threat",
        "allowed_action_kinds": ["loot", "observe", "investigate", "move", "survival", "recover", "craft"]
        if success
        else ["combat", "defend", "escape", "observe", "stealth"],
        "target_locked": True,
        "post_combat_pending_loot": bool(success and loot_names),
        "recent_reward_truth": {
            "monster_name": monster["name"],
            "loot_names": loot_names,
            "xp_gain": int(roll_result.get("xp_gain", 0)),
            "gold_gain": int(roll_result.get("gold_gain", 0)),
        }
        if success
        else None,
        "pending_event_truth": {
            "type": str(roll_result.get("event", {}).get("type", "")).strip(),
            "attribute": str(roll_result.get("event", {}).get("attribute", "")).strip(),
            "monster_name": monster["name"],
        },
        "current_scene_state": {
            "scene_key": scene_key,
            "scene_type": "encounter",
            "scene_phase": scene_phase,
            "has_pending_event": False,
            "has_recent_reward": success,
            "context_hint_kind": "post_encounter" if success else None,
        },
    }


def roll_pending_event(character: Character, pending_event: dict) -> dict:
    attribute = pending_event["attribute"]
    attribute_value = getattr(character, attribute)
    attribute_bonus = (attribute_value - 10) // 2
    roll_value = random.randint(1, 20)
    total = roll_value + attribute_bonus
    difficulty = int(pending_event["difficulty"])
    crítical_failure = roll_value == 1
    crítical_success = roll_value == 20
    success = crítical_success or (not crítical_failure and total >= difficulty)
    decisive = crítical_success or (success and total >= difficulty + 5)
    partial = not success and not crítical_failure and total >= max(difficulty - 2, 1)

    result = {
        "event": pending_event,
        "roll": roll_value,
        "attribute_value": attribute_value,
        "attribute_bonus": attribute_bonus,
        "total": total,
        "difficulty": difficulty,
        "success": success,
        "partial": partial,
        "decisive": decisive,
        "crítical_failure": crítical_failure,
        "crítical_success": crítical_success,
        "xp_gain": 0,
        "gold_gain": 0,
        "loot": [],
    }

    if pending_event["type"] == "encounter":
        monster = MONSTERS[pending_event["monster_slug"]]
        result["monster"] = monster
        result["xp_gain"] = monster["xp"] + (20 if crítical_success else 0) if success else (5 if crítical_failure else max(monster["xp"] // 3, 15))
        if success:
            loot_count = 2 if decisive else 1
            selected_loot = random.sample(monster["drops"], min(loot_count, len(monster["drops"])))
            result["loot"] = selected_loot
            result["gold_gain"] = sum(item["value"] for item in selected_loot) + (10 if crítical_success else 0)
    else:
        result["xp_gain"] = 50 if crítical_success else 40 if success else 5 if crítical_failure else 15
        if crítical_success:
            result["gold_gain"] = 12
        elif decisive:
            result["gold_gain"] = 8
        elif success:
            result["gold_gain"] = 4

    return result


def apply_roll_rewards(character: Character, roll_result: dict) -> dict:
    inventory = get_story_inventory(character)
    flags = get_story_flags(character)
    loot = roll_result.get("loot", [])
    monster = roll_result.get("monster")

    inventory.extend(loot)

    if monster:
        defeated = flags.get("defeated_monsters", {})
        if not isinstance(defeated, dict):
            defeated = {}
        monster_slug = roll_result["event"].get("monster_slug")
        if monster_slug:
            defeated[monster_slug] = defeated.get(monster_slug, 0) + (1 if roll_result.get("success") else 0)
            flags["defeated_monsters"] = defeated

    persist_story_state(
        character.id,
        flags=flags,
        inventory=inventory,
        xp_delta=roll_result["xp_gain"],
        gold_delta=roll_result["gold_gain"],
    )

    if monster and roll_result.get("success"):
        set_context_hint(
            character.id,
            {
                "kind": "post_encounter",
                "monster_slug": roll_result["event"].get("monster_slug"),
                "monster_name": monster["name"],
            },
        )
        set_recent_reward(
            character.id,
            {
                "monster_name": monster["name"],
                "xp_gain": roll_result["xp_gain"],
                "gold_gain": roll_result["gold_gain"],
                "loot_names": [item["name"] for item in loot],
            },
        )

    return {
        "inventory": inventory,
        "flags": flags,
        "loot_names": [item["name"] for item in loot],
    }


def build_loot_summary_text(roll_result: dict) -> str:
    loot = roll_result.get("loot", [])
    monster = roll_result.get("monster")
    if not monster:
        return ""

    if loot:
        loot_names = ", ".join(item["name"] for item in loot)
        return (
            f"Ao derrotar {monster['name']}, você obteve {loot_names}, "
            f"{roll_result['xp_gain']} XP e {roll_result['gold_gain']} de ouro."
        )

    if roll_result.get("success"):
        return (
            f"{monster['name']} foi abatido, mas não deixou nenhum item raro desta vez. "
            f"Mesmo assim, você recebeu {roll_result['xp_gain']} XP."
        )

    return f"{monster['name']} não foi totalmente vencido, então nenhum drop foi entregue."


def _outcome_label(roll_result: dict) -> str:
    if _critical_flag(roll_result, "crítical_failure"):
        return "falha crítica"
    if _critical_flag(roll_result, "crítical_success"):
        return "sucesso crítico"
    if roll_result["decisive"]:
        return "sucesso decisivo"
    if roll_result["success"]:
        return "sucesso"
    if roll_result["partial"]:
        return "falha parcial"
    return "falha"


def _fallback_roll_consequence_text(roll_result: dict, pending_event: dict) -> str:
    action_kind = str(pending_event.get("action_kind", "")).strip()
    monster_name = roll_result.get("monster", {}).get("name")

    if _critical_flag(roll_result, "crítical_success"):
        if action_kind in {"combat", "combat_magic"}:
            target = monster_name or "o alvo"
            return f"O d20 cai perfeito. Seu golpe entra com maestria, quebra a resistência de {target} e empurra a cena a seu favor sem deixar espaço para resposta imediata."
        if action_kind == "observe":
            return "Sua leitura do ambiente é absoluta. Nada relevante escapa aos seus sentidos, e a vantagem tática vem inteira para suas mãos."
        if action_kind == "dialogue":
            return "Sua presença domina o instante. Cada palavra acerta o tom exato, e a outra parte cede de forma clara diante da sua condução."
        return "O resultado vem com maestria. A ação se completa de forma exemplar, com controle total da situação e vantagem evidente para você."

    if _critical_flag(roll_result, "crítical_failure"):
        if action_kind in {"combat", "combat_magic"}:
            target = monster_name or "o alvo"
            return f"O pior resultado possível acontece. Sua ofensiva falha por completo, você se expõe demais e {target} ganha a iniciativa, forçando uma punição imediata na cena."
        if action_kind == "move":
            return "A tentativa desanda no pior momento. O obstáculo não cede, você perde o controle do esforço e a cena responde com uma punição imediata."
        if action_kind == "dialogue":
            return "As palavras saem no pior tom possível. A aproximação falha, a tensão sobe e você sofre uma resposta hostil antes de conseguir corrigir o rumo."
        return "O resultado é uma falha crítica. A ação não acontece, você perde a iniciativa e a situação piora com uma punição imediata."

    if roll_result["success"]:
        return "O impulso certo vem no momento exato, e a situação cede diante da sua resposta."
    if roll_result["partial"]:
        return "Você segura a pressão por pouco, mas a situação cobra um preço antes de ceder."
    return "O momento escapa dos seus dedos e o perigo avança antes que você consiga reagir."


def resolve_pending_roll_with_master(character: Character, pending_event: dict) -> dict:
    stored_resolution = _safe_get_pending_roll_resolution(character)
    roll_result = None
    if stored_resolution and stored_resolution.get("event") == pending_event:
        candidate = stored_resolution.get("roll_result")
        if isinstance(candidate, dict):
            roll_result = candidate

    if roll_result is None:
        roll_result = roll_pending_event(character, pending_event)

    scene = build_scene_context(character.story_scene or "chapter_entry", get_story_flags(character), get_story_inventory(character))
    latest_summary = get_latest_memory_summary(character.id)
    resolution_state = {
        "character_name": character.name,
        "scene": scene["title"],
        "event": pending_event,
        "roll": roll_result["roll"],
        "attribute_bonus": roll_result["attribute_bonus"],
        "total": roll_result["total"],
        "difficulty": roll_result["difficulty"],
        "outcome": _outcome_label(roll_result),
        "monster": roll_result.get("monster", {}).get("name"),
    }

    try:
        graph_state = build_master_graph_state(
            character,
            scene,
            get_recent_game_messages(character.id, limit=6),
            latest_summary.summary_text if latest_summary else None,
            mode="resolution",
            roll_resolution=resolution_state,
        )
        resolution_result = invoke_and_finalize_master_graph(graph_state)
        finalized_resolution = resolution_result.payload
        consequence_text = finalized_resolution["narration"]
        suggested_actions = finalized_resolution["suggested_actions"] or build_default_actions_for_character(
            character,
            character.story_scene or "chapter_entry",
        )
    except Exception:
        consequence_text = _fallback_roll_consequence_text(roll_result, pending_event)
        suggested_actions = build_default_actions_for_character(character, character.story_scene or "chapter_entry")

    reward_update = apply_roll_rewards(character, roll_result)
    clear_pending_event(character.id)
    clear_pending_roll_resolution(character.id)
    store_suggested_actions(character.id, suggested_actions)
    loot_summary = build_loot_summary_text(roll_result)
    full_consequence_text = consequence_text if not loot_summary else f"{consequence_text}\n\n{loot_summary}"

    store_game_messages(
        character.id,
        character.story_scene or "chapter_entry",
        f"[ROLAGEM] {pending_event['roll_type']} com {pending_event['label']} contra CD {roll_result['difficulty']}: {roll_result['roll']} + {roll_result['attribute_bonus']} = {roll_result['total']}",
        full_consequence_text,
    )
    set_authority_snapshot(character.id, _build_post_roll_authority_snapshot(character, roll_result))

    return {
        "roll_result": roll_result,
        "gm_message": full_consequence_text,
        "suggested_actions": suggested_actions,
        "reward_update": reward_update,
    }


def run_roll_start(character: Character, pending_event: dict) -> RollStartSnapshot:
    stored_resolution = _safe_get_pending_roll_resolution(character)
    roll_result = None
    if stored_resolution and stored_resolution.get("event") == pending_event:
        candidate = stored_resolution.get("roll_result")
        if isinstance(candidate, dict):
            roll_result = candidate

    if roll_result is None:
        roll_result = roll_pending_event(character, pending_event)
        set_pending_roll_resolution(
            character.id,
            {
                "event": pending_event,
                "roll_result": roll_result,
            },
        )

    return RollStartSnapshot(
        roll=roll_result["roll"],
        attribute_label=pending_event["label"],
        attribute_bonus=roll_result["attribute_bonus"],
        total=roll_result["total"],
        difficulty=roll_result["difficulty"],
        success=roll_result["success"],
        partial=roll_result["partial"],
        decisive=roll_result["decisive"],
        crítical_failure=_critical_flag(roll_result, "crítical_failure"),
        crítical_success=_critical_flag(roll_result, "crítical_success"),
        outcome_label=_outcome_label(roll_result),
    )


def run_roll_resolution(
    character: Character,
    pending_event: dict,
    *,
    summarize_memory: Callable[[Character], None] | None = None,
    refresh_character: Callable[[int], Character | None] | None = None,
) -> RollResolutionSnapshot:
    resolution_snapshot = resolve_pending_roll_with_master(character, pending_event)
    snapshot_character = refresh_character(character.id) if refresh_character else character
    if snapshot_character is None:
        snapshot_character = character

    if summarize_memory is not None:
        summarize_memory(snapshot_character)

    roll_result = resolution_snapshot["roll_result"]
    reward_update = resolution_snapshot["reward_update"]
    view_state = build_live_view_state(snapshot_character)
    return RollResolutionSnapshot(
        roll=roll_result["roll"],
        attribute_label=pending_event["label"],
        attribute_bonus=roll_result["attribute_bonus"],
        total=roll_result["total"],
        difficulty=roll_result["difficulty"],
        success=roll_result["success"],
        partial=roll_result["partial"],
        decisive=roll_result["decisive"],
        crítical_failure=_critical_flag(roll_result, "crítical_failure"),
        crítical_success=_critical_flag(roll_result, "crítical_success"),
        outcome_label=_outcome_label(roll_result),
        gm_message=resolution_snapshot["gm_message"],
        suggested_actions=resolution_snapshot["suggested_actions"],
        xp_gain=roll_result["xp_gain"],
        gold_gain=roll_result["gold_gain"],
        loot=roll_result["loot"],
        loot_names=reward_update["loot_names"],
        monster_name=roll_result.get("monster", {}).get("name"),
        view_state=view_state,
    )

