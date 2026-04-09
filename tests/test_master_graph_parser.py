import importlib.util
import sys
import types
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from master_graph_components import parser as parser_helpers
from master_graph_components import review as review_helpers


def _install_langchain_stubs() -> None:
    if "langchain_core.messages" not in sys.modules:
        langchain_core = types.ModuleType("langchain_core")
        messages = types.ModuleType("langchain_core.messages")

        class _Message:
            def __init__(self, content: str = "") -> None:
                self.content = content

        messages.AIMessage = _Message
        messages.HumanMessage = _Message
        messages.SystemMessage = _Message
        langchain_core.messages = messages

        sys.modules["langchain_core"] = langchain_core
        sys.modules["langchain_core.messages"] = messages

    if "langchain_groq" not in sys.modules:
        langchain_groq = types.ModuleType("langchain_groq")

        class ChatGroq:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def invoke(self, messages):
                return types.SimpleNamespace(content="")

        langchain_groq.ChatGroq = ChatGroq
        sys.modules["langchain_groq"] = langchain_groq

    if "langgraph.graph" not in sys.modules:
        langgraph = types.ModuleType("langgraph")
        graph = types.ModuleType("langgraph.graph")

        class _CompiledGraph:
            def invoke(self, state):
                return state

        class StateGraph:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def add_node(self, *_args, **_kwargs) -> None:
                pass

            def add_conditional_edges(self, *_args, **_kwargs) -> None:
                pass

            def add_edge(self, *_args, **_kwargs) -> None:
                pass

            def compile(self):
                return _CompiledGraph()

        graph.END = "END"
        graph.START = "START"
        graph.StateGraph = StateGraph
        langgraph.graph = graph

        sys.modules["langgraph"] = langgraph
        sys.modules["langgraph.graph"] = graph


def _load_master_graph_module():
    _install_langchain_stubs()
    module_path = Path(__file__).resolve().parents[1] / "backend" / "master_graph.py"
    spec = importlib.util.spec_from_file_location("test_master_graph_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class MasterGraphParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.master_graph = _load_master_graph_module()

    def test_extracts_actions_from_voce_pode_header(self) -> None:
        narration = (
            "Aqui você está, diante da fonte, com a escolha de beber água ou não. Você pode:\n\n"
            "* Beber água e tentar superar seu medo\n"
            "* Não beber água e continuar sua jornada sem ela\n"
            "* Voltar à clareira e procurar outra fonte de água\n"
            "* Fazer outra coisa"
        )

        cleaned_narration, actions = parser_helpers.extract_embedded_actions(narration)

        self.assertEqual(
            cleaned_narration,
            "Aqui você está, diante da fonte, com a escolha de beber água ou não.",
        )
        self.assertEqual(
            actions,
            [
                "Beber água e tentar superar seu medo",
                "Não beber água e continuar sua jornada sem ela",
                "Voltar à clareira e procurar outra fonte de água",
                "Fazer outra coisa",
            ],
        )

    def test_extracts_actions_from_aqui_estao_algumas_sugestoes_header(self) -> None:
        narration = (
            "Voce observa a clareira e percebe movimentos entre os animais.\n\n"
            "Aqui estão algumas sugestões de ações possíveis:\n\n"
            "* Continue a observar o animal grande e os menores\n"
            "* Tente se aproximar mais da clareira\n"
            "* Volte para a floresta para continuar explorando\n"
            "* Continue a monitorar a clareira de uma distancia segura"
        )

        cleaned_narration, actions = parser_helpers.extract_embedded_actions(narration)

        self.assertEqual(
            cleaned_narration,
            "Voce observa a clareira e percebe movimentos entre os animais.",
        )
        self.assertEqual(
            actions,
            [
                "Continue a observar o animal grande e os menores",
                "Tente se aproximar mais da clareira",
                "Volte para a floresta para continuar explorando",
                "Continue a monitorar a clareira de uma distancia segura",
            ],
        )

    def test_extracts_actions_from_suggested_actions_header(self) -> None:
        narration = (
            "O gato volta a cheirar sua mao, ainda cauteloso.\n\n"
            "Suggested_actions:\n"
            "- Continue a interagir com o gato\n"
            "- Retire-se e deixe o gato em paz\n"
            "- Tente tocar o gato\n"
            "- Continue a observar o gato"
        )

        cleaned_narration, actions = parser_helpers.extract_embedded_actions(narration)

        self.assertEqual(
            cleaned_narration,
            "O gato volta a cheirar sua mao, ainda cauteloso.",
        )
        self.assertEqual(
            actions,
            [
                "Continue a interagir com o gato",
                "Retire-se e deixe o gato em paz",
                "Tente tocar o gato",
                "Continue a observar o gato",
            ],
        )

    def test_soften_player_intent_preserves_attack_but_reduces_gore(self) -> None:
        softened = review_helpers.soften_player_intent("eu pego minha adaga e enfio no coração dele")
        self.assertNotIn("enfio", softened.lower())
        self.assertNotIn("coração", softened.lower())
        self.assertIn("adaga", softened.lower())

    def test_sanitize_actions_extracts_text_from_dict_items(self) -> None:
        actions = parser_helpers.sanitize_actions(
            [{"ação": "revistar o corpo do gato"}, {"action": "observar o entorno"}],
            ["fallback"],
        )
        self.assertEqual(actions, ["revistar o corpo do gato", "observar o entorno"])


    def test_parse_json_prefers_embedded_dynamic_actions_over_fallback(self) -> None:
        raw_text = json_text = (
            '{"narration": "Aqui você está, diante da fonte, com a escolha de beber água ou não. '
            'Você pode:\\n\\n* Beber água e tentar superar seu medo\\n* Não beber água e continuar '
            'sua jornada sem ela\\n* Voltar à clareira e procurar outra fonte de água\\n* Fazer '
            'outra coisa", "suggested_actions": [], "event": null, "next_scene": null}'
        )

        narration, event, next_scene, actions = parser_helpers.parse_json_payload(
            raw_text,
            [],
            ["goblin"],
            [
                "Buscar cobertura antes do disparo",
                "Tentar perceber de onde veio a emboscada",
                "Avancar com agressividade contra o atirador",
                "Gritar para intimidar o inimigo",
            ],
            review_helpers.contextual_actions_from_narration,
        )

        self.assertEqual(
            narration,
            "Aqui você está, diante da fonte, com a escolha de beber água ou não.",
        )
        self.assertIsNone(event)
        self.assertIsNone(next_scene)
        self.assertEqual(
            actions,
            [
                "Beber água e tentar superar seu medo",
                "Não beber água e continuar sua jornada sem ela",
                "Voltar à clareira e procurar outra fonte de água",
                "Fazer outra coisa",
            ],
        )

    def test_parse_json_builds_contextual_actions_for_post_combat_scene(self) -> None:
        raw_text = (
            '{"narration": "Você lança o feitiço de fogo diretamente no goblin. '
            'Com o goblin derrotado, você agora está sozinho na trilha, com o corpo dele '
            'queimando ao seu lado. Você pode ouvir sons de animais selvagens se aproximando.", '
            '"suggested_actions": [], "event": null, "next_scene": null}'
        )

        narration, event, next_scene, actions = parser_helpers.parse_json_payload(
            raw_text,
            [],
            ["goblin"],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
                "Buscar uma saida segura caso a tensao aumente",
                "Ler melhor o terreno e os sinais ao redor",
                "Agir com cautela e responder ao que acontecer agora",
            ],
            review_helpers.contextual_actions_from_narration,
        )

        self.assertIn("goblin derrotado", narration)
        self.assertIsNone(event)
        self.assertIsNone(next_scene)
        self.assertEqual(
            actions,
            [
                "Revistar o corpo e confirmar o que ainda pode ser aproveitado",
                "Se afastar do fogo e sair da area antes que algo seja atraido",
                "Preparar uma retirada curta antes que os animais se aproximem demais",
                "Recolher o que for util e seguir com cautela pela trilha",
                "Examinar o terreno para ver se o goblin guardava algo importante",
            ],
        )

    def test_guardrails_strip_json_and_replace_recent_reward_block(self) -> None:
        narration, actions = review_helpers.enforce_guardrails(
            (
                "Voce pega todos os itens encontrados no corpo.\n\n"
                "**Recent Reward:**\n"
                "- Uma faca pequena de madeira\n"
                "- Uma pedra de fogo\n"
                "- Uma pequena quantidade de comida seca\n\n"
                "```json\n"
                '{"narration":"x","suggested_actions":["y"]}\n'
                "```"
            ),
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            {
                "monster_name": "Goblin Cacador",
                "xp_gain": 30,
                "gold_gain": 5,
                "loot_names": ["Arco curto", "Flecha de madeira"],
            },
        )

        self.assertNotIn("```json", narration)
        self.assertNotIn("Uma faca pequena de madeira", narration)
        self.assertIn("Arco curto, Flecha de madeira", narration)
        self.assertEqual(
            actions,
            [
                "Revistar o corpo e confirmar o que ainda pode ser aproveitado",
                "Se afastar do fogo e sair da area antes que algo seja atraido",
                "Observar de onde os sons ou movimentos ao redor estao vindo",
                "Recolher o que for util e seguir com cautela pela trilha",
                "Examinar o terreno para ver se o goblin guardava algo importante",
            ],
        )

    def test_review_feedback_marks_invalid_draft_with_json_and_fake_loot(self) -> None:
        valid, feedback = review_helpers.build_review_feedback(
            (
                '```json\n{"narration":"x"}\n```\n'
                "**Recent Reward:**\n- Uma faca pequena de madeira\n"
                "Com o goblin derrotado, o corpo ainda queima ao seu lado."
            ),
            [
                "Tentar falar ou demonstrar intencoes sem atacar",
                "Observar a reacao imediata da criatura antes de agir",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            {
                "loot_names": ["Arco curto", "Flecha de madeira"],
            },
        )

        self.assertFalse(valid)
        self.assertIn("JSON", feedback)
        self.assertIn("Recent Reward", feedback)
        self.assertIn("suggested_actions", feedback)
        self.assertIn("loot inventado", feedback)

    def test_review_feedback_flags_embedded_suggestions_not_extracted(self) -> None:
        valid, feedback = review_helpers.build_review_feedback(
            (
                "Voce observa a clareira.\n\n"
                "Aqui estão algumas sugestões de ações possíveis:\n\n"
                "* Continue a observar\n"
                "* Tente se aproximar mais"
            ),
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            None,
        )

        self.assertFalse(valid)
        self.assertIn("lista de sugestoes embutida", feedback)

    def test_review_feedback_flags_model_refusal(self) -> None:
        valid, feedback = review_helpers.build_review_feedback(
            "Não posso prosseguir com essa sequência. Posso ajudar com outra ação?",
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            None,
        )

        self.assertFalse(valid)
        self.assertIn("recusa do modelo", feedback)

    def test_review_feedback_flags_entity_swap_from_cat_to_goblin(self) -> None:
        valid, feedback = review_helpers.build_review_feedback(
            "O goblin esta morto, mas pode haver mais perigos por ai.",
            [
                "Examinar o corpo do goblin",
                "Olhar ao redor para ver se ha mais goblins",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            None,
            "como ele se afasta se ele foi atacado com a adaga e ela esta cravada no peito dele?",
            [
                {"role": "gm", "content": "Voce se aproxima do gato e ele volta a cheirar sua mao."},
                {"role": "player", "content": "eu pego minha adaga e enfio no coração dele"},
            ],
        )

        self.assertFalse(valid)
        self.assertIn("trocou a entidade", feedback)

    def test_entity_continuity_ignores_negated_player_entity(self) -> None:
        broken = review_helpers.entity_continuity_broken(
            "O goblin esta morto.",
            "não estamos falando de goblin",
            [{"role": "gm", "content": "O gato ainda observa sua mao com cautela."}],
        )
        self.assertTrue(broken)

    def test_review_feedback_flags_physical_causality_break(self) -> None:
        valid, feedback = review_helpers.build_review_feedback(
            "Voce pega sua adaga e a crava no peito do gato, mas ele comeca a se afastar e volta a cheirar sua mao.",
            [
                "Tentar acalmar o gato",
                "Preparar-se para uma possível defesa do gato",
            ],
            [
                "Observar a reacao imediata da criatura antes de agir",
                "Tentar falar ou demonstrar intencoes sem atacar",
            ],
            None,
            "eu pego minha adaga e enfio no coração dele",
            [{"role": "gm", "content": "O gato estava perto e atento a sua presenca."}],
        )

        self.assertFalse(valid)
        self.assertIn("causalidade fisica", feedback)

    def test_finalize_node_uses_consistency_fallback_when_review_stays_invalid(self) -> None:
        result = self.master_graph._finalize_node(
            {
                "approved_narration": "",
                "approved_suggested_actions": [],
                "fallback_actions": ["fallback"],
                "character_state": {"recent_reward": "nenhum"},
                "narrative_review_valid": False,
                "suggestion_review_valid": False,
                "player_message": "eu pego minha adaga e enfio no coração dele",
                "recent_messages": [{"role": "gm", "content": "O gato ainda está diante de você."}],
                "narrative_force_fallback": False,
                "suggestion_force_fallback": False,
            }
        )
        self.assertIn("gato", result["result_narration"])
        self.assertNotIn("goblin", result["result_narration"])
        self.assertEqual(result["result_suggested_actions"], ["fallback"])

    def test_route_review_allows_second_revision_before_finalize(self) -> None:
        self.assertEqual(self.master_graph._route_review({"review_valid": False, "revise_attempt": 0}), "revise")
        self.assertEqual(self.master_graph._route_review({"review_valid": False, "revise_attempt": 1}), "revise")
        self.assertEqual(self.master_graph._route_review({"review_valid": False, "revise_attempt": 2}), "finalize")
        self.assertEqual(self.master_graph._route_review({"review_valid": True, "revise_attempt": 0}), "finalize")


if __name__ == "__main__":
    unittest.main()
