from __future__ import annotations

from game_content import CHAPTER_SCENES


SCENE_TRANSITIONS = {
    "chapter_entry": ["encounter_goblin", "encounter_robalo", "act_two_crossroads"],
    "encounter_goblin": ["act_two_crossroads"],
    "encounter_robalo": ["act_two_crossroads"],
    "act_two_crossroads": ["encounter_duende", "encounter_cobra", "encounter_raposa", "act_three_threshold"],
    "encounter_duende": ["act_three_threshold"],
    "encounter_cobra": ["act_three_threshold"],
    "encounter_raposa": ["act_two_crossroads", "act_three_threshold"],
    "act_three_threshold": ["encounter_aranha", "encounter_lupus", "encounter_passaro", "freya_legacy"],
    "encounter_aranha": ["freya_legacy"],
    "encounter_lupus": ["freya_legacy"],
    "encounter_passaro": ["act_three_threshold", "freya_legacy"],
    "freya_legacy": ["encounter_lobisomem", "chapter_complete"],
    "encounter_lobisomem": ["chapter_complete"],
    "chapter_complete": [],
}


ENCOUNTER_TRANSITIONS = {
    "encounter_goblin": {"monster": "goblin-cacador", "next_scene": "act_two_crossroads"},
    "encounter_robalo": {"monster": "robalo-riva-sombria", "next_scene": "act_two_crossroads"},
    "encounter_duende": {"monster": "duende-bosque", "next_scene": "act_three_threshold"},
    "encounter_cobra": {"monster": "cobra-veneno", "next_scene": "act_three_threshold"},
    "encounter_raposa": {"monster": "raposa-fogo", "next_scene": "act_two_crossroads", "flag": "act_two_farm_done"},
    "encounter_aranha": {"monster": "aranha-fogo", "next_scene": "freya_legacy"},
    "encounter_lupus": {"monster": "lupus", "next_scene": "freya_legacy"},
    "encounter_passaro": {"monster": "passaro-assassino", "next_scene": "act_three_threshold", "flag": "act_three_farm_done"},
    "encounter_lobisomem": {"monster": "lobisomem-jovem", "next_scene": "chapter_complete", "flag": "final_guardian_defeated"},
}


def allowed_next_scenes(scene_key: str) -> list[str]:
    return SCENE_TRANSITIONS.get(scene_key, [])


def get_encounter_transition(scene_key: str) -> dict | None:
    transition = ENCOUNTER_TRANSITIONS.get(scene_key)
    return dict(transition) if transition else None


def build_scene_context(scene_key: str, flags: dict, inventory: list[dict]) -> dict:
    scene = CHAPTER_SCENES.get(scene_key, CHAPTER_SCENES["chapter_entry"]).copy()

    options = list(scene.get("options", []))
    if scene_key == "act_two_crossroads" and flags.get("act_two_farm_done"):
        options = [option for option in options if option["action"] != "go_raposa"]
    if scene_key == "act_three_threshold" and flags.get("act_three_farm_done"):
        options = [option for option in options if option["action"] != "go_passaro"]

    scene["options"] = options
    scene["inventory"] = inventory
    scene["flags"] = flags
    return scene


def initial_story_state(existing_inventory: list[dict]) -> dict:
    return {
        "scene": "chapter_entry",
        "act": 1,
        "flags": {"chapter_started": True},
        "inventory": existing_inventory,
    }
