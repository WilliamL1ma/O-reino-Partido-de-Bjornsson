import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app as app_module


class AppNarrativeRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 7

    def test_game_master_route_delegates_to_service_payload(self) -> None:
        character = SimpleNamespace(class_name="wizard")
        service_response = SimpleNamespace(
            to_response=lambda: {
                "ok": True,
                "player_message": "Eu observo.",
                "gm_message": "O mestre descreve a cena.",
                "summary": "Resumo.",
                "pending_event": None,
                "next_scene": None,
                "current_moment": {"title": "Praca", "description": "A cidade respira."},
                "suggested_actions": ["Observar", "Perguntar"],
                "view_state": {
                    "scene": {"key": "act_two_crossroads", "title": "Encruzilhada"},
                    "current_moment": {"title": "Praca", "description": "A cidade respira."},
                    "pending_event": None,
                    "suggested_actions": ["Observar", "Perguntar"],
                    "recent_reward": None,
                    "inventory_preview": [],
                    "progress": {"act": 2, "experience": 0, "gold": 0},
                },
            }
        )

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_groq_is_configured", return_value=True),
            patch.object(app_module, "_get_pending_event", return_value=None),
            patch.object(app_module, "run_master_conversation", return_value=service_response) as run_service,
        ):
            response = self.client.post("/jogo/mestre", data={"message": "Eu observo."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["gm_message"], "O mestre descreve a cena.")
        self.assertEqual(response.get_json()["view_state"]["scene"]["title"], "Encruzilhada")
        run_service.assert_called_once()

    def test_roll_route_delegates_to_service_payload(self) -> None:
        character = SimpleNamespace(class_name="wizard")
        pending_event = {"label": "FOR", "roll_type": "Ataque"}
        service_response = SimpleNamespace(
            to_response=lambda: {
                "ok": True,
                "roll": 18,
                "attribute_label": "FOR",
                "attribute_bonus": 4,
                "total": 22,
                "difficulty": 15,
                "success": True,
                "partial": False,
                "decisive": True,
                "gm_message": "A criatura recua.",
                "suggested_actions": ["Avancar", "Revistar"],
                "xp_gain": 40,
                "gold_gain": 10,
                "loot": [{"name": "Garra"}],
                "loot_names": ["Garra"],
                "monster_name": "Goblin Cacador",
                "view_state": {
                    "scene": {"key": "encounter_goblin", "title": "Emboscada"},
                    "current_moment": {"title": "Emboscada", "description": "O perigo cedeu."},
                    "pending_event": None,
                    "suggested_actions": ["Avancar", "Revistar"],
                    "recent_reward": {"monster_name": "Goblin Cacador"},
                    "inventory_preview": [{"name": "Garra", "value": None}],
                    "progress": {"act": 1, "experience": 40, "gold": 10},
                },
            }
        )

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_get_pending_event", return_value=pending_event),
            patch.object(app_module, "run_roll_resolution", return_value=service_response) as run_service,
        ):
            response = self.client.post("/jogo/rolar/consequencia")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["monster_name"], "Goblin Cacador")
        self.assertEqual(response.get_json()["view_state"]["progress"]["gold"], 10)
        run_service.assert_called_once_with(
            character,
            pending_event,
            summarize_memory=app_module._summarize_memory_if_needed,
            refresh_character=ANY,
        )

    def test_game_master_route_masks_internal_exception_details(self) -> None:
        character = SimpleNamespace(class_name="wizard", id=22)

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_groq_is_configured", return_value=True),
            patch.object(app_module, "_get_pending_event", return_value=None),
            patch.object(app_module, "run_master_conversation", side_effect=RuntimeError("db timeout 42")),
        ):
            response = self.client.post("/jogo/mestre", data={"message": "Eu observo."})

        payload = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(payload["ok"])
        self.assertNotIn("db timeout 42", payload["message"])

    def test_roll_resolution_route_masks_internal_exception_details(self) -> None:
        character = SimpleNamespace(class_name="wizard", id=27)
        pending_event = {"label": "FOR", "roll_type": "Ataque"}

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_get_pending_event", return_value=pending_event),
            patch.object(app_module, "run_roll_resolution", side_effect=RuntimeError("sensitive stack detail")),
        ):
            response = self.client.post("/jogo/rolar/consequencia")

        payload = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(payload["ok"])
        self.assertNotIn("sensitive stack detail", payload["message"])

    def test_roll_start_route_masks_internal_exception_details(self) -> None:
        character = SimpleNamespace(class_name="wizard", id=41)
        pending_event = {"label": "FOR", "roll_type": "Ataque"}

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_get_pending_event", return_value=pending_event),
            patch.object(app_module, "run_roll_start", side_effect=RuntimeError("secret roll stack")),
        ):
            response = self.client.post("/jogo/rolar")

        payload = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(payload["ok"])
        self.assertNotIn("secret roll stack", payload["message"])


if __name__ == "__main__":
    unittest.main()
