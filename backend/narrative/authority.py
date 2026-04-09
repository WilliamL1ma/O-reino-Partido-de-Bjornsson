from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from game_content import MONSTERS


_MODE_ACTION_KINDS = {
    "exploration": ["observe", "investigate", "move", "dialogue", "recover"],
    "dialogue": ["dialogue", "observe", "investigate", "move"],
    "combat": ["combat", "defend", "escape", "observe"],
    "roll_pending": ["combat", "defend", "escape", "observe"],
    "post_combat": ["loot", "observe", "investigate", "move", "recover"],
    "puzzle": ["investigate", "ritual", "observe", "move"],
}

_ACTION_KEYWORDS = {
    "combat": ["atacar", "golpear", "investir", "ofensiva", "pressionar", "ferir", "intimidar"],
    "defend": ["defender", "guardar", "cobertura", "proteger", "bloquear", "posicao"],
    "escape": ["recuar", "fugir", "afastar", "retirada", "sair da area"],
    "loot": ["loot", "saque", "revistar", "vasculhar", "recolher", "corpo", "itens"],
    "observe": ["observar", "avaliar", "medir", "escutar", "vigiar", "ler o terreno"],
    "investigate": ["examinar", "investigar", "procurar", "analisar", "rastro", "pistas"],
    "dialogue": ["falar", "responder", "perguntar", "negociar", "conversar", "dialogo"],
    "move": ["seguir", "avancar", "mudar de posicao", "aproximar", "contornar", "prosseguir"],
    "recover": ["respirar", "descansar", "curar", "recompor", "recuperar"],
    "ritual": ["simbolo", "enigma", "altar", "espelho", "ritual", "hipotese"],
}

_GENERIC_ENTITY_TERMS = [
    "gato",
    "criatura",
    "alvo",
    "guardiao",
    "goblin",
    "lobo",
    "duende",
    "aranha",
    "cobra",
    "raposa",
    "passaro",
    "lobisomem",
    "lupus",
]

_PERSISTABLE_ACTION_KINDS = {kind for action_kinds in _MODE_ACTION_KINDS.values() for kind in action_kinds}


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.lower().strip()


def _extract_target_from_messages(recent_messages: Iterable[dict], scene_lead: str) -> str | None:
    known_names = {monster["name"]: _fold_text(monster["name"]) for monster in MONSTERS.values()}
    texts: list[str] = [scene_lead]
    for message in recent_messages:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content", "")).strip()
        if content:
            texts.append(content)

    for text in reversed(texts):
        folded = _fold_text(text)
        for monster_name, folded_name in known_names.items():
            if folded_name in folded:
                return monster_name

    generic_match = re.search(r"\b(" + "|".join(_GENERIC_ENTITY_TERMS) + r")\b", _fold_text(scene_lead))
    if generic_match:
        return generic_match.group(1)
    return None


def _coerce_allowed_action_kinds(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    allowed: list[str] = []
    for item in value:
        action_kind = str(item).strip()
        if action_kind in _PERSISTABLE_ACTION_KINDS and action_kind not in allowed:
            allowed.append(action_kind)
    return allowed


def _same_scene_snapshot(scene_key: str, persisted_authority: dict | None) -> dict:
    if not isinstance(persisted_authority, dict):
        return {}

    persisted_scene_key = str(persisted_authority.get("scene_key", "")).strip()
    if persisted_scene_key != scene_key:
        return {}

    return persisted_authority


def _derive_target_truth(
    *,
    scene_key: str,
    scene_lead: str,
    recent_messages: Iterable[dict],
    pending_event: dict | None,
    context_hint: dict | None,
    recent_reward: dict | None,
    persisted_authority: dict | None,
) -> tuple[str | None, str]:
    snapshot = _same_scene_snapshot(scene_key, persisted_authority)
    snapshot_target = str(snapshot.get("current_target", "")).strip() or None

    if pending_event and pending_event.get("monster_name"):
        return str(pending_event["monster_name"]), "pending_event"
    if context_hint and context_hint.get("monster_name"):
        return str(context_hint["monster_name"]), "context_hint"
    if recent_reward and recent_reward.get("monster_name"):
        return str(recent_reward["monster_name"]), "recent_reward"
    if snapshot_target:
        return snapshot_target, "authority_snapshot"

    return _extract_target_from_messages(recent_messages, scene_lead), "text_history"


def _extract_inventory_names(inventory: list[dict] | None) -> list[str]:
    if not isinstance(inventory, list):
        return []

    names: list[str] = []
    for item in inventory:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return names[:12]


def _extract_referenced_target(text: str) -> str | None:
    folded = _fold_text(text)
    if not folded:
        return None

    for monster in MONSTERS.values():
        monster_name = str(monster.get("name", "")).strip()
        folded_name = _fold_text(monster_name)
        if folded_name and folded_name in folded:
            return folded_name

    generic_match = re.search(r"\b(" + "|".join(_GENERIC_ENTITY_TERMS) + r")\b", folded)
    if generic_match:
        return generic_match.group(1)
    return None


def _target_conflicts(referenced_target: str | None, current_target: str) -> bool:
    if not referenced_target or not current_target:
        return False
    return referenced_target not in current_target and current_target not in referenced_target


def _detect_dialogue_context(recent_messages: Iterable[dict]) -> bool:
    dialogue_signals = [
        "quem voce e",
        "quem e voce",
        "responde",
        "pergunta",
        "fala em",
        "conversa",
        "negocia",
        "dialogo",
    ]
    for message in recent_messages:
        if not isinstance(message, dict):
            continue
        content = _fold_text(str(message.get("content", "")))
        if any(signal in content for signal in dialogue_signals):
            return True
    return False


def _determine_interaction_mode(
    scene_type: str,
    pending_event: dict | None,
    context_hint: dict | None,
    recent_reward: dict | None,
    recent_messages: Iterable[dict],
    persisted_authority: dict | None = None,
) -> str:
    snapshot_mode = str((persisted_authority or {}).get("interaction_mode", "")).strip()
    if pending_event:
        return "roll_pending"
    if recent_reward:
        return "post_combat"
    if context_hint and context_hint.get("kind") == "post_encounter":
        return "post_combat"
    if snapshot_mode:
        return snapshot_mode
    if scene_type == "encounter":
        return "dialogue" if _detect_dialogue_context(recent_messages) else "combat"
    if scene_type == "puzzle":
        return "puzzle"
    if _detect_dialogue_context(recent_messages):
        return "dialogue"
    return "exploration"


def _determine_danger_level(
    scene_type: str,
    pending_event: dict | None,
    interaction_mode: str,
    persisted_authority: dict | None = None,
) -> str:
    if pending_event and pending_event.get("type") == "encounter":
        return "high"
    if interaction_mode == "combat":
        return "elevated"
    if interaction_mode == "post_combat":
        return "medium"
    if scene_type == "puzzle":
        return "medium"
    persisted_danger = str((persisted_authority or {}).get("danger_level", "")).strip()
    return persisted_danger or "low"


def _determine_recent_outcome(
    pending_event: dict | None,
    recent_reward: dict | None,
    context_hint: dict | None,
    persisted_authority: dict | None = None,
) -> str:
    if pending_event:
        return "awaiting_roll"
    if recent_reward:
        return "victory"
    if context_hint and context_hint.get("kind") == "post_encounter":
        return "victory"

    persisted_outcome = str((persisted_authority or {}).get("recent_outcome", "")).strip()
    return persisted_outcome or "ongoing"


def _mode_transition_signal(
    interaction_mode: str,
    pending_event: dict | None,
    recent_reward: dict | None,
    context_hint: dict | None,
    persisted_authority: dict | None = None,
) -> str:
    if pending_event:
        return "pending_roll"
    if interaction_mode == "post_combat" and recent_reward:
        return "post_combat_loot_window"
    if interaction_mode == "post_combat" and context_hint and context_hint.get("kind") == "post_encounter":
        return "post_combat_resolution"
    if interaction_mode == "combat":
        return "active_threat"

    snapshot_signal = str((persisted_authority or {}).get("mode_transition_signal", "")).strip()
    return snapshot_signal or "stable"


def build_narrative_authority(
    *,
    scene_key: str,
    scene: dict,
    allowed_next_scenes: list[str],
    recent_messages: list[dict],
    pending_event: dict | None,
    context_hint: dict | None,
    recent_reward: dict | None,
    inventory: list[dict] | None = None,
    persisted_authority: dict | None = None,
) -> dict:
    scene_type = str(scene.get("type", "narrative"))
    scene_lead = str(scene.get("lead", ""))
    snapshot = _same_scene_snapshot(scene_key, persisted_authority)
    current_target, target_source = _derive_target_truth(
        scene_key=scene_key,
        scene_lead=scene_lead,
        recent_messages=recent_messages,
        pending_event=pending_event,
        context_hint=context_hint,
        recent_reward=recent_reward,
        persisted_authority=snapshot,
    )
    interaction_mode = _determine_interaction_mode(
        scene_type,
        pending_event,
        context_hint,
        recent_reward,
        recent_messages,
        snapshot,
    )
    interaction_mode = interaction_mode if interaction_mode in _MODE_ACTION_KINDS else "exploration"
    allowed_action_kinds = _coerce_allowed_action_kinds(snapshot.get("allowed_action_kinds"))
    if not allowed_action_kinds:
        allowed_action_kinds = list(_MODE_ACTION_KINDS.get(interaction_mode, _MODE_ACTION_KINDS["exploration"]))
    loot_names = recent_reward.get("loot_names", []) if isinstance(recent_reward, dict) else []
    persisted_locked = bool(snapshot.get("target_locked"))
    target_locked = current_target is not None and (
        pending_event is not None
        or recent_reward is not None
        or (context_hint and context_hint.get("kind") == "post_encounter")
        or persisted_locked
        or interaction_mode in {"combat", "roll_pending", "post_combat", "dialogue"}
    )
    mode_transition_signal = _mode_transition_signal(
        interaction_mode,
        pending_event,
        recent_reward,
        context_hint,
        snapshot,
    )
    scene_phase = str(snapshot.get("scene_phase", "")).strip() or interaction_mode

    return {
        "current_target": current_target,
        "target_source": target_source,
        "interaction_type": interaction_mode,
        "interaction_mode": interaction_mode,
        "danger_level": _determine_danger_level(scene_type, pending_event, interaction_mode, snapshot),
        "recent_outcome": _determine_recent_outcome(pending_event, recent_reward, context_hint, snapshot),
        "mode_transition_signal": mode_transition_signal,
        "allowed_action_kinds": allowed_action_kinds,
        "target_locked": target_locked,
        "post_combat_pending_loot": interaction_mode == "post_combat" and bool(loot_names),
        "inventory_truth": _extract_inventory_names(inventory),
        "recent_reward_truth": {
            "monster_name": recent_reward.get("monster_name") if isinstance(recent_reward, dict) else None,
            "loot_names": loot_names if isinstance(loot_names, list) else [],
        },
        "pending_event_truth": {
            "type": pending_event.get("type"),
            "attribute": pending_event.get("attribute"),
            "monster_name": pending_event.get("monster_name"),
        }
        if isinstance(pending_event, dict)
        else None,
        "current_scene_state": {
            "scene_key": scene_key,
            "scene_type": scene_type,
            "scene_phase": scene_phase,
            "scene_title": scene.get("title"),
            "scene_lead": scene.get("lead"),
            "allowed_next_scenes": allowed_next_scenes,
            "has_pending_event": pending_event is not None,
            "has_recent_reward": recent_reward is not None,
            "context_hint_kind": context_hint.get("kind") if isinstance(context_hint, dict) else None,
        },
    }


def build_scene_fallback_actions(scene_key: str, authority: dict, context_hint: dict | None = None) -> list[str]:
    current_target = authority.get("current_target") or "a ameaca diante de voce"
    mode = authority.get("interaction_mode")

    if context_hint and context_hint.get("kind") == "post_encounter":
        current_target = context_hint.get("monster_name") or current_target

    if mode == "post_combat":
        return [
            f"Revistar com calma o corpo de {current_target}",
            "Observar os arredores antes de sair do local",
            "Procurar rastros ou sinais de outra ameaca por perto",
            "Recolher o que for util e seguir com cautela",
            "Parar por um instante para recuperar o folego",
        ]

    if mode in {"combat", "roll_pending"}:
        return [
            f"Medir a reacao imediata de {current_target}",
            "Ajustar sua posicao antes de se expor demais",
            "Ler o terreno e os sinais ao redor do confronto",
            "Decidir entre pressionar, defender ou recuar",
            "Observar se existe outra ameaca surgindo na cena",
        ]

    if mode == "dialogue":
        return [
            "Responder com calma e manter o mesmo tom da interacao",
            "Fazer uma pergunta curta para esclarecer a situacao",
            "Observar linguagem corporal, distancia e risco imediato",
            "Buscar uma forma segura de continuar a conversa",
            "Decidir se vale manter o contato ou encerrar a aproximacao",
        ]

    if mode == "puzzle":
        return [
            "Examinar os simbolos e os detalhes mais incomuns",
            "Relacionar a cena atual com pistas ja vistas antes",
            "Testar uma hipotese sem forcar a resolucao",
            "Observar o ambiente por mecanismos, espelhos ou marcas",
            "Recuar um passo e reorganizar o raciocinio antes de agir",
        ]

    defaults = {
        "chapter_entry": [
            "Ir ate a taverna mais proxima",
            "Observar a praca e o movimento das ruas",
            "Falar com um guarda sobre a cidade",
            "Caminhar pelas vielas e ouvir rumores",
            "Perguntar onde conseguir abrigo ou trabalho",
        ],
        "chapter_complete": [
            "Revisar a propria ficha e os itens obtidos",
            "Refletir sobre o legado descoberto",
            "Buscar um novo rumo em Elandoria",
        ],
    }
    return defaults.get(
        scene_key,
        [
            "Observar melhor o ambiente",
            "Falar com a pessoa mais proxima",
            "Investigar sinais, rastros ou marcas",
            "Avancar com cautela",
            "Parar um instante para reavaliar o caminho",
        ],
    )


def _extract_action_text(item: object) -> str:
    if isinstance(item, dict):
        for key in ("acao", "a\u00e7\u00e3o", "action", "label", "text", "title", "name", "summary"):
            value = item.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
        return ""
    return str(item).strip()


def _classify_action_kind(action: str) -> str | None:
    folded = _fold_text(action)
    for kind, keywords in _ACTION_KEYWORDS.items():
        if any(keyword in folded for keyword in keywords):
            return kind
    return None


def sanitize_suggested_actions(actions: object, authority: dict, fallback_actions: list[str]) -> list[str]:
    if not isinstance(actions, list):
        return fallback_actions[:5]

    allowed = set(authority.get("allowed_action_kinds", []))
    mode = authority.get("interaction_mode")
    current_target = _fold_text(str(authority.get("current_target") or ""))
    target_locked = bool(authority.get("target_locked"))
    sanitized: list[str] = []

    for item in actions:
        text = _extract_action_text(item)
        if not text or text in sanitized:
            continue

        kind = _classify_action_kind(text)
        if kind and kind not in allowed:
            continue

        folded = _fold_text(text)
        referenced_target = _extract_referenced_target(text)
        if target_locked and _target_conflicts(referenced_target, current_target):
            continue

        if mode == "post_combat" and any(
            keyword in folded for keyword in ["falar", "negociar", "interrogar", "convencer", "intimidar"]
        ):
            if not current_target or current_target in folded:
                continue

        sanitized.append(text)
        if len(sanitized) == 5:
            break

    return sanitized or fallback_actions[:5]
