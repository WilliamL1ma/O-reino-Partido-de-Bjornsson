from __future__ import annotations


def get_race_by_slug(slug: str, *, races: list[dict]) -> dict | None:
    for race in races:
        if race["slug"] == slug:
            return race
    return None


def special_race_is_locked(character) -> bool:
    if character is None:
        return False
    return character.race_slug in {"anjo", "demonio"}


def get_attribute_rolls(*, session, attribute_fields: list[tuple[str, str]]) -> dict[str, int]:
    raw_rolls = session.get("character_attribute_rolls", {})
    valid_fields = {field_name for field_name, _label in attribute_fields}
    rolls: dict[str, int] = {}

    if not isinstance(raw_rolls, dict):
        return rolls

    for field_name, value in raw_rolls.items():
        if field_name not in valid_fields:
            continue
        if isinstance(value, int) and 1 <= value <= 20:
            rolls[field_name] = value

    return rolls


def store_attribute_roll(field_name: str, value: int, *, session, attribute_fields: list[tuple[str, str]]) -> None:
    rolls = get_attribute_rolls(session=session, attribute_fields=attribute_fields)
    rolls[field_name] = value
    session["character_attribute_rolls"] = rolls


def clear_attribute_rolls(*, session) -> None:
    session.pop("character_attribute_rolls", None)


def parse_character_attributes(*, session, attribute_fields: list[tuple[str, str]]) -> tuple[dict[str, int] | None, str | None]:
    attributes = get_attribute_rolls(session=session, attribute_fields=attribute_fields)
    required_fields = [field_name for field_name, _label in attribute_fields]

    if any(field_name not in attributes for field_name in required_fields):
        return None, "Role um d20 para cada status antes de criar a ficha."

    return attributes, None


def clear_pending_status_rolls(*, session) -> None:
    clear_attribute_rolls(session=session)


def apply_status_rolls(character_id: int, status_rolls: dict[str, int], *, session_scope, character_model, attribute_fields) -> None:
    with session_scope() as db_session:
        db_character = db_session.get(character_model, character_id)
        if db_character is None:
            return

        for field_name, _label in attribute_fields:
            setattr(db_character, field_name, status_rolls[field_name])

        db_character.onboarding_step = "class"


def character_meets_class_requirements(character, class_definition: dict, *, attribute_fields) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for field_name, minimum in class_definition.get("requirements", {}).items():
        current_value = getattr(character, field_name)
        if current_value < minimum:
            label = next((short for name, short in attribute_fields if name == field_name), field_name.upper())
            missing.append(f"{label} {minimum}")
    return len(missing) == 0, missing


def get_class_by_slug(slug: str, *, classes: list[dict]) -> dict | None:
    for class_definition in classes:
        if class_definition["slug"] == slug:
            return class_definition
    return None


def apply_race_selection(
    character_id: int,
    selected_race: dict,
    roll_value: int | None = None,
    *,
    session_scope,
    character_model,
    clear_pending_status_rolls_callback,
) -> dict:
    final_race_name = selected_race["name"]
    success = True
    race_status = "full"

    threshold = selected_race.get("threshold")
    if threshold is not None and roll_value is not None and roll_value < threshold:
        final_race_name = selected_race["inferior_name"]
        success = False
        race_status = "inferior"

    with session_scope() as db_session:
        db_character = db_session.get(character_model, character_id)
        db_character.race_slug = selected_race["slug"]
        db_character.race_name = final_race_name
        db_character.race_status = race_status
        db_character.onboarding_step = "stats"

    clear_pending_status_rolls_callback()

    return {
        "success": success,
        "final_race_name": final_race_name,
        "threshold": threshold,
        "roll_value": roll_value,
        "race_status": race_status,
    }
