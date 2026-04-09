import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


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
            }
        )

        with (
            patch.object(app_module, "_get_character_by_user_id", return_value=character),
            patch.object(app_module, "_get_pending_event", return_value=pending_event),
            patch.object(app_module, "run_roll_resolution", return_value=service_response) as run_service,
        ):
            response = self.client.post("/jogo/rolar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["monster_name"], "Goblin Cacador")
        run_service.assert_called_once_with(
            character,
            pending_event,
            summarize_memory=app_module._summarize_memory_if_needed,
        )


if __name__ == "__main__":
    unittest.main()
