from __future__ import annotations

from collections.abc import Callable

from flask import Blueprint, flash, redirect, session, url_for


def create_game_blueprint(
    *,
    login_required,
    attribute_fields: list[tuple[str, str]],
    get_character_by_user_id: Callable[[], Callable[[int], object | None]],
    post_login_redirect: Callable[[], str],
    handle_game_play: Callable[[], Callable[..., object]],
    handle_game_master_chat: Callable[[], Callable[..., object]],
    handle_game_roll: Callable[[], Callable[..., object]],
    handle_game_roll_resolution: Callable[[], Callable[..., object]],
    get_story_flags: Callable[[], Callable[[object], dict]],
    get_story_inventory: Callable[[], Callable[[object], list[dict]]],
    get_pending_event: Callable[[], Callable[[object], dict | None]],
    persist_story_state: Callable[[], Callable[..., None]],
    ensure_story_initialized: Callable[[], Callable[[object], object]],
    groq_is_configured: Callable[[], Callable[[], bool]],
    summarize_memory_if_needed: Callable[[], Callable[[object], None]],
    run_master_conversation: Callable[[], Callable[..., object]],
    run_roll_start: Callable[[], Callable[..., object]],
    run_roll_resolution: Callable[[], Callable[..., object]],
    reset_campaign_state: Callable[[], Callable[[int], None]],
) -> Blueprint:
    blueprint = Blueprint("game_routes", __name__)

    @blueprint.route("/jogo", methods=["GET", "POST"], endpoint="game_play")
    @login_required
    def game_play():
        character = get_character_by_user_id()(session["user_id"])
        if character is None:
            return redirect(url_for("player_routes.character_create"))
        if not character.class_name:
            return redirect(post_login_redirect())

        return handle_game_play()(
            character,
            attribute_fields=attribute_fields,
            get_flags=get_story_flags(),
            get_inventory=get_story_inventory(),
            get_character_by_user_id=get_character_by_user_id(),
            persist_state=persist_story_state(),
            ensure_story=ensure_story_initialized(),
            groq_enabled=groq_is_configured()(),
        )

    @blueprint.post("/jogo/mestre", endpoint="game_master_chat")
    @login_required
    def game_master_chat():
        character = get_character_by_user_id()(session["user_id"])
        return handle_game_master_chat()(
            character,
            get_pending_event_for_character=get_pending_event(),
            get_character_by_user_id=lambda _user_id: get_character_by_user_id()(session["user_id"]),
            summarize_memory=summarize_memory_if_needed(),
            conversation_runner=run_master_conversation(),
            groq_enabled=groq_is_configured()(),
        )

    @blueprint.post("/jogo/rolar", endpoint="game_roll_pending_event")
    @login_required
    def game_roll_pending_event():
        character = get_character_by_user_id()(session["user_id"])
        return handle_game_roll()(
            character,
            summarize_memory=summarize_memory_if_needed(),
            roll_runner=run_roll_start(),
            get_pending_event_for_character=get_pending_event(),
        )

    @blueprint.post("/jogo/rolar/consequencia", endpoint="game_roll_resolution")
    @login_required
    def game_roll_resolution():
        character = get_character_by_user_id()(session["user_id"])
        return handle_game_roll_resolution()(
            character,
            summarize_memory=summarize_memory_if_needed(),
            roll_runner=run_roll_resolution(),
            get_pending_event_for_character=get_pending_event(),
        )

    @blueprint.post("/jogo/resetar-campanha", endpoint="game_reset_campaign")
    @login_required
    def game_reset_campaign():
        character = get_character_by_user_id()(session["user_id"])
        if character is None:
            return redirect(url_for("player_routes.character_create"))

        reset_campaign_state()(character.id)
        flash("A campanha foi reiniciada. Sua ficha foi mantida e a jornada começou do zero.", "success")
        return redirect(url_for("game_routes.game_play"))

    return blueprint
