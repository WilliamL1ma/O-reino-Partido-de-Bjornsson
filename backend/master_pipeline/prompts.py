from __future__ import annotations

import json


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def build_mechanics_messages(state: dict) -> list[object]:
    payload = {
        "player_message": state.get("player_message", ""),
        "character_state": state.get("character_state", {}),
        "authoritative_state": state.get("authoritative_state", {}),
        "recent_messages": state.get("recent_messages", []),
        "available_monsters": state.get("available_monsters", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "Voce e um especialista mecanico de um RPG textual. "
                "Sua unica funcao e decidir se a intencao do jogador exige um evento mecanico imediato. "
                "Nao narre a cena. Nao escreva sugestoes. Nao altere lore. "
                "Responda apenas em JSON com a chave event. "
                "event pode ser null ou um objeto com type, attribute, difficulty, roll_type, stakes e monster_slug quando houver encounter. "
                "Use encounter apenas se existir um alvo hostil concreto e conhecido. "
                "Se a acao puder ser resolvida sem rolagem, retorne {\"event\": null}."
            ),
        },
        {"role": "user", "content": _compact_json(payload)},
    ]


def build_narrative_messages(state: dict, mechanics_event: dict | None) -> list[object]:
    payload = {
        "mode": state.get("mode"),
        "scene_title": state.get("scene_title"),
        "scene_lead": state.get("scene_lead"),
        "current_scene": state.get("current_scene"),
        "character_state": state.get("character_state", {}),
        "authoritative_state": state.get("authoritative_state", {}),
        "allowed_next_scenes": state.get("allowed_next_scenes", []),
        "available_monsters": state.get("available_monsters", []),
        "mechanics_event": mechanics_event,
        "player_message": state.get("player_message", ""),
        "roll_resolution": state.get("roll_resolution", {}),
    }
    messages: list[object] = [
        {
            "role": "system",
            "content": (
                "Voce e o especialista em narrativa do mestre de um RPG textual em Elandoria. "
                "Sua unica funcao e entregar a narracao principal do mestre, mantendo tom, continuidade, atmosfera, causalidade e lore. "
                "Voce pode refletir um event mecanico ja decidido, mas nao cria sugestoes de acoes. "
                "Nao controle XP, ouro, dano, inventario ou recompensas. "
                "Nao exponha termos internos, JSON ou nomes tecnicos ao jogador. "
                "A narracao do mestre nao pode vir inteira entre aspas. Apenas falas de personagens ou NPCs devem aparecer entre aspas. "
                "Mantenha a linguagem compativel com fantasia medieval. Evite objetos e referencias modernas como garrafa plastica, telefone, carro, motor, gasolina, elevador ou arma de fogo moderna, salvo se o lore disser explicitamente o contrario. "
                "Se mechanics_event existir, interrompa a cena no ponto em que a rolagem precisa acontecer e nao narre o desfecho como fato consumado. "
                "Se um encontro surpresa ou combate forcado surgir do mundo, use story_event com type='forced_encounter', scene e monster_slug. "
                "Nao use next_scene sozinho para iniciar combate surpresa. "
                "Use next_scene apenas quando houver uma transicao narrativa real. "
                "Responda apenas em JSON com narration, next_scene e story_event."
            ),
        },
        {"role": "system", "content": "Lore oficial relevante: " + _compact_json(state.get("lore_packet", {}))},
        {"role": "system", "content": "Contexto autoritativo: " + _compact_json(payload)},
    ]
    for message in state.get("recent_messages", []):
        if message.get("role") == "gm":
            messages.append({"role": "assistant", "content": message.get("content", "")})
        else:
            messages.append({"role": "user", "content": message.get("content", "")})
    if state.get("player_message"):
        messages.append({"role": "user", "content": state["player_message"]})
    return messages


def build_narrative_revision_messages(
    state: dict,
    draft_narration: str,
    draft_next_scene: str | None,
    draft_story_event: dict | None,
    mechanics_event: dict | None,
    feedback: str,
) -> list[object]:
    payload = {
        "mode": state.get("mode"),
        "current_scene": state.get("current_scene"),
        "character_state": state.get("character_state", {}),
        "authoritative_state": state.get("authoritative_state", {}),
        "allowed_next_scenes": state.get("allowed_next_scenes", []),
        "available_monsters": state.get("available_monsters", []),
        "player_message": state.get("player_message", ""),
        "mechanics_event": mechanics_event,
        "draft": {"narration": draft_narration, "next_scene": draft_next_scene, "story_event": draft_story_event},
        "feedback": feedback,
    }
    return [
        {
            "role": "system",
            "content": (
                "Voce e o especialista em revisao narrativa. "
                "Corrija apenas a narracao do mestre. "
                "Nao escreva sugestoes. Nao mude mecanicas. Nao adicione dados tecnicos. "
                "A narracao do mestre nao pode ficar inteira entre aspas. So falas de personagens ficam entre aspas. "
                "Remova anacronismos e troque objetos modernos por equivalentes coerentes com fantasia medieval. "
                "Se houver combate surpresa, use story_event em vez de next_scene tecnico para disparar o encontro. "
                "Entregue apenas JSON com narration, next_scene e story_event."
            ),
        },
        {"role": "user", "content": _compact_json(payload)},
    ]


def build_suggestion_messages(state: dict, approved_narration: str) -> list[object]:
    payload = {
        "narration": approved_narration,
        "authoritative_state": state.get("authoritative_state", {}),
        "current_scene": state.get("current_scene"),
        "scene_title": state.get("scene_title"),
        "player_message": state.get("player_message", ""),
        "recent_messages": state.get("recent_messages", []),
        "fallback_actions": state.get("fallback_actions", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "Voce e o especialista em sugestoes do mestre de um RPG textual. "
                "Sua unica funcao e propor proximas acoes que o jogador realmente pode executar agora. "
                "Leia a narracao final como verdade do momento. "
                "Respeite authoritative_state.allowed_action_kinds. "
                "Escreva sempre em portugues do Brasil. "
                "Nao responda em ingles nem misture idiomas nas acoes. "
                "Nao mude lore, nao narre a cena, nao invente recompensas, nao escreva explicacoes tecnicas. "
                "Responda apenas em JSON com suggested_actions contendo de 2 a 5 opcoes concretas, contextuais e nao genericas."
            ),
        },
        {"role": "user", "content": _compact_json(payload)},
    ]


def build_suggestion_revision_messages(
    state: dict,
    approved_narration: str,
    draft_actions: list[str],
    feedback: str,
) -> list[object]:
    payload = {
        "narration": approved_narration,
        "authoritative_state": state.get("authoritative_state", {}),
        "draft_actions": draft_actions,
        "feedback": feedback,
        "fallback_actions": state.get("fallback_actions", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "Voce e o especialista em revisao de sugestoes. "
                "Corrija apenas suggested_actions. "
                "Todas as acoes devem ficar em portugues do Brasil. "
                "Nao altere a narracao. Nao explique nada. "
                "Responda apenas em JSON com suggested_actions contendo de 2 a 5 acoes coerentes com a narracao final."
            ),
        },
        {"role": "user", "content": _compact_json(payload)},
    ]
