from __future__ import annotations

import logging
import random
import threading
from collections.abc import Callable

from flask import flash, jsonify, redirect, render_template, request, url_for

from game_content import CHAPTER_SCENES, MONSTERS, TACTICS
from models import Character

from .game_master_service import build_game_view_snapshot, ensure_story_initialized, run_master_conversation
from .llm_gateway import LLMRateLimitError, call_groq_messages, groq_is_configured
from .memory_service import store_gm_message
from .roll_service import run_roll_resolution, run_roll_start
from .scene_flow import get_encounter_transition
from .state_store import get_pending_event, get_story_flags, get_story_inventory, persist_story_state


LOGGER = logging.getLogger(__name__)


SCENE_ACTION_TRANSITIONS = {
    "chapter_entry": {"go_goblin": ("encounter_goblin", 1), "go_robalo": ("encounter_robalo", 1)},
    "act_two_crossroads": {
        "go_duende": ("encounter_duende", 2),
        "go_cobra": ("encounter_cobra", 2),
        "go_raposa": ("encounter_raposa", 2),
    },
    "act_three_threshold": {
        "go_aranha": ("encounter_aranha", 3),
        "go_lupus": ("encounter_lupus", 3),
        "go_passaro": ("encounter_passaro", 3),
    },
}

FIRST_CHAPTER_ACHIEVEMENT = {
    "slug": "primeiro-capitulo-concluido",
    "name": "Primeiro Capitulo Concluido",
    "description": "Recebeu um legado do capitulo inicial e assumiu o misterio principal de Elandoria.",
}


def _inventory_names(inventory: list[dict]) -> set[str]:
    names: set[str] = set()
    for item in inventory:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.add(name)
    return names


def _has_first_chapter_rewards(inventory: list[dict]) -> bool:
    names = _inventory_names(inventory)
    has_main_mystery = "Cristal Incompreendido" in names
    has_legacy = "Espada de Vinganca de Rowan" in names or "Cajado de Freya" in names
    return has_main_mystery and has_legacy


def _upsert_first_chapter_achievement(flags: dict) -> tuple[dict, bool]:
    updated_flags = dict(flags or {})
    achievements = updated_flags.get("achievements")
    if not isinstance(achievements, list):
        achievements = []

    achievement_slug = FIRST_CHAPTER_ACHIEVEMENT["slug"]
    if any(isinstance(item, dict) and str(item.get("slug", "")).strip() == achievement_slug for item in achievements):
        updated_flags["achievements"] = achievements
        return updated_flags, False

    achievements.append(dict(FIRST_CHAPTER_ACHIEVEMENT))
    updated_flags["achievements"] = achievements
    return updated_flags, True


def _ensure_first_chapter_achievement(
    character: Character,
    *,
    get_flags: Callable[[Character], dict],
    get_inventory: Callable[[Character], list[dict]],
    persist_state: Callable[..., None],
) -> None:
    flags = get_flags(character)
    inventory = get_inventory(character)
    if not _has_first_chapter_rewards(inventory):
        return

    updated_flags, created = _upsert_first_chapter_achievement(flags)
    thank_you_sent = bool(updated_flags.get("first_chapter_master_reverence"))

    if created or not thank_you_sent:
        updated_flags["first_chapter_master_reverence"] = True
        persist_state(character.id, flags=updated_flags)
        store_gm_message(
            character.id,
            "chapter_complete",
            "O mestre inclina a cabeca em reverencia. Obrigado por jogar o primeiro capitulo.",
        )
    elif updated_flags != flags:
        persist_state(character.id, flags=updated_flags)


def summarize_memory_if_needed(character: Character, *, summarize_memory: Callable[[Character, Callable[[list[dict]], str]], None]) -> None:
    def _run_summary() -> None:
        try:
            summarize_memory(
                character,
                call_llm=lambda messages: call_groq_messages(messages, temperature=0.3),
            )
        except Exception:
            LOGGER.exception("Falha ao resumir memoria narrativa em background.")

    threading.Thread(
        target=_run_summary,
        name=f"memory-summary-{character.id}",
        daemon=True,
    ).start()


def character_primary_bonus(character: Character, tactic: str) -> tuple[int, str]:
    candidates = {
        "power": [("strength", "FOR"), ("constitution", "CON"), ("charisma", "CAR")],
        "precision": [("dexterity", "DEX"), ("perception", "PER"), ("intelligence", "INT")],
        "mystic": [("intelligence", "INT"), ("wisdom", "SAB"), ("charisma", "CAR")],
        "instinct": [("perception", "PER"), ("wisdom", "SAB"), ("constitution", "CON")],
    }

    selected_field, selected_label = max(candidates[tactic], key=lambda item: getattr(character, item[0]))
    selected_value = getattr(character, selected_field)
    bonus = (selected_value - 10) // 2

    class_name = (character.class_name or "").lower()
    if tactic == "mystic" and class_name in {"wizard", "bard", "cleric", "druid", "necromancer", "summoner"}:
        bonus += 1
    if tactic == "power" and class_name in {"barbarian", "fighter", "demon hunter"}:
        bonus += 1
    if tactic == "precision" and class_name in {"rogue", "monk", "demon hunter"}:
        bonus += 1
    if tactic == "instinct" and character.race_slug in {"elfo", "meio-elfo", "halfling"}:
        bonus += 1

    return bonus, selected_label


def resolve_encounter(character: Character, monster_slug: str, tactic: str) -> dict:
    monster = MONSTERS[monster_slug]
    roll_value = random.randint(1, 20)
    tactic_bonus, stat_label = character_primary_bonus(character, tactic)
    total = roll_value + tactic_bonus
    favored_bonus = 1 if tactic in monster["favored_tactics"] else 0
    total += favored_bonus
    success = total >= monster["dc"]
    decisive = total >= monster["dc"] + 4

    available_drops = monster["drops"]
    if decisive:
        loot_count = min(2, len(available_drops))
    elif success:
        loot_count = 1
    else:
        loot_count = 1 if available_drops else 0

    selected_loot = random.sample(available_drops, loot_count) if loot_count else []
    xp_gain = monster["xp"] if success else max(monster["xp"] // 2, 25)
    gold_gain = sum(item["value"] for item in selected_loot)

    return {
        "monster": monster,
        "roll": roll_value,
        "bonus": tactic_bonus + favored_bonus,
        "stat_label": stat_label,
        "total": total,
        "success": success,
        "decisive": decisive,
        "xp_gain": xp_gain,
        "gold_gain": gold_gain,
        "loot": selected_loot,
        "tactic": TACTICS[tactic],
    }


def build_story_rewards(character: Character) -> list[dict]:
    magic_classes = {"wizard", "bard", "cleric", "druid", "necromancer", "summoner"}
    class_name = (character.class_name or "").lower()

    rewards = [
        {
            "name": "Cristal Incompreendido",
            "tag": "Misterio principal",
            "description": "Artefato instavel ligado aos segredos maiores dos reinos.",
        }
    ]

    if class_name in magic_classes or (
        class_name == "sem classe"
        and max(character.intelligence, character.wisdom, character.charisma) >= max(character.strength, character.dexterity)
    ):
        rewards.insert(
            0,
            {
                "name": "Cajado de Freya",
                "tag": "Legado de vida",
                "description": "Amplifica magia, cura e percepcao do fluxo vital em areas perigosas.",
            },
        )
    else:
        rewards.insert(
            0,
            {
                "name": "Espada de Vinganca de Rowan",
                "tag": "Legado de justica",
                "description": "Arma a dor transformada em coragem, moral de grupo e dano aumentado.",
            },
        )

    return rewards


def finalize_chapter_rewards(
    character: Character,
    *,
    get_flags: Callable[[Character], dict],
    get_inventory: Callable[[Character], list[dict]],
    persist_state: Callable[..., None],
) -> None:
    flags = get_flags(character)
    if flags.get("chapter_complete"):
        return

    inventory = get_inventory(character)
    chapter_rewards = build_story_rewards(character)
    inventory.extend(chapter_rewards)
    flags["chapter_complete"] = True
    flags, _ = _upsert_first_chapter_achievement(flags)
    flags["first_chapter_master_reverence"] = True

    persist_state(
        character.id,
        scene="chapter_complete",
        act=5,
        flags=flags,
        inventory=inventory,
        xp_delta=150,
        gold_delta=25,
    )

    reward_names = {reward["name"] for reward in chapter_rewards}
    if "Espada de Vinganca de Rowan" in reward_names and "Cristal Incompreendido" in reward_names:
        closing_message = (
            "O legado de justica repousa agora em suas maos, e o misterio principal de Elandoria segue vivo diante de voce. "
            "O mestre inclina a cabeca em respeito. Obrigado por jogar o primeiro capitulo."
        )
    else:
        closing_message = (
            "Os dons conquistados neste capitulo agora seguem com voce para o que vem depois. "
            "O mestre inclina a cabeca em respeito. Obrigado por jogar o primeiro capitulo."
        )

    store_gm_message(character.id, "chapter_complete", closing_message)


def _apply_scene_transition(
    character: Character,
    scene_key: str,
    action: str,
    *,
    persist_state: Callable[..., None],
) -> bool:
    scene_transition = SCENE_ACTION_TRANSITIONS.get(scene_key, {})
    next_step = scene_transition.get(action)
    if not next_step:
        return False

    next_scene, act = next_step
    persist_state(character.id, scene=next_scene, act=act)
    return True


def _handle_legacy_puzzle_action(
    character: Character,
    *,
    get_flags: Callable[[Character], dict],
    persist_state: Callable[..., None],
) -> bool:
    mirrors = [
        request.form.get("mirror_1", "").strip().lower(),
        request.form.get("mirror_2", "").strip().lower(),
        request.form.get("mirror_3", "").strip().lower(),
    ]
    legacy_word = request.form.get("legacy_word", "").strip().lower()
    altar_flower = request.form.get("altar_flower", "").strip().lower()

    if mirrors != ["amor", "luto", "vinganca"]:
        flash("Os espelhos ainda nao foram compreendidos na ordem correta.", "error")
        return True
    if legacy_word != "paz":
        flash("O guardiao ainda aguarda a palavra que define o futuro de Elandoria.", "error")
        return True
    if altar_flower != "flor da esperanca":
        flash("O altar so responde a flor certa, ligada ao herdeiro que nunca nasceu.", "error")
        return True

    flags = get_flags(character)
    flags["freya_legacy_solved"] = True
    persist_state(character.id, scene="encounter_lobisomem", act=5, flags=flags)
    flash("O legado de Freya respondeu. Algo feroz desperta alem do portal.", "success")
    return True


def handle_game_play(
    character: Character,
    *,
    attribute_fields: list[tuple[str, str]],
    get_flags: Callable[[Character], dict],
    get_inventory: Callable[[Character], list[dict]],
    get_character_by_user_id: Callable[[int], Character | None],
    persist_state: Callable[..., None],
    ensure_story: Callable[[Character], Character] = ensure_story_initialized,
    groq_enabled: bool | None = None,
) -> object:
    character = ensure_story(character)
    scene_key = character.story_scene or "chapter_entry"
    if scene_key == "chapter_complete":
        _ensure_first_chapter_achievement(
            character,
            get_flags=get_flags,
            get_inventory=get_inventory,
            persist_state=persist_state,
        )
        character = get_character_by_user_id(character.user_id) or character
        scene_key = character.story_scene or "chapter_entry"

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if _apply_scene_transition(character, scene_key, action, persist_state=persist_state):
            return redirect(url_for("game_routes.game_play"))

        transition = get_encounter_transition(scene_key)
        if transition:
            if action not in TACTICS:
                flash("Escolha uma tatica valida para o confronto.", "error")
                return redirect(url_for("game_routes.game_play"))

            outcome = resolve_encounter(character, transition["monster"], action)
            inventory = get_inventory(character)
            inventory.extend(outcome["loot"])
            flags = get_flags(character)
            flags[f"{scene_key}_resolved"] = True
            if transition.get("flag"):
                flags[transition["flag"]] = True

            persist_state(
                character.id,
                scene=transition["next_scene"],
                act=CHAPTER_SCENES.get(transition["next_scene"], {}).get("act", character.story_act),
                flags=flags,
                inventory=inventory,
                xp_delta=outcome["xp_gain"],
                gold_delta=outcome["gold_gain"],
            )

            loot_names = ", ".join(item["name"] for item in outcome["loot"]) if outcome["loot"] else "sem drops raros"
            flash(
                (
                    f"{outcome['monster']['name']} vencido com {outcome['tactic']['name'].lower()}. "
                    f"Rolagem {outcome['roll']} + bonus {outcome['bonus']} = {outcome['total']}. "
                    f"Voce ganhou {outcome['xp_gain']} XP, {outcome['gold_gain']} ouro e coletou {loot_names}."
                ),
                "success" if outcome["success"] else "warning",
            )

            if transition["next_scene"] == "chapter_complete":
                updated_character = get_character_by_user_id(character.user_id)
                if updated_character is not None:
                    finalize_chapter_rewards(
                        updated_character,
                        get_flags=get_flags,
                        get_inventory=get_inventory,
                        persist_state=persist_state,
                    )

            return redirect(url_for("game_routes.game_play"))

        if scene_key == "freya_legacy" and _handle_legacy_puzzle_action(
            character,
            get_flags=get_flags,
            persist_state=persist_state,
        ):
            return redirect(url_for("game_routes.game_play"))

    if groq_enabled is None:
        groq_enabled = groq_is_configured()
    view_snapshot = build_game_view_snapshot(character, groq_enabled=groq_enabled)
    rewards = build_story_rewards(character) if scene_key == "chapter_complete" else []
    return render_template(
        "game_play.html",
        character=character,
        scene=view_snapshot.scene,
        encounter=view_snapshot.encounter,
        tactics=TACTICS,
        rewards=rewards,
        attribute_fields=attribute_fields,
        inventory=get_inventory(character),
        recent_reward=view_snapshot.recent_reward,
        recent_messages=view_snapshot.recent_messages,
        current_moment=view_snapshot.current_moment,
        memory_summary=view_snapshot.memory_summary,
        suggested_actions=view_snapshot.suggested_actions,
        groq_enabled=groq_enabled,
        pending_event=view_snapshot.pending_event,
    )


def handle_game_master_chat(
    character: Character | None,
    *,
    get_pending_event_for_character: Callable[[Character], dict | None] = get_pending_event,
    get_character_by_user_id: Callable[[int], Character | None],
    summarize_memory: Callable[[Character], None],
    conversation_runner: Callable[..., object] = run_master_conversation,
    groq_enabled: bool | None = None,
) -> tuple[object, int] | object:
    if character is None:
        return jsonify({"ok": False, "message": "Crie sua ficha antes de falar com o mestre."}), 400
    if not character.class_name:
        return jsonify({"ok": False, "message": "Finalize a criacao do personagem antes de usar o mestre."}), 400

    if groq_enabled is None:
        groq_enabled = groq_is_configured()
    if not groq_enabled:
        return jsonify({"ok": False, "message": "Configure GROQ_API_KEY no .env para ativar o mestre conversacional."}), 400
    if get_pending_event_for_character(character):
        return jsonify({"ok": False, "message": "Existe uma rolagem pendente. Resolva o dado antes de continuar a conversa."}), 400

    player_message = request.form.get("message", "").strip()
    if not player_message:
        return jsonify({"ok": False, "message": "Escreva sua acao ou pergunta antes de enviar."}), 400

    try:
        response_payload = conversation_runner(
            character,
            player_message,
            refresh_character=lambda _character_id: get_character_by_user_id(character.user_id),
            summarize_memory=summarize_memory,
        ).to_response()
    except LLMRateLimitError as error:
        return jsonify({"ok": False, "message": str(error)}), 429
    except Exception as error:
        return jsonify({"ok": False, "message": f"Falha ao consultar o mestre via grafo: {error}"}), 502

    return jsonify(response_payload)


def handle_game_roll(
    character: Character | None,
    *,
    summarize_memory: Callable[[Character], None],
    roll_runner: Callable[..., object] = run_roll_start,
    get_pending_event_for_character: Callable[[Character], dict | None] = get_pending_event,
) -> tuple[object, int] | object:
    if character is None:
        return jsonify({"ok": False, "message": "Personagem nao encontrado."}), 400

    pending_event = get_pending_event_for_character(character)
    if not pending_event:
        return jsonify({"ok": False, "message": "Nao existe evento pendente para rolagem."}), 400

    try:
        response_payload = roll_runner(character, pending_event).to_response()
    except Exception as error:
        return jsonify({"ok": False, "message": f"Falha ao iniciar a rolagem: {error}"}), 502

    return jsonify(response_payload)


def handle_game_roll_resolution(
    character: Character | None,
    *,
    summarize_memory: Callable[[Character], None],
    roll_runner: Callable[..., object] = run_roll_resolution,
    get_pending_event_for_character: Callable[[Character], dict | None] = get_pending_event,
) -> tuple[object, int] | object:
    if character is None:
        return jsonify({"ok": False, "message": "Personagem nao encontrado."}), 400

    pending_event = get_pending_event_for_character(character)
    if not pending_event:
        return jsonify({"ok": False, "message": "Nao existe evento pendente para rolagem."}), 400

    try:
        response_payload = roll_runner(
            character,
            pending_event,
            summarize_memory=summarize_memory,
        ).to_response()
    except Exception as error:
        return jsonify({"ok": False, "message": f"Falha ao resolver a rolagem: {error}"}), 502

    return jsonify(response_payload)
