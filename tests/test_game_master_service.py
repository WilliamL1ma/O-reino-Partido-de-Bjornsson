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
    def test_get_effective_suggested_actions_returns_empty_when_roll_is_pending(self) -> None:
        character = SimpleNamespace(id=31)

        with (
            patch.object(service, "get_pending_event", return_value={"type": "encounter", "monster_name": "Goblin Cacador"}),
            patch.object(service, "get_suggested_actions", return_value=["Atacar", "Observar"]),
            patch.object(
                service,
                "build_default_actions_for_character",
                side_effect=AssertionError("default suggestions should stay blocked during a pending roll"),
            ),
        ):
            actions = service.get_effective_suggested_actions(character, "encounter_goblin")

        self.assertEqual(actions, [])

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
        recent_messages = [SimpleNamespace(role="gm", content="O goblin rosna diante de você.")]
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
        self.assertEqual(snapshot.encounter["name"], "Goblin Caçador")

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
            patch.object(
                service,
                "build_live_view_state",
                return_value={
                    "scene": {"key": "encounter_goblin", "title": "Emboscada"},
                    "current_moment": {"title": "Emboscada", "description": "A trilha fecha."},
                    "pending_event": {"type": "skill_check"},
                    "suggested_actions": ["Avancar", "Observar"],
                    "recent_reward": None,
                    "inventory_preview": [],
                    "progress": {"act": 1, "experience": 0, "gold": 0},
                },
            ),
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
                "view_state": {
                    "scene": {"key": "encounter_goblin", "title": "Emboscada"},
                    "current_moment": {"title": "Emboscada", "description": "A trilha fecha."},
                    "pending_event": {"type": "skill_check"},
                    "suggested_actions": ["Avancar", "Observar"],
                    "recent_reward": None,
                    "inventory_preview": [],
                    "progress": {"act": 1, "experience": 0, "gold": 0},
                },
            },
        )

    def test_run_master_turn_returns_narration_and_suggestions_when_no_roll_is_needed(self) -> None:
        character = SimpleNamespace(
            id=18,
            name="Rowan",
            class_name="fighter",
            story_scene="chapter_entry",
            story_act=1,
        )

        with (
            patch.object(service, "build_scene_context", return_value={"title": "Trilha", "lead": "A estrada segue aberta."}),
            patch.object(service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(service, "get_story_inventory", return_value=[]),
            patch.object(service, "get_context_hint", return_value=None),
            patch.object(service, "get_recent_reward", return_value=None),
            patch.object(service, "get_recent_game_messages", return_value=[]),
            patch.object(service, "get_latest_memory_summary", return_value=None),
            patch.object(service, "build_master_graph_state", return_value={"authoritative_state": {}}),
            patch.object(
                service,
                "invoke_and_finalize_master_graph",
                return_value=SimpleNamespace(
                    payload={
                        "narration": "A trilha responde ao seu passo, e o caminho permanece livre.",
                        "event": None,
                        "story_event": None,
                        "next_scene": None,
                        "suggested_actions": ["Observar as árvores", "Seguir pela estrada"],
                    }
                ),
            ),
            patch.object(service, "set_authority_snapshot") as set_snapshot,
            patch.object(service, "store_suggested_actions") as store_suggested_actions,
            patch.object(service, "store_game_messages") as store_game_messages,
            patch.object(service, "store_player_message") as store_player_message,
        ):
            result = service.run_master_turn(character, "Eu sigo pela estrada.")

        self.assertEqual(
            result,
            {
                "gm_message": "A trilha responde ao seu passo, e o caminho permanece livre.",
                "pending_event": None,
                "next_scene": None,
                "suggested_actions": ["Observar as árvores", "Seguir pela estrada"],
            },
        )
        set_snapshot.assert_called_once()
        store_suggested_actions.assert_called_once_with(character.id, ["Observar as árvores", "Seguir pela estrada"])
        store_game_messages.assert_called_once_with(
            character.id,
            "chapter_entry",
            "Eu sigo pela estrada.",
            "A trilha responde ao seu passo, e o caminho permanece livre.",
        )
        store_player_message.assert_not_called()

    def test_run_master_turn_persists_pending_roll_snapshot_without_gm_message_before_roll(self) -> None:
        character = SimpleNamespace(
            id=11,
            name="Rowan",
            class_name="fighter",
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
                        "suggested_actions": [],
                    }
                ),
            ),
            patch.object(service, "set_authority_snapshot") as set_snapshot,
            patch.object(service, "store_suggested_actions") as store_suggested_actions,
            patch.object(service, "set_context_hint"),
            patch.object(service, "set_pending_event") as set_pending_event,
            patch.object(service, "store_game_messages") as store_game_messages,
            patch.object(service, "store_player_message") as store_player_message,
        ):
            result = service.run_master_turn(character, "Eu puxo a arma.")

        set_snapshot.assert_called_once()
        snapshot = set_snapshot.call_args.args[1]
        self.assertEqual(snapshot["interaction_mode"], "roll_pending")
        self.assertEqual(snapshot["danger_level"], "high")
        self.assertEqual(snapshot["mode_transition_signal"], "pending_roll")
        self.assertEqual(snapshot["pending_event_truth"]["monster_name"], "Goblin Cacador")
        self.assertEqual(snapshot["current_scene_state"]["scene_phase"], "roll_pending")
        set_pending_event.assert_called_once()
        persisted_event = set_pending_event.call_args.args[1]
        self.assertEqual(persisted_event["type"], "encounter")
        self.assertEqual(persisted_event["attribute"], "strength")
        self.assertEqual(persisted_event["monster_name"], "Goblin Cacador")
        self.assertEqual(result["pending_event"]["monster_name"], "Goblin Cacador")
        self.assertEqual(result["suggested_actions"], [])
        store_suggested_actions.assert_called_once_with(character.id, [])
        store_player_message.assert_called_once_with(character.id, "encounter_goblin", "Eu puxo a arma.")
        store_game_messages.assert_not_called()
        self.assertEqual(result["gm_message"], "")

    def test_run_master_turn_creates_strength_roll_for_throwing_a_goblin_even_when_llm_skips_event(self) -> None:
        character = SimpleNamespace(
            id=19,
            name="Rowan",
            class_name="fighter",
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

        with (
            patch.object(service, "build_scene_context", return_value={"title": "Emboscada", "lead": "O goblin jaz aos seus pés."}),
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
                        "narration": "O corpo parece pesado demais para sair do lugar com facilidade.",
                        "event": None,
                        "story_event": None,
                        "next_scene": None,
                        "suggested_actions": [],
                    }
                ),
            ),
            patch.object(service, "set_authority_snapshot") as set_snapshot,
            patch.object(service, "store_suggested_actions") as store_suggested_actions,
            patch.object(service, "set_context_hint"),
            patch.object(service, "set_pending_event") as set_pending_event,
            patch.object(service, "store_game_messages") as store_game_messages,
            patch.object(service, "store_player_message") as store_player_message,
        ):
            result = service.run_master_turn(character, "Quero agora arremessar o goblin a 10 metros de distancia.")

        set_snapshot.assert_called_once()
        store_suggested_actions.assert_called_once_with(character.id, [])
        store_player_message.assert_called_once_with(
            character.id,
            "encounter_goblin",
            "Quero agora arremessar o goblin a 10 metros de distancia.",
        )
        store_game_messages.assert_not_called()
        set_pending_event.assert_called_once()
        pending_event = set_pending_event.call_args.args[1]
        self.assertEqual(pending_event["type"], "skill_check")
        self.assertEqual(pending_event["attribute"], "strength")
        self.assertEqual(pending_event["label"], "FOR")
        self.assertEqual(pending_event["action_kind"], "move")
        self.assertEqual(result["pending_event"]["attribute"], "strength")
        self.assertEqual(result["gm_message"], "")
        self.assertEqual(result["suggested_actions"], [])

    def test_run_master_turn_returns_story_event_announcement_before_pending_roll(self) -> None:
        character = SimpleNamespace(
            id=14,
            name="Rowan",
            class_name="fighter",
            story_scene="chapter_entry",
            story_act=1,
        )
        story_event = {
            "type": "forced_encounter",
            "scene": "encounter_goblin",
            "monster_slug": "goblin-cacador",
            "trigger_text": "Os arbustos explodem em um salto brusco, e um goblin irrompe para cortar a trilha",
        }

        with (
            patch.object(service, "build_scene_context", return_value={"title": "Trilha", "lead": "A mata aperta."}),
            patch.object(service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(service, "get_story_inventory", return_value=[]),
            patch.object(service, "get_context_hint", return_value=None),
            patch.object(service, "get_recent_reward", return_value=None),
            patch.object(service, "get_recent_game_messages", return_value=[]),
            patch.object(service, "get_latest_memory_summary", return_value=None),
            patch.object(service, "build_master_graph_state", return_value={"authoritative_state": {}}),
            patch.object(
                service,
                "invoke_and_finalize_master_graph",
                return_value=SimpleNamespace(
                    payload={
                        "narration": "A mata fica quieta por um segundo.",
                        "event": None,
                        "story_event": story_event,
                        "next_scene": None,
                        "suggested_actions": [],
                    }
                ),
            ),
            patch.object(service, "persist_story_state") as persist_story_state,
            patch.object(service, "set_context_hint"),
            patch.object(service, "set_authority_snapshot"),
            patch.object(service, "set_pending_event"),
            patch.object(service, "store_suggested_actions"),
            patch.object(service, "store_game_messages") as store_game_messages,
        ):
            result = service.run_master_turn(character, "Eu avanço pela trilha.")

        persist_story_state.assert_called_once_with(character.id, scene="encounter_goblin", act=1)
        store_game_messages.assert_called_once()
        gm_message = store_game_messages.call_args.args[3]
        self.assertIn("Os arbustos explodem", gm_message)
        self.assertIn("goblin", gm_message.lower())
        self.assertEqual(result["gm_message"], gm_message)
        self.assertEqual(result["pending_event"]["type"], "encounter")
        self.assertEqual(result["suggested_actions"], [])


if __name__ == "__main__":
    unittest.main()
