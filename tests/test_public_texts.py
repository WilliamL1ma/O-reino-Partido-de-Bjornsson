import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FILES_TO_VALIDATE = [
    ROOT_DIR / "backend" / "app.py",
    ROOT_DIR / "backend" / "narrative" / "action_rolls.py",
    ROOT_DIR / "backend" / "narrative" / "game_master_service.py",
    ROOT_DIR / "backend" / "narrative" / "llm_gateway.py",
    ROOT_DIR / "backend" / "narrative" / "memory_service.py",
    ROOT_DIR / "backend" / "narrative" / "roll_service.py",
    ROOT_DIR / "backend" / "narrative" / "story_events.py",
    ROOT_DIR / "backend" / "narrative" / "web_handlers.py",
    ROOT_DIR / "backend" / "web_blueprints" / "auth.py",
    ROOT_DIR / "frontend" / "player_home.html",
    ROOT_DIR / "frontend" / "script.js",
]
SUSPICIOUS_TOKENS = [
    "Ã",
    "Â",
    "portuguęs",
    "Vocę",
    "birth_daté",
    "raté limit",
]


class PublicTextQualityTests(unittest.TestCase):
    def test_public_files_are_clean_utf8_and_free_of_known_corruption_tokens(self) -> None:
        for path in FILES_TO_VALIDATE:
            text = path.read_text(encoding="utf-8")
            for token in SUSPICIOUS_TOKENS:
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
