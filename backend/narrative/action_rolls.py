from __future__ import annotations

import re
import unicodedata

from game_content import MONSTERS
from models import Character


ATTRIBUTE_LABELS = {
    "strength": "FOR",
    "dexterity": "DEX",
    "constitution": "CON",
    "intelligence": "INT",
    "wisdom": "SAB",
    "charisma": "CAR",
    "perception": "PER",
}

MENTAL_ATTRIBUTES = ("intelligence", "wisdom", "charisma")
MAGIC_CLASS_ATTRIBUTE = {
    "wizard": "intelligence",
    "necromancer": "intelligence",
    "summoner": "intelligence",
    "bard": "charisma",
    "cleric": "wisdom",
    "druid": "wisdom",
    "monk": "wisdom",
}

ACTION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "combat_magic",
        (
            "magia",
            "feitico",
            "feiti",
            "conjuro",
            "conjurar",
            "invocar",
            "encantar",
            "amaldi",
            "raio",
            "bola de fogo",
            "canalizar",
            "ritual ofensivo",
        ),
    ),
    (
        "dialogue",
        (
            "falar",
            "conversar",
            "negoci",
            "convencer",
            "persuadir",
            "enganar",
            "mentir",
            "intimid",
            "gritar com",
            "amea",
            "perguntar",
            "responder",
        ),
    ),
    (
        "observe",
        (
            "perceber",
            "notar",
            "observar",
            "escutar",
            "ouvir",
            "farejar",
            "vigiar",
            "procurar sinais",
            "ver se",
            "examinar ao redor",
        ),
    ),
    (
        "investigate",
        (
            "investigar",
            "examinar",
            "analisar",
            "procurar pistas",
            "estudar",
            "inspecionar",
            "decifrar",
            "interpretar",
        ),
    ),
    (
        "move",
        (
            "mover",
            "empurrar",
            "puxar",
            "levantar",
            "arrastar",
            "carregar",
            "arrombar",
            "forcar a porta",
            "abrir a forca",
            "quebrar",
            "derrubar",
            "deslocar",
        ),
    ),
    (
        "combat",
        (
            "atacar",
            "golpear",
            "bater",
            "cortar",
            "esfaquear",
            "cravar",
            "dar um golpe",
            "investir contra",
            "acertar",
            "ferir",
            "lutar",
        ),
    ),
    (
        "defend",
        (
            "defender",
            "bloquear",
            "aparar",
            "proteger",
            "segurar o golpe",
            "ficar em guarda",
            "guardar posicao",
        ),
    ),
    (
        "escape",
        (
            "fugir",
            "escapar",
            "recuar",
            "correr",
            "sair daqui",
            "retirada",
            "me afastar",
        ),
    ),
    (
        "recover",
        (
            "curar",
            "meditar",
            "descansar",
            "recuperar",
            "respirar fundo",
            "me recompor",
        ),
    ),
    (
        "ritual",
        (
            "ritual",
            "rezar",
            "canalizar energia",
            "consagrar",
            "ativar o altar",
            "invocacao",
        ),
    ),
]


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.lower().strip()


def _class_slug(character: Character) -> str:
    return _fold_text(character.class_name or "").replace(" ", "-")


def _best_mental_attribute(character: Character) -> str:
    return max(MENTAL_ATTRIBUTES, key=lambda attribute: getattr(character, attribute))


def class_magic_attribute(character: Character) -> str:
    return MAGIC_CLASS_ATTRIBUTE.get(_class_slug(character), _best_mental_attribute(character))


def class_prefers_magic_combat(character: Character) -> bool:
    return _class_slug(character) in MAGIC_CLASS_ATTRIBUTE


def classify_player_action(player_message: str) -> str | None:
    folded = _fold_text(player_message)
    if not folded or folded.endswith("?"):
        if not any(keyword in folded for keyword in ("atacar", "falar", "mover", "observar", "investigar")):
            return None

    for action_kind, keywords in ACTION_PATTERNS:
        if any(keyword in folded for keyword in keywords):
            return action_kind
    return None


def choose_roll_attribute(character: Character, action_kind: str) -> str:
    if action_kind == "combat_magic":
        return class_magic_attribute(character)
    if action_kind == "combat":
        if class_prefers_magic_combat(character):
            return class_magic_attribute(character)
        return "strength"
    if action_kind == "observe":
        return "perception"
    if action_kind == "dialogue":
        return "charisma"
    if action_kind == "move":
        return "strength"
    if action_kind == "investigate":
        return "intelligence"
    if action_kind == "defend":
        return "constitution"
    if action_kind == "escape":
        return "dexterity"
    if action_kind == "recover":
        return "constitution"
    if action_kind == "ritual":
        return class_magic_attribute(character)
    return "perception"


def _difficulty_by_action(action_kind: str, authority: dict) -> int:
    base = {
        "combat": 13,
        "combat_magic": 13,
        "move": 12,
        "observe": 11,
        "investigate": 12,
        "dialogue": 11,
        "defend": 12,
        "escape": 13,
        "recover": 10,
        "ritual": 14,
    }.get(action_kind, 12)

    danger = str(authority.get("danger_level", "")).strip().lower()
    if danger == "high":
        base += 2
    elif danger == "elevated":
        base += 1
    return max(8, min(base, 20))


def _monster_slug_from_name(monster_name: str) -> str | None:
    folded_name = _fold_text(monster_name)
    for slug, monster in MONSTERS.items():
        if _fold_text(monster.get("name", "")) == folded_name:
            return slug
    return None


def _resolve_monster_context(authority: dict, llm_event: dict | None) -> tuple[str | None, str | None]:
    if isinstance(llm_event, dict):
        monster_slug = str(llm_event.get("monster_slug", "")).strip().lower() or None
        if monster_slug and monster_slug in MONSTERS:
            return monster_slug, MONSTERS[monster_slug]["name"]

        monster_name = str(llm_event.get("monster_name", "")).strip()
        if monster_name:
            inferred_slug = _monster_slug_from_name(monster_name)
            return inferred_slug, monster_name

    authority_target = str(authority.get("current_target", "")).strip()
    if not authority_target:
        return None, None
    monster_slug = _monster_slug_from_name(authority_target)
    return monster_slug, authority_target


def _build_roll_type(action_kind: str, attribute: str) -> str:
    roll_names = {
        "combat": "ataque",
        "combat_magic": "ataque magico",
        "move": "teste de movimento",
        "observe": "teste de percepcao",
        "investigate": "teste de investigacao",
        "dialogue": "teste social",
        "defend": "teste de defesa",
        "escape": "teste de fuga",
        "recover": "teste de recuperacao",
        "ritual": "teste de ritual",
    }
    return f"{roll_names.get(action_kind, 'teste')} ({ATTRIBUTE_LABELS[attribute]})"


def _build_stakes(action_kind: str, monster_name: str | None) -> str:
    if action_kind == "move":
        return "A forca do personagem vai decidir se ele consegue deslocar ou romper o obstaculo."
    if action_kind in {"combat", "combat_magic"} and monster_name:
        return f"O ataque precisa ser resolvido no dado antes de definir como {monster_name} reage."
    if action_kind in {"combat", "combat_magic"}:
        return "O ataque precisa ser resolvido no dado antes de definir se o golpe encaixa."
    if action_kind == "observe":
        return "A percepcao do personagem vai decidir o que ele realmente consegue notar no ambiente."
    if action_kind == "dialogue":
        return "O carisma do personagem vai decidir como a outra parte recebe suas palavras."
    if action_kind == "investigate":
        return "A analise do personagem vai decidir se pistas relevantes aparecem agora."
    if action_kind == "defend":
        return "A reacao defensiva precisa ser resolvida no dado antes de definir o custo da pressão."
    if action_kind == "escape":
        return "A fuga precisa ser resolvida no dado antes de definir se você abre distância."
    if action_kind == "recover":
        return "A tentativa de se recompor depende do controle do corpo sob pressão."
    if action_kind == "ritual":
        return "A canalizacao do poder precisa ser resolvida no dado antes de definir o efeito do ritual."
    return "A situação exige uma rolagem antes que a cena possa ser resolvida."


def normalize_pending_event(
    character: Character,
    player_message: str,
    authority: dict,
    llm_event: dict | None,
) -> dict | None:
    action_kind = classify_player_action(player_message)
    if action_kind is None and not isinstance(llm_event, dict):
        return None

    resolved_kind = action_kind
    if resolved_kind is None and isinstance(llm_event, dict):
        resolved_kind = "combat" if llm_event.get("type") == "encounter" else "investigate"

    if resolved_kind is None:
        return None

    attribute = choose_roll_attribute(character, resolved_kind)
    monster_slug, monster_name = _resolve_monster_context(authority, llm_event)
    event_type = "encounter" if resolved_kind in {"combat", "combat_magic"} and monster_slug else "skill_check"
    difficulty = _difficulty_by_action(resolved_kind, authority)

    if isinstance(llm_event, dict):
        try:
            difficulty = max(8, min(int(llm_event.get("difficulty", difficulty)), 20))
        except (TypeError, ValueError):
            pass

    event = {
        "type": event_type,
        "attribute": attribute,
        "difficulty": difficulty,
        "roll_type": _build_roll_type(resolved_kind, attribute),
        "label": ATTRIBUTE_LABELS[attribute],
        "stakes": _build_stakes(resolved_kind, monster_name),
        "action_kind": resolved_kind,
        "player_intent": re.sub(r"\s+", " ", player_message.strip())[:220],
    }

    if isinstance(llm_event, dict):
        for key in ("stakes", "player_intent"):
            value = str(llm_event.get(key, "")).strip()
            if value:
                event[key] = value

    if event_type == "encounter" and monster_slug:
        event["monster_slug"] = monster_slug
        event["monster_name"] = monster_name or MONSTERS[monster_slug]["name"]

    return event
