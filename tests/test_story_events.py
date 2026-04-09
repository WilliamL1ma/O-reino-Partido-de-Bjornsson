import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative import story_events


class StoryEventsTests(unittest.TestCase):
    def test_apply_story_event_uses_trigger_text_for_forced_encounter_announcement(self) -> None:
        character = SimpleNamespace(
            story_act=1,
            class_name="fighter",
            strength=16,
            dexterity=12,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=10,
            perception=11,
        )

        event = story_events.apply_story_event(
            character,
            {
                "type": "forced_encounter",
                "scene": "encounter_goblin",
                "monster_slug": "goblin-cacador",
                "trigger_text": "Os arbustos explodem em um salto curto, e o goblin já vem rasgando a trilha",
            },
            authority={},
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertIn("Os arbustos explodem", event.announcement_text)
        self.assertIn("dado", event.announcement_text.lower())
        self.assertEqual(event.pending_event["type"], "encounter")
        self.assertEqual(event.pending_event["monster_name"], "Goblin Caçador")

    def test_apply_story_event_builds_fallback_announcement_without_trigger_text(self) -> None:
        character = SimpleNamespace(
            story_act=1,
            class_name="wizard",
            strength=9,
            dexterity=11,
            constitution=10,
            intelligence=16,
            wisdom=14,
            charisma=12,
            perception=13,
        )

        event = story_events.apply_story_event(
            character,
            {
                "type": "forced_encounter",
                "scene": "encounter_goblin",
                "monster_slug": "goblin-cacador",
            },
            authority={},
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertIn("Goblin Caçador", event.announcement_text)
        self.assertIn("reação", event.announcement_text.lower())
        self.assertEqual(event.pending_event["monster_slug"], "goblin-cacador")


if __name__ == "__main__":
    unittest.main()
