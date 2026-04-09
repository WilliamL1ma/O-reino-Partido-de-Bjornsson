import os
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import flash, redirect, session, url_for
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app_factory import create_app as build_flask_app
from database import session_scope
from migrations import run_migrations
from models import Character, User
from models import GameMessage, MemorySummary
from narrative import (
    get_pending_event as narrative_get_pending_event,
    get_story_flags as narrative_get_story_flags,
    get_story_inventory as narrative_get_story_inventory,
    persist_story_state as narrative_persist_story_state,
    summarize_memory_if_needed as narrative_summarize_memory_if_needed,
)
from narrative.game_master_service import ensure_story_initialized as narrative_ensure_story_initialized, run_master_conversation
from narrative.llm_gateway import groq_is_configured
from narrative.roll_service import run_roll_resolution, run_roll_start
from narrative.web_handlers import (
    handle_game_master_chat as narrative_handle_game_master_chat,
    handle_game_play as narrative_handle_game_play,
    handle_game_roll as narrative_handle_game_roll,
    handle_game_roll_resolution as narrative_handle_game_roll_resolution,
    summarize_memory_if_needed as narrative_summarize_memory_if_needed_with_llm,
)
from web_blueprints import create_auth_blueprint, create_game_blueprint, create_player_blueprint
from web_support.auth_helpers import (
    get_character_by_user_id,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    login_user,
    logout_user,
    normalize_email,
    password_is_strong,
    validate_birth_date,
    verify_password,
)
from web_support.catalog import ATTRIBUTE_FIELDS, CLASS_NAME_TRANSLATIONS, CLASSES, RACES
from web_support.narrative_helpers import (
    get_pending_event,
    get_story_flags,
    get_story_inventory,
    persist_story_state,
    summarize_memory_if_needed,
)
from web_support.player_helpers import (
    apply_race_selection,
    apply_status_rolls,
    character_meets_class_requirements,
    clear_attribute_rolls,
    clear_pending_status_rolls,
    get_attribute_rolls,
    get_class_by_slug,
    get_race_by_slug,
    parse_character_attributes,
    special_race_is_locked,
    store_attribute_roll,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


def _normalize_email(email: str) -> str:
    return normalize_email(email)


def _validate_birth_date(raw_value: str):
    return validate_birth_date(raw_value)


def _password_is_strong(password: str) -> bool:
    return password_is_strong(password)


def _hash_password(password: str) -> str:
    return hash_password(password)


def _verify_password(password: str, password_hash: str) -> bool:
    return verify_password(password, password_hash)


def _get_user_by_email(email: str):
    return get_user_by_email(email, session_scope=session_scope, user_model=User)


def _get_user_by_id(user_id: int):
    return get_user_by_id(user_id, session_scope=session_scope, user_model=User)


def _get_character_by_user_id(user_id: int):
    return get_character_by_user_id(user_id, session_scope=session_scope, character_model=Character)


def _get_race_by_slug(slug: str):
    return get_race_by_slug(slug, races=RACES)


def _special_race_is_locked(character: Character | None) -> bool:
    return special_race_is_locked(character)


def _get_attribute_rolls() -> dict[str, int]:
    return get_attribute_rolls(session=session, attribute_fields=ATTRIBUTE_FIELDS)


def _store_attribute_roll(field_name: str, value: int) -> None:
    store_attribute_roll(field_name, value, session=session, attribute_fields=ATTRIBUTE_FIELDS)


def _clear_attribute_rolls() -> None:
    clear_attribute_rolls(session=session)


def _parse_character_attributes() -> tuple[dict[str, int] | None, str | None]:
    return parse_character_attributes(session=session, attribute_fields=ATTRIBUTE_FIELDS)


def _clear_pending_status_rolls() -> None:
    clear_pending_status_rolls(session=session)


def _apply_status_rolls(character_id: int, status_rolls: dict[str, int]) -> None:
    apply_status_rolls(
        character_id,
        status_rolls,
        session_scope=session_scope,
        character_model=Character,
        attribute_fields=ATTRIBUTE_FIELDS,
    )


def _character_meets_class_requirements(character: Character, class_definition: dict) -> tuple[bool, list[str]]:
    return character_meets_class_requirements(character, class_definition, attribute_fields=ATTRIBUTE_FIELDS)


def _get_class_by_slug(slug: str) -> dict | None:
    return get_class_by_slug(slug, classes=CLASSES)


def _translate_class_name(name: str | None) -> str:
    if not name:
        return ""
    return CLASS_NAME_TRANSLATIONS.get(name, name)


def _get_story_flags(character: Character) -> dict:
    return get_story_flags(character, narrative_get_story_flags=narrative_get_story_flags)


def _get_story_inventory(character: Character) -> list[dict]:
    return get_story_inventory(character, narrative_get_story_inventory=narrative_get_story_inventory)


def _get_pending_event(character: Character) -> dict | None:
    return get_pending_event(character, narrative_get_pending_event=narrative_get_pending_event)


def _persist_story_state(
    character_id: int,
    *,
    scene: str | None = None,
    act: int | None = None,
    flags: dict | None = None,
    inventory: list[dict] | None = None,
    xp_delta: int = 0,
    gold_delta: int = 0,
) -> None:
    persist_story_state(
        character_id,
        narrative_persist_story_state=narrative_persist_story_state,
        scene=scene,
        act=act,
        flags=flags,
        inventory=inventory,
        xp_delta=xp_delta,
        gold_delta=gold_delta,
    )


def _reset_campaign_state(character_id: int) -> None:
    with session_scope() as db_session:
        db_character = db_session.get(Character, character_id)
        if db_character is None:
            return

        db_character.story_scene = None
        db_character.story_act = 0
        db_character.story_flags = None
        db_character.story_inventory = None
        db_character.pending_event = None
        db_character.experience = 0
        db_character.gold = 0

        db_session.execute(delete(GameMessage).where(GameMessage.character_id == character_id))
        db_session.execute(delete(MemorySummary).where(MemorySummary.character_id == character_id))


def _groq_is_configured() -> bool:
    return groq_is_configured()


def _summarize_memory_if_needed(character: Character) -> None:
    summarize_memory_if_needed(
        character,
        narrative_summarize_memory_if_needed_with_llm=narrative_summarize_memory_if_needed_with_llm,
        narrative_summarize_memory_if_needed=narrative_summarize_memory_if_needed,
    )


def _apply_race_selection(character_id: int, selected_race: dict, roll_value: int | None = None) -> dict:
    return apply_race_selection(
        character_id,
        selected_race,
        roll_value,
        session_scope=session_scope,
        character_model=Character,
        clear_pending_status_rolls_callback=_clear_pending_status_rolls,
    )


def _login_user(user: User) -> None:
    login_user(user, session=session)


def _logout_user() -> None:
    logout_user(session=session)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Faca login para acessar essa area.", "error")
            return redirect(url_for("auth_routes.login"))
        return view(*args, **kwargs)

    return wrapped_view


def _post_login_redirect() -> str:
    if not session.get("has_character"):
        return url_for("player_routes.character_create")
    character = _get_character_by_user_id(session["user_id"])
    if character and character.onboarding_step == "race":
        return url_for("player_routes.race_select")
    if character and character.onboarding_step == "stats":
        return url_for("player_routes.status_page")
    if character and character.onboarding_step == "class":
        return url_for("player_routes.class_select")
    if character and character.class_name:
        return url_for("game_routes.game_play")
    return url_for("player_routes.player_home")


def create_app():
    auth_blueprint = create_auth_blueprint(
        normalize_email=_normalize_email,
        validate_birth_date=_validate_birth_date,
        password_is_strong=_password_is_strong,
        hash_password=_hash_password,
        verify_password=_verify_password,
        get_user_by_email=_get_user_by_email,
        get_character_by_user_id=_get_character_by_user_id,
        login_user=_login_user,
        logout_user=_logout_user,
        post_login_redirect=_post_login_redirect,
        session_scope=session_scope,
        user_model=User,
        integrity_error=IntegrityError,
    )
    player_blueprint = create_player_blueprint(
        login_required=login_required,
        attribute_fields=ATTRIBUTE_FIELDS,
        races=RACES,
        classes=CLASSES,
        character_model=Character,
        session_scope=session_scope,
        get_user_by_id=_get_user_by_id,
        get_character_by_user_id=_get_character_by_user_id,
        get_story_inventory=_get_story_inventory,
        get_attribute_rolls=_get_attribute_rolls,
        store_attribute_roll=_store_attribute_roll,
        clear_attribute_rolls=_clear_attribute_rolls,
        clear_pending_status_rolls=_clear_pending_status_rolls,
        apply_status_rolls=_apply_status_rolls,
        character_meets_class_requirements=_character_meets_class_requirements,
        get_class_by_slug=_get_class_by_slug,
        get_race_by_slug=_get_race_by_slug,
        special_race_is_locked=_special_race_is_locked,
        apply_race_selection=_apply_race_selection,
        post_login_redirect=_post_login_redirect,
    )
    game_blueprint = create_game_blueprint(
        login_required=login_required,
        attribute_fields=ATTRIBUTE_FIELDS,
        get_character_by_user_id=lambda: _get_character_by_user_id,
        post_login_redirect=_post_login_redirect,
        handle_game_play=lambda: narrative_handle_game_play,
        handle_game_master_chat=lambda: narrative_handle_game_master_chat,
        handle_game_roll=lambda: narrative_handle_game_roll,
        handle_game_roll_resolution=lambda: narrative_handle_game_roll_resolution,
        get_story_flags=lambda: _get_story_flags,
        get_story_inventory=lambda: _get_story_inventory,
        get_pending_event=lambda: _get_pending_event,
        persist_story_state=lambda: _persist_story_state,
        ensure_story_initialized=lambda: narrative_ensure_story_initialized,
        groq_is_configured=lambda: _groq_is_configured,
        summarize_memory_if_needed=lambda: _summarize_memory_if_needed,
        run_master_conversation=lambda: run_master_conversation,
        run_roll_start=lambda: run_roll_start,
        run_roll_resolution=lambda: run_roll_resolution,
        reset_campaign_state=lambda: _reset_campaign_state,
    )
    return build_flask_app(
        import_name=__name__,
        template_folder=str(FRONTEND_DIR),
        static_folder=str(FRONTEND_DIR),
        static_url_path="",
        secret_key=os.getenv("SECRET_KEY", "dev-secret-key"),
        auth_blueprint=auth_blueprint,
        player_blueprint=player_blueprint,
        game_blueprint=game_blueprint,
        translate_class_name=_translate_class_name,
    )


app = create_app()


def start_server() -> None:
    run_migrations()
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host=host, port=port, debug=debug)
