from __future__ import annotations

import json
import random
from collections.abc import Callable

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for


def create_player_blueprint(
    *,
    login_required,
    attribute_fields: list[tuple[str, str]],
    races: list[dict],
    classes: list[dict],
    character_model,
    session_scope,
    get_user_by_id: Callable[[int], object | None],
    get_character_by_user_id: Callable[[int], object | None],
    get_story_inventory: Callable[[object], list[dict]],
    get_attribute_rolls: Callable[[], dict[str, int]],
    store_attribute_roll: Callable[[str, int], None],
    clear_attribute_rolls: Callable[[], None],
    clear_pending_status_rolls: Callable[[], None],
    apply_status_rolls: Callable[[int, dict[str, int]], None],
    character_meets_class_requirements: Callable[[object, dict], tuple[bool, list[str]]],
    get_class_by_slug: Callable[[str], dict | None],
    get_race_by_slug: Callable[[str], dict | None],
    special_race_is_locked: Callable[[object | None], bool],
    apply_race_selection: Callable[[int, dict, int | None], dict],
    post_login_redirect: Callable[[], str],
) -> Blueprint:
    blueprint = Blueprint("player_routes", __name__)

    @blueprint.get("/jogador", endpoint="player_home")
    @login_required
    def player_home():
        user = get_user_by_id(session["user_id"])
        character = get_character_by_user_id(session["user_id"])
        if user is None:
            session.clear()
            flash("Sua sessão não é mais válida.", "error")
            return redirect(url_for("auth_routes.login"))

        if character is None:
            return redirect(url_for(".character_create"))

        return render_template(
            "player_home.html",
            user=user,
            character=character,
            attribute_fields=attribute_fields,
            pending_status_rolls=get_attribute_rolls(),
        )

    @blueprint.get("/jogador/status", endpoint="status_page")
    @login_required
    def status_page():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return redirect(url_for(".character_create"))
        if not character.race_slug:
            return redirect(url_for(".race_select"))
        if character.onboarding_step == "class":
            return redirect(url_for(".class_select"))
        if character.class_name:
            return redirect(url_for("game_routes.game_play"))

        return render_template(
            "status_page.html",
            character=character,
            attribute_fields=attribute_fields,
            pending_status_rolls=get_attribute_rolls(),
        )

    @blueprint.route("/jogador/classe", methods=["GET", "POST"], endpoint="class_select")
    @login_required
    def class_select():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return redirect(url_for(".character_create"))
        if not character.race_slug:
            return redirect(url_for(".race_select"))
        if character.onboarding_step == "stats":
            return redirect(url_for(".status_page"))
        if character.class_name:
            return redirect(url_for("game_routes.game_play"))

        if request.method == "POST":
            class_slug = request.form.get("class", "").strip()
            class_definition = get_class_by_slug(class_slug)
            if class_definition is None:
                flash("Escolha uma classe válida.", "error")
                return redirect(url_for(".class_select"))

            allowed, missing = character_meets_class_requirements(character, class_definition)
            if not allowed:
                flash(f"Seu personagem ainda não atende os requisitos: {', '.join(missing)}.", "error")
                return redirect(url_for(".class_select"))

            with session_scope() as db_session:
                db_character = db_session.get(character_model, character.id)
                db_character.class_name = class_definition["name"]
                db_character.onboarding_step = "complete"
                if not db_character.story_scene:
                    db_character.story_scene = "chapter_entry"
                    db_character.story_act = 1
                    db_character.story_flags = json.dumps({"chapter_started": True}, ensure_ascii=True)
                if db_character.story_inventory is None:
                    db_character.story_inventory = json.dumps([], ensure_ascii=True)

                flash(f"Classe {class_definition.get('display_name', class_definition['name'])} escolhida com sucesso.", "success")
                return redirect(url_for("game_routes.game_play"))

        class_cards = []
        for class_definition in classes:
            allowed, missing = character_meets_class_requirements(character, class_definition)
            class_cards.append(
                {
                    **class_definition,
                    "display_name": class_definition.get("display_name", class_definition["name"]),
                    "allowed": allowed,
                    "missing": missing,
                }
            )

        return render_template("class_select.html", character=character, classes=class_cards)

    @blueprint.get("/jogador/ficha-completa", endpoint="character_sheet")
    @login_required
    def character_sheet():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return redirect(url_for(".character_create"))
        if not character.class_name:
            return redirect(post_login_redirect())

        return render_template(
            "character_sheet.html",
            character=character,
            attribute_fields=attribute_fields,
            inventory=get_story_inventory(character),
        )

    @blueprint.route("/jogador/ficha", methods=["GET", "POST"], endpoint="character_create")
    @login_required
    def character_create():
        existing_character = get_character_by_user_id(session["user_id"])
        if existing_character is not None:
            session["has_character"] = True
            clear_pending_status_rolls()
            clear_attribute_rolls()
            return redirect(post_login_redirect())

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            age_raw = request.form.get("age", "").strip()
            personality = request.form.get("personality", "").strip()
            objective = request.form.get("objective", "").strip()
            fear = request.form.get("fear", "").strip()

            if not name or not age_raw:
                flash("Preencha pelo menos o nome e a idade do personagem.", "error")
                return redirect(url_for(".character_create"))

            if not age_raw.isdigit():
                flash("Informe uma idade válida em números.", "error")
                return redirect(url_for(".character_create"))

            age = int(age_raw)
            if age < 10 or age > 120:
                flash("A idade do personagem deve estar entre 10 e 120 anos.", "error")
                return redirect(url_for(".character_create"))

            with session_scope() as db_session:
                character = character_model(
                    user_id=session["user_id"],
                    name=name,
                    age=age,
                    personality=personality or None,
                    objective=objective or None,
                    fear=fear or None,
                    onboarding_step="race",
                )
                db_session.add(character)

            session["has_character"] = True
            flash("Ficha criada com sucesso. O próximo passo será escolher sua raça.", "success")
            return redirect(url_for(".race_select"))

        return render_template("character_create.html")

    @blueprint.post("/jogador/status/rolar", endpoint="character_roll_status")
    @login_required
    def character_roll_status():
        existing_character = get_character_by_user_id(session["user_id"])
        if existing_character is not None:
            return jsonify({"ok": False, "message": "A ficha já foi criada para esta conta."}), 400

        field_name = request.form.get("attribute", "").strip()
        valid_fields = {name for name, _label in attribute_fields}
        if field_name not in valid_fields:
            return jsonify({"ok": False, "message": "Status inválido para rolagem."}), 400

        current_rolls = get_attribute_rolls()
        if field_name in current_rolls:
            return jsonify({"ok": False, "message": "Esse status já foi rolado e não pode ser repetido."}), 400

        rolled_value = random.randint(1, 20)
        store_attribute_roll(field_name, rolled_value)

        return jsonify(
            {
                "ok": True,
                "attribute": field_name,
                "roll": rolled_value,
                "remaining": len(attribute_fields) - len(get_attribute_rolls()),
                "message": f"{field_name.upper()} recebeu {rolled_value} no d20.",
            }
        )

    @blueprint.post("/jogador/status/rolar-modal", endpoint="character_roll_status_modal")
    @login_required
    def character_roll_status_modal():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return jsonify({"ok": False, "message": "Crie a ficha antes de rolar os status."}), 400
        if not character.race_slug:
            return jsonify({"ok": False, "message": "Escolha a raça antes de rolar os status."}), 400
        if character.class_name:
            return jsonify({"ok": False, "message": "A classe já foi definida para este personagem."}), 400
        if character.onboarding_step == "class":
            return jsonify({"ok": False, "message": "Os status já foram rolados para este personagem."}), 400

        current_rolls = get_attribute_rolls()
        next_field = None
        next_label = None
        for field_name, label in attribute_fields:
            if field_name not in current_rolls:
                next_field = field_name
                next_label = label
                break

        if next_field is None or next_label is None:
            apply_status_rolls(character.id, current_rolls)
            clear_pending_status_rolls()
            return jsonify(
                {
                    "ok": True,
                    "completed": True,
                    "next_url": url_for(".class_select"),
                    "message": "Todos os status já foram definidos.",
                }
            )

        rolled_value = random.randint(1, 20)
        store_attribute_roll(next_field, rolled_value)
        updated_rolls = get_attribute_rolls()
        completed = len(updated_rolls) == len(attribute_fields)

        if completed:
            apply_status_rolls(character.id, updated_rolls)
            clear_pending_status_rolls()

        return jsonify(
            {
                "ok": True,
                "attribute": next_field,
                "label": next_label,
                "roll": rolled_value,
                "completed": completed,
                "remaining": len(attribute_fields) - len(updated_rolls),
                "next_url": url_for(".class_select") if completed else None,
                "message": f"{next_label} recebeu {rolled_value} no d20.",
            }
        )

    @blueprint.post("/jogador/resetar-criacao", endpoint="character_reset")
    @login_required
    def character_reset():
        existing_character = get_character_by_user_id(session["user_id"])

        if existing_character is not None and existing_character.class_name:
            flash("A criação não pode mais ser resetada depois que a classe foi definida.", "error")
            return redirect(url_for("game_routes.game_play"))

        if existing_character is not None:
            with session_scope() as db_session:
                db_character = db_session.get(character_model, existing_character.id)
                if db_character is not None:
                    db_session.delete(db_character)
            session["has_character"] = False

        clear_attribute_rolls()
        flash("A criação do personagem foi resetada. Você pode começar tudo do zero.", "success")
        return redirect(url_for(".character_create"))

    @blueprint.route("/jogador/raca", methods=["GET", "POST"], endpoint="race_select")
    @login_required
    def race_select():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return redirect(url_for(".character_create"))
        if character.class_name:
            flash("A raça foi bloqueada porque a classe já foi definida.", "error")
            return redirect(url_for(".player_home"))
        if special_race_is_locked(character):
            flash("Depois de arriscar a sorte com Anjo ou Demonio, a raça fica bloqueada mesmo antes da classe.", "error")
            return redirect(url_for(".player_home"))

        if request.method == "POST":
            race_slug = request.form.get("race", "").strip()
            selected_race = get_race_by_slug(race_slug)
            if selected_race is None:
                flash("Escolha uma raça válida para continuar.", "error")
                return redirect(url_for(".race_select"))

            if selected_race.get("threshold") is not None:
                flash("Essa raça exige uma rolagem especial. Use o modal para concluir a escolha.", "error")
                return redirect(url_for(".race_select"))

            result = apply_race_selection(character.id, selected_race, None)
            flash(f"Raça {result['final_race_name']} escolhida com sucesso. A próxima etapa será rolar os status.", "success")
            return redirect(url_for(".status_page"))

        return render_template("race_select.html", character=character, races=races)

    @blueprint.post("/jogador/raca/rolar", endpoint="race_roll")
    @login_required
    def race_roll():
        character = get_character_by_user_id(session["user_id"])
        if character is None:
            return jsonify({"ok": False, "message": "Crie sua ficha antes de escolher uma raça."}), 400
        if character.class_name:
            return jsonify({"ok": False, "message": "A raça não pode mais ser alterada após definir a classe."}), 400
        if special_race_is_locked(character):
            return jsonify(
                {
                    "ok": False,
                    "message": "Depois de arriscar a sorte com Anjo ou Demônio, a raça fica bloqueada até o restante do onboarding.",
                }
            ), 400

        race_slug = request.form.get("race", "").strip()
        selected_race = get_race_by_slug(race_slug)
        if selected_race is None or selected_race.get("threshold") is None:
            return jsonify({"ok": False, "message": "Essa raça não usa rolagem especial."}), 400

        roll_value = random.randint(1, 20)
        result = apply_race_selection(character.id, selected_race, roll_value)
        return jsonify(
            {
                "ok": True,
                "roll": result["roll_value"],
                "threshold": result["threshold"],
                "success": result["success"],
                "selected_race": selected_race["name"],
                "final_race_name": result["final_race_name"],
                "next_url": url_for(".status_page"),
                "message": (
                    f"Você tirou {result['roll_value']} e permaneceu como {result['final_race_name']}."
                    if result["success"]
                    else f"Você tirou {result['roll_value']} e se tornou {result['final_race_name']}."
                ),
            }
        )

    return blueprint
