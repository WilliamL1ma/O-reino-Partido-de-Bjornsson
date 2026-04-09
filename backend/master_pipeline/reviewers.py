from __future__ import annotations

from dataclasses import dataclass
import re

from master_graph_components.review import (
    actions_are_too_generic,
    actions_contradict_narration,
    build_consistency_fallback,
    contextual_actions_from_narration,
    entity_continuity_broken,
    looks_like_model_refusal,
    physical_causality_broken,
)
from master_graph_components.parser import strip_json_artifacts
from master_graph_components.parser import normalize_narrative_dialogue
from narrative.authority import sanitize_suggested_actions


@dataclass(frozen=True)
class ReviewResult:
    valid: bool
    feedback: str = ""


_ANACHRONISM_PATTERNS = [
    r"\bgarrafa(?: de agua)?\b",
    r"\bplastico\b",
    r"\btelefone\b",
    r"\bcelular\b",
    r"\bcarro\b",
    r"\bmotor\b",
    r"\bgasolina\b",
    r"\belevador\b",
    r"\bpistola\b",
    r"\brev[óo]lver\b",
]

_ENGLISH_ACTION_PATTERNS = [
    r"\bthe\b",
    r"\bwhile\b",
    r"\bstrike\b",
    r"\bleap\b",
    r"\bchannel\b",
    r"\buse\b",
    r"\bcreate\b",
    r"\bopening\b",
    r"\bagainst\b",
]


def _narration_wrapped_in_quotes(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.startswith('"') and stripped.count('"') <= 2


def _contains_anachronism(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _ANACHRONISM_PATTERNS)


def _looks_like_english_actions(actions: list[str]) -> bool:
    for action in actions:
        lowered = action.lower()
        hits = sum(1 for pattern in _ENGLISH_ACTION_PATTERNS if re.search(pattern, lowered))
        if hits >= 2:
            return True
    return False


def review_narration(
    *,
    narration: str,
    player_message: str,
    recent_messages: list[dict],
) -> ReviewResult:
    feedback: list[str] = []
    cleaned = strip_json_artifacts(narration)
    cleaned = normalize_narrative_dialogue(cleaned)

    if not cleaned.strip():
        feedback.append("A narração ficou vazia.")
    if narration != cleaned:
        feedback.append("Remova JSON cru, markdown tecnico ou estruturas internas vazadas.")
    if re.search(r"\b(next_scene|story_event)\b", cleaned, flags=re.IGNORECASE):
        feedback.append("Remova marcadores tecnicos como next_scene ou story_event do texto visivel ao jogador.")
    if _narration_wrapped_in_quotes(cleaned):
        feedback.append("A narração do mestre veio inteira entre aspas. Deixe aspas apenas em falas de personagens.")
    if looks_like_model_refusal(narration):
        feedback.append("A narração virou recusa do modelo. Continue a cena normalmente.")
    if entity_continuity_broken(narration, player_message, recent_messages):
        feedback.append("A narração trocou a entidade em foco sem base no contexto.")
    if physical_causality_broken(player_message, narration):
        feedback.append("A narração quebrou a causalidade física imediata da cena.")
    if _contains_anachronism(cleaned):
        feedback.append("A narração usou objeto ou referencia anacronica para fantasia medieval. Troque por equivalente coerente com o mundo.")
    return ReviewResult(valid=not feedback, feedback=" ".join(feedback).strip())


def review_suggestions(
    *,
    actions: list[str],
    narration: str,
    authority: dict,
    fallback_actions: list[str],
) -> tuple[list[str], ReviewResult]:
    sanitized = sanitize_suggested_actions(actions, authority, fallback_actions)
    feedback: list[str] = []

    if len(sanitized) < 2 or len(sanitized) > 5:
        feedback.append("As sugestões devem trazer de 2 a 5 opções.")
    if actions_contradict_narration(sanitized, narration):
        feedback.append("As sugestões contradizem a narração final.")
    if actions_are_too_generic(sanitized, fallback_actions):
        feedback.append("As sugestões ficaram genéricas ou coladas no fallback.")
    if _looks_like_english_actions(sanitized):
        feedback.append("As sugestões vieram em inglês. Reescreva todas em português do Brasil.")

    contextual = contextual_actions_from_narration(narration)
    if contextual and sanitized == fallback_actions[:5]:
        feedback.append("As sugestões não acompanharam o momento narrado.")

    return sanitized, ReviewResult(valid=not feedback, feedback=" ".join(feedback).strip())


def build_narrative_fallback(state: dict) -> str:
    mode = state.get("mode")
    if mode == "intro":
        return (
            f"Voce esta em {state.get('scene_title', 'um novo ponto da jornada')}. "
            f"{state.get('scene_lead', 'O lugar exige atenção imediata enquanto a história comeca a se mover diante de você.')}"
        ).strip()
    if mode == "resolution":
        resolution = state.get("roll_resolution", {})
        outcome = str(resolution.get("outcome", "")).strip() or "resultado incerto"
        scene = str(resolution.get("scene", "")).strip() or str(state.get("scene_title", "")).strip()
        return f"A consequência da rolagem se impõe em {scene}. O momento se resolve como {outcome}, e a cena muda de peso diante de você."
    return build_consistency_fallback(
        str(state.get("player_message", "")),
        state.get("recent_messages", []),
    )


def build_suggestion_fallback(state: dict, narration: str) -> list[str]:
    fallback_actions = state.get("fallback_actions", [])
    contextual = contextual_actions_from_narration(narration)
    actions = contextual or fallback_actions
    return sanitize_suggested_actions(actions, state.get("authoritative_state", {}), fallback_actions)
