import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative import roll_service


class RollServiceTests(unittest.TestCase):
    def test_run_roll_resolution_returns_clean_response_payload(self) -> None:
        character = SimpleNamespace(id=22)
        pending_event = {"label": "FOR", "roll_type": "Ataque"}
        summarize_memory = Mock()

        with patch.object(
            roll_service,
            "resolve_pending_roll_with_master",
            return_value={
                "roll_result": {
                    "roll": 17,
                    "attribute_bonus": 3,
                    "total": 20,
                    "difficulty": 15,
                    "success": True,
                    "partial": False,
                    "decisive": True,
                    "xp_gain": 45,
                    "gold_gain": 12,
                    "loot": [{"name": "Presa de Goblin"}],
                    "monster": {"name": "Goblin Cacador"},
                },
                "gm_message": "O golpe abre a guarda da criatura.",
                "suggested_actions": ["Revistar o corpo", "Observar o entorno"],
                "reward_update": {"loot_names": ["Presa de Goblin"]},
            },
        ):
            snapshot = roll_service.run_roll_resolution(
                character,
                pending_event,
                summarize_memory=summarize_memory,
            )

        summarize_memory.assert_called_once_with(character)
        self.assertEqual(
            snapshot.to_response(),
            {
                "ok": True,
                "roll": 17,
                "attribute_label": "FOR",
                "attribute_bonus": 3,
                "total": 20,
                "difficulty": 15,
                "success": True,
                "partial": False,
                "decisive": True,
                "gm_message": "O golpe abre a guarda da criatura.",
                "suggested_actions": ["Revistar o corpo", "Observar o entorno"],
                "xp_gain": 45,
                "gold_gain": 12,
                "loot": [{"name": "Presa de Goblin"}],
                "loot_names": ["Presa de Goblin"],
                "monster_name": "Goblin Cacador",
            },
        )

    def test_resolve_pending_roll_with_master_persists_rich_authority_snapshot(self) -> None:
        character = SimpleNamespace(id=22, name="Rowan", story_scene="encounter_goblin")
        pending_event = {
            "type": "encounter",
            "attribute": "strength",
            "difficulty": 14,
            "monster_slug": "goblin-cacador",
            "monster_name": "Goblin Cacador",
            "roll_type": "Ataque",
            "label": "FOR",
        }

        with (
            patch.object(
                roll_service,
                "roll_pending_event",
                return_value={
                    "event": pending_event,
                    "roll": 16,
                    "attribute_bonus": 3,
                    "total": 19,
                    "difficulty": 14,
                    "success": True,
                    "partial": False,
                    "decisive": False,
                    "xp_gain": 45,
                    "gold_gain": 12,
                    "loot": [{"name": "Presa de Goblin", "value": 12}],
                    "monster": {"name": "Goblin Cacador"},
                },
            ),
            patch.object(roll_service, "build_scene_context", return_value={"title": "Emboscada", "lead": "A trilha fecha."}),
            patch.object(roll_service, "get_story_flags", return_value={"chapter_started": True}),
            patch.object(roll_service, "get_story_inventory", return_value=[]),
            patch.object(roll_service, "get_latest_memory_summary", return_value=None),
            patch.object(roll_service, "get_recent_game_messages", return_value=[]),
            patch.object(roll_service, "build_master_graph_state", return_value={"authoritative_state": {}}),
            patch.object(
                roll_service,
                "invoke_and_finalize_master_graph",
                return_value=SimpleNamespace(
                    payload={
                        "narration": "Voce quebra a postura do goblin.",
                        "suggested_actions": ["Revistar o corpo", "Observar o entorno"],
                    }
                ),
            ),
            patch.object(
                roll_service,
                "apply_roll_rewards",
                return_value={"inventory": [], "flags": {}, "loot_names": ["Presa de Goblin"]},
            ),
            patch.object(roll_service, "clear_pending_event") as clear_pending_event,
            patch.object(roll_service, "store_suggested_actions") as store_actions,
            patch.object(roll_service, "store_game_messages") as store_messages,
            patch.object(roll_service, "set_authority_snapshot") as set_snapshot,
        ):
            result = roll_service.resolve_pending_roll_with_master(character, pending_event)

        clear_pending_event.assert_called_once_with(22)
        store_actions.assert_called_once_with(22, ["Revistar o corpo", "Observar o entorno"])
        store_messages.assert_called_once()
        set_snapshot.assert_called_once()
        persisted_snapshot = set_snapshot.call_args.args[1]
        self.assertEqual(persisted_snapshot["interaction_mode"], "post_combat")
        self.assertEqual(persisted_snapshot["mode_transition_signal"], "post_combat_loot_window")
        self.assertEqual(persisted_snapshot["target_source"], "roll_resolution")
        self.assertEqual(persisted_snapshot["recent_reward_truth"]["loot_names"], ["Presa de Goblin"])
        self.assertEqual(persisted_snapshot["current_scene_state"]["scene_phase"], "post_combat")
        self.assertEqual(result["reward_update"]["loot_names"], ["Presa de Goblin"])


if __name__ == "__main__":
    unittest.main()
