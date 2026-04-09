from __future__ import annotations

import re
import unicodedata

from .parser import extract_embedded_actions, sanitize_actions, strip_json_artifacts


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.lower().strip()


def soften_player_intent(player_message: str) -> str:
    softened = player_message.strip()
    replacements = [
        (r"\benfio\b", "tento cravar"),
        (r"\benfiar\b", "cravar"),
        (r"\bcoracao\b", "peito"),
        (r"\bcora[cç][aã]o\b", "peito"),
        (r"\bmatar\b", "derrubar"),
        (r"\bdegolar\b", "neutralizar com um golpe"),
        (r"\besquartejar\b", "atacar com violencia"),
    ]
    for pattern, replacement in replacements:
        softened = re.sub(pattern, replacement, softened, flags=re.IGNORECASE)
    return softened


def looks_like_model_refusal(narration: str) -> bool:
    folded = fold_text(narration)
    refusal_signals = [
        "nao posso prosseguir com essa sequencia",
        "nao posso ajudar com isso",
        "nao posso continuar com isso",
        "posso ajudar com outra acao",
        "posso ajudar com outra ação",
        "nao posso prosseguir",
    ]
    return any(signal in folded for signal in refusal_signals)


def extract_known_entities(text: str) -> list[str]:
    folded = fold_text(text)
    known_entities = [
        "gato",
        "goblin",
        "lobo",
        "raposa",
        "aranha",
        "duende",
        "cobra",
        "passaro",
        "lobisomem",
        "lupus",
        "animal",
        "criatura",
    ]
    return [entity for entity in known_entities if entity in folded]


def extract_affirmed_entities(text: str) -> set[str]:
    folded = fold_text(text)
    entities = set(extract_known_entities(text))
    negation_patterns = [
        r"nao estamos falando de ([a-z]+)",
        r"nao estamos faladno de ([a-z]+)",
        r"nao e ([a-z]+)",
        r"nao eh ([a-z]+)",
        r"nao e o ([a-z]+)",
        r"nao eh o ([a-z]+)",
        r"nao e um ([a-z]+)",
        r"nao eh um ([a-z]+)",
    ]

    for pattern in negation_patterns:
        for match in re.findall(pattern, folded):
            entities.discard(match.strip())

    return entities


def entity_continuity_broken(narration: str, player_message: str, recent_messages: list[dict] | list[object]) -> bool:
    narration_entities = extract_affirmed_entities(narration)
    player_entities = extract_affirmed_entities(player_message)
    gm_context_entities: set[str] = set()
    player_context_entities: set[str] = set()

    for message in recent_messages[-4:]:
        if isinstance(message, dict):
            content = str(message.get("content", ""))
            role = str(message.get("role", ""))
        else:
            content = str(getattr(message, "content", ""))
            role = str(getattr(message, "role", ""))
        if role == "gm":
            gm_context_entities.update(extract_affirmed_entities(content))
        else:
            player_context_entities.update(extract_affirmed_entities(content))

    expected_entities = gm_context_entities or player_context_entities or player_entities
    if not expected_entities or not narration_entities:
        return False
    return not bool(narration_entities.intersection(expected_entities))


def physical_causality_broken(player_message: str, narration: str) -> bool:
    folded_player = fold_text(player_message)
    folded_narration = fold_text(narration)

    close_range_attack = any(
        keyword in folded_player
        for keyword in ["adaga", "faca", "apunhal", "cravar", "golpe curto", "esfaque"]
    )
    severe_hit = any(
        keyword in folded_narration
        for keyword in ["crava no peito", "cravar no peito", "atinge em cheio", "golpe profundo", "perfura o peito"]
    )
    implausible_recovery = any(
        keyword in folded_narration
        for keyword in ["comeca a se afastar", "afasta um pouco", "volta a se aproximar", "continua calmo", "volta a cheirar"]
    )

    return close_range_attack and severe_hit and implausible_recovery


def latest_context_entity(recent_messages: list[dict] | list[object]) -> str | None:
    for message in reversed(recent_messages):
        if isinstance(message, dict):
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
        else:
            role = str(getattr(message, "role", ""))
            content = str(getattr(message, "content", ""))
        if role != "gm":
            continue
        entities = list(extract_affirmed_entities(content))
        if entities:
            return entities[0]
    return None


def build_consistency_fallback(player_message: str, recent_messages: list[dict] | list[object]) -> str:
    target = latest_context_entity(recent_messages) or "alvo a sua frente"
    softened_intent = soften_player_intent(player_message)
    if any(keyword in fold_text(softened_intent) for keyword in ["adaga", "faca", "cravar", "golpe", "atacar"]):
        return (
            f"Voce transforma a aproximacao em um ataque direto contra {target}. "
            f"O instante quebra qualquer hesitacao anterior e obriga {target} a reagir imediatamente ao confronto."
        )
    return (
        f"A tensao com {target} muda de tom de forma brusca. "
        f"O proximo instante exige uma resposta imediata ao risco diante de voce."
    )


def contextual_actions_from_narration(narration: str) -> list[str]:
    folded = fold_text(narration)

    if any(keyword in folded for keyword in ["derrotad", "abatid", "corpo", "queimando ao seu lado", "recent reward", "obteve"]):
        actions = [
            "Revistar o corpo e confirmar o que ainda pode ser aproveitado",
            "Se afastar do fogo e sair da area antes que algo seja atraido",
            "Observar de onde os sons ou movimentos ao redor estao vindo",
            "Recolher o que for util e seguir com cautela pela trilha",
            "Examinar o terreno para ver se o goblin guardava algo importante",
        ]
        if any(keyword in folded for keyword in ["animais selvagens", "se aproximando", "cheiro de sangue", "barulho vindo", "sons de animais"]):
            actions[2] = "Preparar uma retirada curta antes que os animais se aproximem demais"
        return actions

    if any(keyword in folded for keyword in ["quem voce e", "quem e voce", "tentar conversar", "fala em", "dialeto", "dialogo", "conversa", "negoci"]):
        return [
            "Responder com calma e manter a conversa no mesmo tom",
            "Tentar entender melhor o que a criatura quer ou procura",
            "Fazer uma pergunta simples para evitar novo mal-entendido",
            "Observar a linguagem corporal antes de se aproximar mais",
            "Propor distancia segura enquanto a conversa continua",
        ]

    if any(keyword in folded for keyword in ["mal-estar", "tonto", "enjo", "recuperar", "respirar", "se acalmar"]):
        return [
            "Parar por um instante e recuperar o folego antes de agir",
            "Se afastar da fonte e observar se o mal-estar piora",
            "Procurar um lugar seguro para se sentar e se recompor",
            "Examinar se houve veneno, magia ou algum sinal estranho na agua",
            "Decidir se vale continuar agora ou recuar por um momento",
        ]

    if any(keyword in folded for keyword in ["emboscad", "disparo", "flecha", "ataque vindo", "hostil", "pronto para atacar"]):
        return [
            "Buscar cobertura antes de se expor novamente",
            "Tentar localizar a origem exata da ameaca",
            "Ganhar tempo e medir a proxima acao do inimigo",
            "Mudar de posicao usando o terreno a seu favor",
            "Decidir entre responder ao ataque ou recuar com cautela",
        ]

    return []


def actions_contradict_narration(actions: list[str], narration: str) -> bool:
    folded_narration = fold_text(narration)
    folded_actions = [fold_text(action) for action in actions]

    if any(keyword in folded_narration for keyword in ["derrotad", "abatid", "morreu", "corpo", "queimando ao seu lado"]):
        return any(
            any(term in action for term in ["falar", "demonstrar intencoes", "reacao imediata da criatura", "conversa"])
            for action in folded_actions
        )

    if any(keyword in folded_narration for keyword in ["conversa", "dialeto", "negoci", "quem voce e", "fala em"]):
        return any(
            any(term in action for term in ["cobertura", "atacar", "investida", "avancar", "intimid"])
            for action in folded_actions
        )

    return False


def actions_are_too_generic(actions: list[str], fallback_actions: list[str]) -> bool:
    if len(actions) < 2 or len(actions) > 5:
        return True

    if actions == fallback_actions[:5]:
        return True

    folded_actions = [fold_text(action) for action in actions]
    generic_signals = [
        "observar melhor o ambiente",
        "avancar com cautela",
        "parar um instante para reavaliar o caminho",
        "falar com a pessoa mais proxima",
        "investigar sinais, rastros ou marcas",
    ]
    generic_hits = sum(1 for action in folded_actions if action in generic_signals)
    return generic_hits >= 3


def replace_reward_block_with_truth(narration: str, recent_reward: object) -> str:
    if "recent reward" not in fold_text(narration):
        return narration

    cleaned = re.sub(
        r"\*\*Recent Reward:\*\*[\s\S]*?(?=(?:\n{2,}|$))",
        "",
        narration,
        flags=re.IGNORECASE,
    ).strip()

    if not isinstance(recent_reward, dict):
        return cleaned

    loot_names = recent_reward.get("loot_names", [])
    if not isinstance(loot_names, list) or not loot_names:
        return cleaned

    loot_text = ", ".join(str(item).strip() for item in loot_names if str(item).strip())
    if not loot_text:
        return cleaned

    truth = f"Voce confirma o saque real deixado pela criatura: {loot_text}."
    return f"{cleaned}\n\n{truth}".strip()


def enforce_guardrails(
    narration: str,
    suggested_actions: list[str],
    fallback_actions: list[str],
    recent_reward: object,
) -> tuple[str, list[str]]:
    cleaned_narration = strip_json_artifacts(narration)
    cleaned_narration = replace_reward_block_with_truth(cleaned_narration, recent_reward)

    contextual_actions = contextual_actions_from_narration(cleaned_narration)
    final_actions = sanitize_actions(suggested_actions, fallback_actions)
    if contextual_actions and (
        final_actions == fallback_actions[:5] or actions_contradict_narration(final_actions, cleaned_narration)
    ):
        final_actions = contextual_actions

    return cleaned_narration or narration.strip(), final_actions


def build_review_feedback(
    narration: str,
    actions: list[str],
    fallback_actions: list[str],
    recent_reward: object,
    player_message: str = "",
    recent_messages: list[dict] | list[object] | None = None,
) -> tuple[bool, str]:
    feedback: list[str] = []
    folded_narration = fold_text(narration)
    recent_messages = recent_messages or []

    if narration != strip_json_artifacts(narration):
        feedback.append("Remova qualquer bloco JSON, markdown tecnico ou estrutura interna vazada ao jogador.")

    if looks_like_model_refusal(narration):
        feedback.append("A resposta virou uma recusa do modelo. Reescreva a intencao do jogador em linguagem menos grafica, mas preserve a acao de atacar o alvo e continue a cena normalmente.")

    if entity_continuity_broken(narration, player_message, recent_messages):
        feedback.append("A narracao trocou a entidade ou criatura em foco sem base no contexto recente. Mantenha o mesmo alvo em continuidade com a cena.")

    if physical_causality_broken(player_message, narration):
        feedback.append("A narracao quebrou a causalidade fisica do ataque. Se houve golpe corpo a corpo grave, a reacao imediata do alvo deve ser coerente com esse impacto.")

    if "recent reward" in folded_narration:
        feedback.append("Nao exponha 'Recent Reward'. Integre apenas o saque real na narracao, sem bloco tecnico.")

    if actions_contradict_narration(actions, narration):
        feedback.append("As suggested_actions contradizem a narracao final. Reescreva-as para seguir exatamente o ultimo estado narrado.")

    if len(actions) < 2 or len(actions) > 5:
        feedback.append("As suggested_actions devem trazer de 2 a 5 opcoes.")

    embedded_narration, embedded_actions = extract_embedded_actions(narration)
    if embedded_actions and actions != embedded_actions[:5]:
        feedback.append("Existe uma lista de sugestoes embutida na narracao. Extraia essa lista para suggested_actions e remova-a do texto final.")

    contextual_actions = contextual_actions_from_narration(narration)
    if contextual_actions and actions == fallback_actions[:5]:
        feedback.append("As suggested_actions ficaram genericas ou herdadas do fallback. Gere acoes especificas para este momento narrativo.")

    if actions_are_too_generic(actions, fallback_actions):
        feedback.append("As suggested_actions estao genericas, incompletas ou herdadas do fallback. Reescreva 5 opcoes concretas que nascam diretamente da narracao entregue ao jogador.")

    if isinstance(recent_reward, dict):
        loot_names = recent_reward.get("loot_names", [])
        if isinstance(loot_names, list) and loot_names:
            for item in re.findall(r"^\s*-\s+(.+)$", narration, flags=re.MULTILINE):
                if item.strip() not in loot_names:
                    feedback.append("Ha loot inventado na narracao. Cite apenas os itens reais presentes em recent_reward.loot_names.")
                    break

    return (len(feedback) == 0, " ".join(feedback).strip())

