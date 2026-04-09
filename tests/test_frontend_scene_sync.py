import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class FrontendSceneSyncTests(unittest.TestCase):
    def test_game_script_avoids_hard_reload_on_scene_transition(self) -> None:
        script_text = (ROOT_DIR / "frontend" / "script.js").read_text(encoding="utf-8")

        self.assertNotIn("location.reload(", script_text)
        self.assertIn("applyViewState(payload.view_state", script_text)

    def test_game_page_loads_roll_lifecycle_helper(self) -> None:
        template_text = (ROOT_DIR / "frontend" / "game_play.html").read_text(encoding="utf-8")

        self.assertIn('<script src="/game_ui_helpers.js"></script>', template_text)


if __name__ == "__main__":
    unittest.main()
