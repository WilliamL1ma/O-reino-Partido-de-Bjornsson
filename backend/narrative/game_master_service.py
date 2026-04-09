from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

from game_content import CHAPTER_SCENES, MONSTERS
from models import Character, GameMessage

from .action_rolls import normalize_pending_event
from .memory_service import (
    get_latest_memory_summary,
    get_recent_game_messages,
    store_game_messages,
    store_gm_message,
    store_player_message,
)
from .scene_flow import allowed_next_scenes, build_scene_context, get_encounter_transition, initial_story_state
from .story_events import apply_story_event
from .state_store import (
    get_authority_snapshot,
    get_context_hint,
    get_pending_event,
    get_recent_reward,
    get_story_flags,
    get_story_inventory,
    get_suggested_actions,
    persist_story_state,
    set_context_hint,
    set_authority_snapshot,
    set_pending_event,
    set_recent_reward,
    store_suggested_actions,
)
from .turn_service import build_default_suggested_actions, build_master_graph_state, invoke_and_finalize_master_graph


@dataclass(frozen=True)
class IntroMessageResult:
    message: str
    suggested_actions: list[str]


@dataclass(frozen=True)
class GameViewSnapshot:
    scene: dict
    pending_event: dict | None
    recent_messages: list[GameMessage]
    memory_summary: object | None
    current_moment: dict
    suggested_actions: list[str]
    recent_reward: dict | None
    encounter: dict | None


@dataclass(frozen=True)
class MasterConversationSnapshot:
    player_message: str
    gm_message: str
    summary: str | None
    pending_event: dict | None
    next_scene: str | None
    current_moment: dict
    suggested_actions: list[str]

    def to_response(self) -> dict:
        payload = asdict(self)
        payload["ok"] = True
        return payload


def _invoke_master_graph(graph_state: dict) -> dict:
    from master_graph import invoke_master_graph

    return invoke_master_graph(graph_state)


def _snapshot_with_event_transition(authority: dict, event: dict | None) -> dict | None:
    if not isinstance(authority, dict):
        authority = {}
    if not isinstance(event, dict):
        return authority or None

    snapshot = dict(authority)
    monster_name = str(event.get("monster_name", "")).strip()
    if monster_name:
        snapshot["current_target"] = monster_name
        snapshot["target_source"] = "pending_event"

    snapshot["interaction_mode"] = "roll_pending"
    snapshot["interaction_type"] = "roll_pending"
    snapshot["recent_outcome"] = "awaiting_roll"
    snapshot["mode_transition_signal"] = "pending_roll"

    if event.get("type") == "encounter":
        snapshot["interaction_mode"] = "roll_pending"
        snapshot["interaction_type"] = "roll_pending"
        snapshot["danger_level"] = "high"
        snapshot["allowed_action_kinds"] = ["combat", "defend", "escape", "observe"]
        snapshot["target_locked"] = bool(monster_name)
        snapshot["post_combat_pending_loot"] = False
        pending_event_truth = snapshot.get("pending_event_truth")
        if not isinstance(pending_event_truth, dict):
            pending_event_truth = {}
        pending_event_truth.update(
            {
                "type": event.get("type"),
                "attribute": event.get("attribute"),
                "monster_name": monster_name or pending_event_truth.get("monster_name"),
            }
        )
        snapshot["pending_event_truth"] = pending_event_truth

        current_scene_state = snapshot.get("current_scene_state")
        if not isinstance(current_scene_state, dict):
            current_scene_state = {}
        current_scene_state["has_pending_event"] = True
        current_scene_state["has_recent_reward"] = False
        current_scene_state["scene_phase"] = "roll_pending"
        snapshot["current_scene_state"] = current_scene_state
        snapshot["scene_phase"] = "roll_pending"
    else:
        snapshot["danger_level"] = str(snapshot.get("danger_level", "")).strip() or "medium"
        snapshot["allowed_action_kinds"] = ["observe", "investigate", "move", "dialogue", "recover"]

        current_scene_state = snapshot.get("current_scene_state")
        if not isinstance(current_scene_state, dict):
            current_scene_state = {}
        current_scene_state["has_pending_event"] = True
        current_scene_state["has_recent_reward"] = False
        current_scene_state["scene_phase"] = "roll_pending"
        snapshot["current_scene_state"] = current_scene_state
        snapshot["scene_phase"] = "roll_pending"

    return snapshot or None


def _truncate_text(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def build_default_actions_for_character(character: Character, scene_key: str) -> list[str]:
    scene = CHAPTER_SCENES.get(scene_key, CHAPTER_SCENES["chapter_entry"])
    return build_default_suggested_actions(
        scene_key=scene_key,
        scene=scene,
        allowed_next_scenes=allowed_next_scenes(scene_key),
        context_hint=get_context_hint(character),
        recent_reward=get_recent_reward(character),
        pending_event=get_pending_event(character),
        inventory=get_story_inventory(character),
        persisted_authority=get_authority_snapshot(character),
    )


def get_effective_suggested_actions(character: Character, scene_key: str) -> list[str]:
    actions = get_suggested_actions(character)
    if actions:
        return actions[:5]
    return build_default_actions_for_character(character, scene_key)


def message_looks_like_looting(message: str) -> bool:
    normalized = message.strip().lower()
    keywords = [
        "loot",
        "lootear",
        "saquear",
        "vasculhar",
        "explorar o corpo",
        "pegar os itens",
        "revistar o corpo",
        "ver os drops",
    ]
    return any(keyword in normalized for keyword in keywords)


def build_recent_reward_message(recent_reward: dict) -> str:
    loot_names = recent_reward.get("loot_names", [])
    loot_text = ", ".join(loot_names) if loot_names else "nenhum item raro"
    return (
        f"Voce revira o corpo de {recent_reward['monster_name']} e confirma o saque real deixado pela criatura. "
        f"Voce recebeu {loot_text}. O confronto tambem rendeu {recent_reward['xp_gain']} XP e {recent_reward['gold_gain']} de ouro."
    )


def _extract_current_moment_from_message(message: str) -> tuple[str | None, str | None]:
    text = (message or "").strip()
    if not text:
        return None, None

    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        return None, None

    narrative_paragraph = paragraphs[0]
    first_sentence = re.split(r"(?<=[.!?])\s+", narrative_paragraph, maxsplit=1)[0].strip()
    if len(first_sentence) < 10 or len(first_sentence) > 110:
        first_sentence = None

    return first_sentence, _truncate_text(narrative_paragraph, 240)


def _build_pre_roll_message(narration: str, event: dict, player_message: str) -> str:
    text = re.sub(r"\s+", " ", (narration or "").strip())
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip() if text else ""

    if len(first_sentence) < 12:
        intent = re.sub(r"\s+", " ", (player_message or "").strip())
        if intent:
            first_sentence = f"Voce tenta {intent.lower()}."

    stakes = str(event.get("stakes", "")).strip() or "A situacao precisa ser resolvida no dado antes de seguir."
    monster_name = str(event.get("monster_name", "")).strip()
    event_type = str(event.get("type", "")).strip()
    action_kind = str(event.get("action_kind", "")).strip()

    if event_type == "encounter" and monster_name:
        trigger = f"{monster_name} exige resposta imediata."
    elif action_kind == "investigate":
        trigger = "Antes de concluir o que isso significa, a situacao pede um teste."
    elif action_kind == "observe":
        trigger = "Antes de ter certeza do que voce percebeu, a situacao pede um teste."
    elif action_kind == "dialogue":
        trigger = "Antes de definir como isso e recebido, a situacao pede um teste."
    elif action_kind == "move":
        trigger = "Antes de saber se o movimento se completa, a situacao pede um teste."
    else:
        trigger = "Antes de definir o desfecho, a situacao pede um teste."

    pieces = [piece for piece in (first_sentence, trigger, stakes) if piece]
    return " ".join(pieces).strip()


def build_current_moment(character: Character, scene: dict, recent_messages: list[GameMessage]) -> dict:
    pending_event = get_pending_event(character)
    if pending_event:
        title = pending_event.get("monster_name") or "Momento de decisao"
        description = str(pending_event.get("stakes", "")).strip() or scene["lead"]
        return {"title": title, "description": description}

    latest_gm_message = next(
        (message.content for message in reversed(recent_messages) if message.role == "gm" and message.content.strip()),
        "",
    )
    live_title, live_description = _extract_current_moment_from_message(latest_gm_message)
    if live_description:
        return {"title": live_title or "Momento atual da jornada", "description": live_description}

    return {"title": scene["title"], "description": scene["lead"]}


def build_game_view_snapshot(character: Character, *, groq_enabled: bool) -> GameViewSnapshot:
    character = ensure_story_initialized(character)
    scene_key = character.story_scene or "chapter_entry"
    ensure_intro_message(character, groq_enabled=groq_enabled)
    scene = build_scene_context(scene_key, get_story_flags(character), get_story_inventory(character))
    recent_messages = get_recent_game_messages(character.id, limit=6)
    memory_summary = get_latest_memory_summary(character.id)
    pending_event = get_pending_event(character)
    transition = get_encounter_transition(scene_key)
    encounter = MONSTERS[transition["monster"]] if transition else None
    return GameViewSnapshot(
        scene=scene,
        pending_event=pending_event,
        recent_messages=recent_messages,
        memory_summary=memory_summary,
        current_moment=build_current_moment(character, scene, recent_messages),
        suggested_actions=get_effective_suggested_actions(character, scene_key),
        recent_reward=get_recent_reward(character),
        encounter=encounter,
    )


def ensure_story_initialized(character: Character) -> Character:
    if character.story_scene:
        return character
    state = initial_story_state(get_story_inventory(character))
    persist_story_state(character.id, **state)
    character.story_scene = state["scene"]
    character.story_act = state["act"]
    character.story_flags = json.dumps(state["flags"], ensure_ascii=True)
    character.story_inventory = json.dumps(state["inventory"], ensure_ascii=True)
    return character


def _build_fallback_intro(scene: dict) -> str:
    actions = [
        "ir ate a taverna mais proxima",
        "observar a praca e o movimento das ruas",
        "falar com um guarda ou morador",
        "andar pelas vielas em busca de rumores",
        "pedir orientacao sobre onde conseguir trabalho ou abrigo",
    ]
    return (
        f"Voce esta em {scene['title']}. {scene['lead']} "
        "A partir daqui, voce pode agir livremente pela conversa. "
        "Por exemplo: " + "; ".join(actions) + "."
    )


def prepare_intro_message(character: Character) -> IntroMessageResult:
    scene = build_scene_context(character.story_scene or "chapter_entry", get_story_flags(character), get_story_inventory(character))
    latest_summary = get_latest_memory_summary(character.id)
    try:
        intro_state = build_master_graph_state(
            character,
            scene,
            [],
            latest_summary.summary_text if latest_summary else None,
            mode="intro",
        )
        intro_result = invoke_and_finalize_master_graph(intro_state, _invoke_master_graph)
        intro_message = intro_result.payload["narration"].strip() or _build_fallback_intro(scene)
        suggested_actions = intro_result.payload["suggested_actions"] or build_default_actions_for_character(
            character,
            character.story_scene or "chapter_entry",
        )
    except Exception:
        intro_message = _build_fallback_intro(scene)
        suggested_actions = build_default_actions_for_character(character, character.story_scene or "chapter_entry")
    return IntroMessageResult(message=intro_message, suggested_actions=suggested_actions)


def ensure_intro_message(character: Character, *, groq_enabled: bool) -> None:
    if get_recent_game_messages(character.id, limit=1):
        return

    if groq_enabled:
        intro = prepare_intro_message(character)
    else:
        scene = build_scene_context(character.story_scene or "chapter_entry", get_story_flags(character), get_story_inventory(character))
        intro = IntroMessageResult(
            message=_build_fallback_intro(scene),
            suggested_actions=build_default_actions_for_character(character, character.story_scene or "chapter_entry"),
        )

    store_suggested_actions(character.id, intro.suggested_actions)
    if intro.message:
        store_gm_message(character.id, character.story_scene or "chapter_entry", intro.message)


def run_master_turn(character: Character, player_message: str) -> dict:
    scene = build_scene_context(character.story_scene or "chapter_entry", get_story_flags(character), get_story_inventory(character))
    context_hint = get_context_hint(character)
    recent_reward = get_recent_reward(character)

    if (
        context_hint
        and context_hint.get("kind") == "post_encounter"
        and recent_reward
        and message_looks_like_looting(player_message)
    ):
        gm_reply = build_recent_reward_message(recent_reward)
        suggested_actions = build_default_actions_for_character(character, character.story_scene or "chapter_entry")
        store_suggested_actions(character.id, suggested_actions)
        store_game_messages(character.id, character.story_scene or "chapter_entry", player_message, gm_reply)
        return {
            "gm_message": gm_reply,
            "pending_event": None,
            "next_scene": None,
            "suggested_actions": suggested_actions,
        }

    recent_messages = get_recent_game_messages(character.id, limit=6)
    latest_summary = get_latest_memory_summary(character.id)
    graph_state = build_master_graph_state(
        character,
        scene,
        recent_messages,
        latest_summary.summary_text if latest_summary else None,
        mode="turn",
        player_message=player_message,
    )
    turn_result = invoke_and_finalize_master_graph(graph_state, _invoke_master_graph)
    finalized_turn = turn_result.payload
    gm_reply = finalized_turn["narration"]
    story_event = apply_story_event(
        character,
        finalized_turn.get("story_event"),
        graph_state.get("authoritative_state", {}),
    )
    if story_event:
        persist_story_state(
            character.id,
            scene=story_event.scene_key,
            act=story_event.act,
        )
        set_context_hint(character.id, None)
        set_authority_snapshot(character.id, story_event.authority_snapshot)
        set_pending_event(character.id, story_event.pending_event)
        store_suggested_actions(character.id, [])
        store_player_message(character.id, story_event.scene_key, player_message)
        return {
            "gm_message": "",
            "pending_event": story_event.pending_event,
            "next_scene": None,
            "suggested_actions": [],
        }

    event = normalize_pending_event(character, player_message, graph_state.get("authoritative_state", {}), finalized_turn["event"])
    if event:
        gm_reply = ""
    next_scene = None if event else finalized_turn["next_scene"]
    suggested_actions = finalized_turn["suggested_actions"] or build_default_actions_for_character(
        character,
        next_scene or character.story_scene or "chapter_entry",
    )

    if next_scene:
        persist_story_state(
            character.id,
            scene=next_scene,
            act=CHAPTER_SCENES.get(next_scene, {}).get("act", character.story_act),
        )
        set_context_hint(character.id, None)
        set_authority_snapshot(character.id, None)
    else:
        set_authority_snapshot(
            character.id,
            _snapshot_with_event_transition(graph_state.get("authoritative_state", {}), event),
        )
    store_suggested_actions(character.id, suggested_actions)
    if event:
        set_context_hint(character.id, None)
        set_pending_event(character.id, event)

    if event:
        store_player_message(character.id, character.story_scene or "chapter_entry", player_message)
    else:
        store_game_messages(character.id, character.story_scene or "chapter_entry", player_message, gm_reply)
    return {
        "gm_message": gm_reply,
        "pending_event": event,
        "next_scene": next_scene,
        "suggested_actions": suggested_actions,
    }


def run_master_conversation(
    character: Character,
    player_message: str,
    *,
    refresh_character: Callable[[int], Character | None] | None = None,
    summarize_memory: Callable[[Character], None] | None = None,
) -> MasterConversationSnapshot:
    character = ensure_story_initialized(character)
    turn_snapshot = run_master_turn(character, player_message)
    snapshot_character = refresh_character(character.id) if refresh_character else character
    if snapshot_character is None:
        snapshot_character = character

    if summarize_memory is not None:
        summarize_memory(snapshot_character)

    latest_summary = get_latest_memory_summary(character.id)
    snapshot_scene = build_scene_context(
        snapshot_character.story_scene or "chapter_entry",
        get_story_flags(snapshot_character),
        get_story_inventory(snapshot_character),
    )
    snapshot_messages = get_recent_game_messages(character.id, limit=6)
    next_scene = turn_snapshot["next_scene"]
    return MasterConversationSnapshot(
        player_message=player_message,
        gm_message=turn_snapshot["gm_message"],
        summary=latest_summary.summary_text if latest_summary else None,
        pending_event=turn_snapshot["pending_event"],
        next_scene=next_scene,
        current_moment=build_current_moment(snapshot_character, snapshot_scene, snapshot_messages),
        suggested_actions=get_effective_suggested_actions(
            snapshot_character,
            next_scene or (snapshot_character.story_scene or "chapter_entry"),
        ),
    )
