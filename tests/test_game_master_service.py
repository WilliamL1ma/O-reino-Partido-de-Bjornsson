import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative import game_master_service as service


class GameMasterServiceTests(unittest.TestCase):
    def test_run_master_turn_uses_loot_shortcut_without_graph(self) -> None:
        character = SimpleNamespace(
            id=9,
            name="Rowan",
            story_scene="encounter_goblin",
            story_act=1,
        )

        with (
            patch.object(service, "build_scene_context", return_value={"title": "Emboscada", "lead": "O goblin caiu."}),
            patch.object(service, "get_story_flags", return_value={}),
            patch.object(service, "get_story_inventory", return_value=[]),
            patch.object(service, "get_context_hint", return_value={"kind": "post_encounter", "monster_name": "Goblin Cacador"}),
            patch.object(
                service,
                "get_recent_reward",
                return_value={
                    "monster_name": "Goblin Cacador",
                    "loot_names": ["Arco de Curto Alcance"],
                    "xp_gain": 30,
                    "gold_gain": 5,
                },
            ),
            patch.object(service, "build_default_actions_for_character", return_value=["Revistar o corpo", "Observar os arredores"]),
            patch.object(service, "store_suggested_actions") as store_actions,
            patch.object(service, "store_game_messages") as store_messages,
            patch.object(service, "invoke_and_finalize_master_graph", side_effect=AssertionError("graph should not run")),
        ):
            result = service.run_master_turn(character, "Vou revistar o corpo do goblin.")

        self.assertEqual(result["pending_event"], None)
        self.assertEqual(result["next_scene"], None)
        self.assertIn("confirma o saque real", result["gm_message"])
        self.assertEqual(result["suggested_actions"], ["Revistar o corpo", "Observar os arredores"])
        store_actions.assert_called_once()
        store_messages.assert_called_once()

    def test_build_current_moment_prefers_pending_event_truth(self) -> None:
        character = SimpleNamespace(id=3)
        scene = {"title": "Bosque", "lead": "A trilha se fecha."}

        with patch.object(
            service,
            "get_pending_event",
            return_value={"monster_name": "Lupus da Floresta Profunda", "stakes": "O lupus fecha o cerco."},
        ):
            current_moment = service.build_current_moment(character, scene, [])

        self.assertEqual(current_moment["title"], "Lupus da Floresta Profunda")
        self.assertEqual(current_moment["description"], "O lupus fecha o cerco.")

    def test_build_game_view_snapshot_assembles_runtime_view(self) -> None:
        character = SimpleNamespace(
            id=12,
            story_scene="encounter_goblin",
            story_act=1,
        )
        recent_messages = [SimpleNamespace(role="gm", content="O goblin rosna diante de voce.")]
        memory_summary = SimpleNamespace(summary_text="Resumo consolidado.")
        pending_event = {"type": "encounter", "monster_name": "Goblin Cacador"}

        with (
            patch.object(service, "ensure_story_initialized", return_value=character) as ensure_story,
            patch.object(service, "ensure_intro_message") as ensure_intro,
            patch.object(service, "build_scene_context", return_value={"title": "Emboscada", "lead": "O goblin rosna."}),
            patch.object(service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(service, "get_story_inventory", return_value=[{"name": "Adaga"}]),
            patch.object(service, "get_recent_game_messages", return_value=recent_messages),
            patch.object(service, "get_latest_memory_summary", return_value=memory_summary),
            patch.object(service, "get_pending_event", return_value=pending_event),
            patch.object(service, "build_current_moment", return_value={"title": "Emboscada", "description": "O goblin rosna."}),
            patch.object(service, "get_effective_suggested_actions", return_value=["Atacar", "Observar"]),
            patch.object(service, "get_recent_reward", return_value={"monster_name": "Goblin Cacador"}),
            patch.object(service, "get_encounter_transition", return_value={"monster": "goblin-cacador"}),
        ):
            snapshot = service.build_game_view_snapshot(character, groq_enabled=True)

        ensure_story.assert_called_once_with(character)
        ensure_intro.assert_called_once_with(character, groq_enabled=True)
        self.assertEqual(snapshot.scene["title"], "Emboscada")
        self.assertEqual(snapshot.pending_event, pending_event)
        self.assertEqual(snapshot.recent_messages, recent_messages)
        self.assertEqual(snapshot.memory_summary, memory_summary)
        self.assertEqual(snapshot.current_moment["title"], "Emboscada")
        self.assertEqual(snapshot.suggested_actions, ["Atacar", "Observar"])
        self.assertEqual(snapshot.recent_reward["monster_name"], "Goblin Cacador")
        self.assertEqual(snapshot.encounter["name"], "Goblin Cacador")

    def test_run_master_conversation_returns_clean_response_payload(self) -> None:
        character = SimpleNamespace(
            id=15,
            story_scene="chapter_entry",
            story_act=1,
        )
        updated_character = SimpleNamespace(
            id=15,
            story_scene="encounter_goblin",
            story_act=1,
        )
        summary = SimpleNamespace(summary_text="Resumo novo.")
        summarize_memory = Mock()

        with (
            patch.object(service, "ensure_story_initialized", return_value=character),
            patch.object(
                service,
                "run_master_turn",
                return_value={
                    "gm_message": "A neblina abre caminho.",
                    "pending_event": {"type": "skill_check"},
                    "next_scene": "encounter_goblin",
                    "suggested_actions": ["Avancar"],
                },
            ),
            patch.object(service, "get_latest_memory_summary", return_value=summary),
            patch.object(service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(service, "get_story_inventory", return_value=[]),
            patch.object(service, "build_scene_context", return_value={"title": "Emboscada", "lead": "A trilha fecha."}),
            patch.object(service, "get_recent_game_messages", return_value=[SimpleNamespace(role="gm", content="A neblina abre caminho.")]),
            patch.object(service, "build_current_moment", return_value={"title": "Emboscada", "description": "A trilha fecha."}),
            patch.object(service, "get_effective_suggested_actions", return_value=["Avancar", "Observar"]),
        ):
            snapshot = service.run_master_conversation(
                character,
                "Eu sigo em frente.",
                refresh_character=lambda _character_id: updated_character,
                summarize_memory=summarize_memory,
            )

        summarize_memory.assert_called_once_with(updated_character)
        self.assertEqual(
            snapshot.to_response(),
            {
                "ok": True,
                "player_message": "Eu sigo em frente.",
                "gm_message": "A neblina abre caminho.",
                "summary": "Resumo novo.",
                "pending_event": {"type": "skill_check"},
                "next_scene": "encounter_goblin",
                "current_moment": {"title": "Emboscada", "description": "A trilha fecha."},
                "suggested_actions": ["Avancar", "Observar"],
            },
        )

    def test_run_master_turn_persists_pending_roll_snapshot_when_graph_emits_event(self) -> None:
        character = SimpleNamespace(
            id=11,
            name="Rowan",
            story_scene="encounter_goblin",
            story_act=1,
        )
        graph_state = {
            "authoritative_state": {
                "scene_key": "encounter_goblin",
                "current_target": "Goblin Cacador",
                "interaction_mode": "combat",
                "interaction_type": "combat",
                "danger_level": "elevated",
                "recent_outcome": "ongoing",
                "allowed_action_kinds": ["combat", "defend", "escape", "observe"],
                "target_locked": True,
                "current_scene_state": {"scene_key": "encounter_goblin", "scene_phase": "combat"},
            }
        }
        emitted_event = {
            "type": "encounter",
            "attribute": "strength",
            "monster_name": "Goblin Cacador",
        }

        with (
            patch.object(service, "build_scene_context", return_value={"title": "Emboscada", "lead": "O goblin rosna."}),
            patch.object(service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(service, "get_story_inventory", return_value=[]),
            patch.object(service, "get_context_hint", return_value=None),
            patch.object(service, "get_recent_reward", return_value=None),
            patch.object(service, "get_recent_game_messages", return_value=[]),
            patch.object(service, "get_latest_memory_summary", return_value=None),
            patch.object(service, "build_master_graph_state", return_value=graph_state),
            patch.object(
                service,
                "invoke_and_finalize_master_graph",
                return_value=SimpleNamespace(
                    payload={
                        "narration": "O goblin salta das sombras.",
                        "event": emitted_event,
                        "next_scene": None,
                        "suggested_actions": ["Sacar a arma"],
                    }
                ),
            ),
            patch.object(service, "set_authority_snapshot") as set_snapshot,
            patch.object(service, "store_suggested_actions"),
            patch.object(service, "set_context_hint"),
            patch.object(service, "set_pending_event") as set_pending_event,
            patch.object(service, "store_game_messages"),
        ):
            result = service.run_master_turn(character, "Eu puxo a arma.")

        set_snapshot.assert_called_once()
        snapshot = set_snapshot.call_args.args[1]
        self.assertEqual(snapshot["interaction_mode"], "roll_pending")
        self.assertEqual(snapshot["danger_level"], "high")
        self.assertEqual(snapshot["mode_transition_signal"], "pending_roll")
        self.assertEqual(snapshot["pending_event_truth"]["monster_name"], "Goblin Cacador")
        self.assertEqual(snapshot["current_scene_state"]["scene_phase"], "roll_pending")
        set_pending_event.assert_called_once_with(11, emitted_event)
        self.assertEqual(result["pending_event"], emitted_event)


if __name__ == "__main__":
    unittest.main()
