import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative.scene_flow import allowed_next_scenes, build_scene_context, get_encounter_transition, initial_story_state


class SceneFlowTests(unittest.TestCase):
    def test_allowed_next_scenes_returns_authoritative_transitions(self) -> None:
        self.assertEqual(
            allowed_next_scenes("act_three_threshold"),
            ["encounter_aranha", "encounter_lupus", "encounter_passaro", "freya_legacy"],
        )
        self.assertEqual(allowed_next_scenes("chapter_complete"), [])

    def test_get_encounter_transition_returns_copy(self) -> None:
        transition = get_encounter_transition("encounter_raposa")
        self.assertEqual(transition["monster"], "raposa-fogo")
        self.assertEqual(transition["flag"], "act_two_farm_done")
        transition["monster"] = "outro"
        self.assertEqual(get_encounter_transition("encounter_raposa")["monster"], "raposa-fogo")

    def test_build_scene_context_hides_farm_option_after_flag(self) -> None:
        scene = build_scene_context(
            "act_two_crossroads",
            {"act_two_farm_done": True},
            [{"name": "Flor de Prata"}],
        )

        actions = [option["action"] for option in scene["options"]]
        self.assertNotIn("go_raposa", actions)
        self.assertEqual(scene["inventory"][0]["name"], "Flor de Prata")

    def test_initial_story_state_starts_chapter_entry(self) -> None:
        state = initial_story_state([{"name": "Capa Velha"}])
        self.assertEqual(state["scene"], "chapter_entry")
        self.assertEqual(state["act"], 1)
        self.assertTrue(state["flags"]["chapter_started"])
        self.assertEqual(state["inventory"][0]["name"], "Capa Velha")


if __name__ == "__main__":
    unittest.main()
