import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import master_graph
from master_pipeline.contracts import MechanicsAgentResult
from master_pipeline.reviewers import ReviewResult


def _base_state() -> dict:
    return {
        "mode": "turn",
        "scene_title": "Bosque Fechado",
        "scene_lead": "A trilha aperta entre raizes antigas.",
        "current_scene": "chapter_entry",
        "allowed_next_scenes": ["act_two_crossroads", "encounter_goblin"],
        "available_monsters": ["goblin-cacador"],
        "lore_packet": {"chapter": "I"},
        "character_state": {"character_name": "Rowan"},
        "recent_messages": [],
        "player_message": "Eu observo a trilha.",
        "fallback_actions": [
            "Observar melhor o ambiente",
            "Avancar com cautela",
        ],
        "authoritative_state": {
            "interaction_mode": "exploration",
            "allowed_action_kinds": ["observe", "investigate", "move", "dialogue", "recover"],
            "current_target": "Goblin Cacador",
        },
    }


class MasterGraphFlowTests(unittest.TestCase):
    def test_mechanics_event_blocks_suggestion_generation(self) -> None:
        mechanics_event = {
            "type": "encounter",
            "attribute": "strength",
            "difficulty": 14,
            "monster_slug": "goblin-cacador",
            "monster_name": "Goblin Cacador",
        }
        bundle = SimpleNamespace(
            mechanics_agent=SimpleNamespace(
                detect_event=lambda _state: MechanicsAgentResult(
                    event=mechanics_event,
                    diagnostics=["mechanics:ok:event"],
                )
            ),
            narrative_agent=SimpleNamespace(
                generate=lambda _state, _event: ("O goblin salta das sombras.", None, None),
                revise=lambda *_args, **_kwargs: ("", None, None),
            ),
            suggestion_agent=SimpleNamespace(
                generate=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("suggestions should be blocked")),
                revise=lambda *_args, **_kwargs: [],
            ),
        )

        with (
            patch.object(master_graph, "_get_stage_bundle", return_value=bundle),
            patch.object(master_graph, "review_narration", return_value=ReviewResult(valid=True)),
        ):
            result = master_graph.invoke_master_graph(_base_state())

        self.assertEqual(result["result_event"], mechanics_event)
        self.assertEqual(result["result_suggested_actions"], [])
        self.assertIn("suggestions:blocked_pending_event", result["pipeline_diagnostics"])
        self.assertIn("suggestions_blocked", result["execution_trace"])
        self.assertNotIn("suggestions_generate", result["execution_trace"])

    def test_narrative_review_routes_through_single_revision_before_approval(self) -> None:
        bundle = SimpleNamespace(
            mechanics_agent=SimpleNamespace(
                detect_event=lambda _state: MechanicsAgentResult(event=None, diagnostics=["mechanics:ok:none"])
            ),
            narrative_agent=SimpleNamespace(
                generate=lambda _state, _event: ("Rascunho incoerente.", None, None),
                revise=lambda *_args, **_kwargs: ("A trilha revela marcas frescas no barro.", None, None),
            ),
            suggestion_agent=SimpleNamespace(
                generate=lambda *_args, **_kwargs: ["Examinar as marcas no barro"],
                revise=lambda *_args, **_kwargs: ["Examinar as marcas no barro"],
            ),
        )

        with (
            patch.object(master_graph, "_get_stage_bundle", return_value=bundle),
            patch.object(
                master_graph,
                "review_narration",
                side_effect=[
                    ReviewResult(valid=False, feedback="Corrija a continuidade."),
                    ReviewResult(valid=True),
                ],
            ),
            patch.object(
                master_graph,
                "review_suggestions",
                return_value=(["Examinar as marcas no barro"], ReviewResult(valid=True)),
            ),
        ):
            result = master_graph.invoke_master_graph(_base_state())

        self.assertEqual(result["result_narration"], "A trilha revela marcas frescas no barro.")
        self.assertIn("narrative_review:failed", result["pipeline_diagnostics"])
        self.assertIn("narrative:ok", result["pipeline_diagnostics"])
        self.assertIn("narrative_revise", result["execution_trace"])
        self.assertIn("suggestions_generate", result["execution_trace"])

    def test_suggestion_review_falls_back_after_failed_revision(self) -> None:
        state = _base_state()
        state["mode"] = "intro"
        bundle = SimpleNamespace(
            mechanics_agent=SimpleNamespace(
                detect_event=lambda _state: MechanicsAgentResult(event=None, diagnostics=["mechanics:skipped"])
            ),
            narrative_agent=SimpleNamespace(
                generate=lambda _state, _event: ("A praça desperta com passos indecisos.", None, None),
                revise=lambda *_args, **_kwargs: ("", None, None),
            ),
            suggestion_agent=SimpleNamespace(
                generate=lambda *_args, **_kwargs: ["Falar com alguem sem contexto"],
                revise=lambda *_args, **_kwargs: ["Repetir a sugestao generica"],
            ),
        )

        with (
            patch.object(master_graph, "_get_stage_bundle", return_value=bundle),
            patch.object(master_graph, "review_narration", return_value=ReviewResult(valid=True)),
            patch.object(
                master_graph,
                "review_suggestions",
                side_effect=[
                    (["Falar com alguem sem contexto"], ReviewResult(valid=False, feedback="Seja especifico.")),
                    (["Repetir a sugestao generica"], ReviewResult(valid=False, feedback="Ainda generico.")),
                ],
            ),
            patch.object(
                master_graph,
                "build_suggestion_fallback",
                return_value=["Observar quem cruza a praça", "Perguntar por rumores na entrada da cidade"],
            ),
        ):
            result = master_graph.invoke_master_graph(state)

        self.assertEqual(
            result["result_suggested_actions"],
            ["Observar quem cruza a praça", "Perguntar por rumores na entrada da cidade"],
        )
        self.assertIn("suggestion_review:failed", result["pipeline_diagnostics"])
        self.assertIn("suggestion_fallback", result["pipeline_diagnostics"])
        self.assertIn("fallbacks:only_suggestions", result["pipeline_diagnostics"])
        self.assertIn("suggestions_revise", result["execution_trace"])
        self.assertIn("suggestions_fallback", result["execution_trace"])

    def test_story_event_blocks_suggestions_and_preserves_event_payload(self) -> None:
        story_event = {
            "type": "forced_encounter",
            "scene": "encounter_goblin",
            "monster_slug": "goblin-cacador",
            "trigger_text": "Os galhos se partem com uma investida curta.",
        }
        bundle = SimpleNamespace(
            mechanics_agent=SimpleNamespace(
                detect_event=lambda _state: MechanicsAgentResult(event=None, diagnostics=["mechanics:ok:none"])
            ),
            narrative_agent=SimpleNamespace(
                generate=lambda _state, _event: ("Os galhos se abrem para uma investida repentina.", None, story_event),
                revise=lambda *_args, **_kwargs: ("", None, None),
            ),
            suggestion_agent=SimpleNamespace(
                generate=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("story_event should block suggestions")),
                revise=lambda *_args, **_kwargs: [],
            ),
        )

        with (
            patch.object(master_graph, "_get_stage_bundle", return_value=bundle),
            patch.object(master_graph, "review_narration", return_value=ReviewResult(valid=True)),
        ):
            result = master_graph.invoke_master_graph(_base_state())

        self.assertEqual(result["result_story_event"], story_event)
        self.assertEqual(result["result_suggested_actions"], [])
        self.assertIn("suggestions_blocked", result["execution_trace"])


if __name__ == "__main__":
    unittest.main()
