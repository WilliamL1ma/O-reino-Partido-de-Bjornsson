import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative.session_store import (
    get_context_hint,
    get_recent_reward,
    get_suggested_actions,
    set_context_hint,
    set_recent_reward,
    store_suggested_actions,
)
from narrative.state_store import (
    get_authority_snapshot,
    get_context_hint as get_persisted_context_hint,
    get_pending_event,
    get_pending_roll_resolution,
    get_recent_reward as get_persisted_recent_reward,
    get_story_flags,
    get_story_inventory,
    get_suggested_actions as get_persisted_suggested_actions,
    set_authority_snapshot,
    set_context_hint as set_persisted_context_hint,
    set_pending_roll_resolution,
    set_recent_reward as set_persisted_recent_reward,
    store_suggested_actions as store_persisted_suggested_actions,
)


class _FakeDbSession:
    def __init__(self, character) -> None:
        self.character = character

    def get(self, _model, character_id: int):
        if character_id == self.character.id:
            return self.character
        return None


@contextmanager
def _fake_session_scope(character):
    yield _FakeDbSession(character)


class NarrativeSessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"

    def test_session_store_roundtrip(self) -> None:
        with self.app.test_request_context("/"):
            set_context_hint(7, {"kind": "post_encounter", "monster_name": "Goblin Cacador"})
            set_recent_reward(7, {"monster_name": "Goblin Cacador", "loot_names": ["Arco de Curto Alcance"]})
            store_suggested_actions(7, ["Revistar o corpo", "Observar os arredores"])

            self.assertEqual(get_context_hint(7), {"kind": "post_encounter", "monster_name": "Goblin Cacador"})
            self.assertEqual(get_recent_reward(7)["monster_name"], "Goblin Cacador")
            self.assertEqual(get_suggested_actions(7), ["Revistar o corpo", "Observar os arredores"])

    def test_session_store_returns_none_for_invalid_shapes(self) -> None:
        with self.app.test_request_context("/"):
            from flask import session

            session["game_context_hint_4"] = "x"
            session["game_recent_reward_4"] = ["x"]
            session["game_suggested_actions_4"] = "x"

            self.assertIsNone(get_context_hint(4))
            self.assertIsNone(get_recent_reward(4))
            self.assertIsNone(get_suggested_actions(4))


class NarrativeStateStoreTests(unittest.TestCase):
    def test_parses_story_fields_and_pending_event(self) -> None:
        character = SimpleNamespace(
            story_flags='{"chapter_started": true, "chapter_complete": false}',
            story_inventory='[{"name": "Flor de Prata", "value": 0}]',
            pending_event='{"type": "skill_check", "attribute": "wisdom", "difficulty": 12}',
        )

        self.assertEqual(get_story_flags(character)["chapter_started"], True)
        self.assertEqual(get_story_inventory(character)[0]["name"], "Flor de Prata")
        self.assertEqual(get_pending_event(character)["attribute"], "wisdom")

    def test_invalid_story_fields_fail_closed(self) -> None:
        character = SimpleNamespace(
            story_flags="[]",
            story_inventory="{}",
            pending_event='"x"',
        )

        self.assertEqual(get_story_flags(character), {})
        self.assertEqual(get_story_inventory(character), [])
        self.assertIsNone(get_pending_event(character))

    def test_persistent_runtime_state_roundtrip_uses_story_flags(self) -> None:
        character = SimpleNamespace(
            id=7,
            story_flags='{"chapter_started": true}',
            story_inventory="[]",
            pending_event=None,
        )

        with patch("narrative.state_store.session_scope", lambda: _fake_session_scope(character)):
            set_persisted_context_hint(7, {"kind": "post_encounter", "monster_name": "Goblin Cacador"})
            set_persisted_recent_reward(
                7,
                {
                    "monster_name": "Goblin Cacador",
                    "loot_names": ["Arco de Curto Alcance"],
                    "xp_gain": 30,
                    "gold_gain": 5,
                },
            )
            store_persisted_suggested_actions(7, ["Revistar o corpo", "Observar os arredores"])

        self.assertEqual(get_persisted_context_hint(character)["monster_name"], "Goblin Cacador")
        self.assertEqual(get_persisted_recent_reward(character)["loot_names"], ["Arco de Curto Alcance"])
        self.assertEqual(get_persisted_suggested_actions(character), ["Revistar o corpo", "Observar os arredores"])
        self.assertIn("narrative_runtime", get_story_flags(character))

    def test_persistent_authority_snapshot_roundtrip(self) -> None:
        character = SimpleNamespace(
            id=8,
            story_flags='{"chapter_started": true}',
            story_inventory="[]",
            pending_event=None,
        )

        with patch("narrative.state_store.session_scope", lambda: _fake_session_scope(character)):
            set_authority_snapshot(
                8,
                {
                    "scene_key": "encounter_goblin",
                    "current_target": "Goblin Cacador",
                    "interaction_mode": "combat",
                    "interaction_type": "combat",
                    "danger_level": "elevated",
                    "recent_outcome": "ongoing",
                    "mode_transition_signal": "active_threat",
                    "allowed_action_kinds": ["combat", "defend", "escape", "observe"],
                    "target_locked": True,
                    "target_source": "authority_snapshot",
                    "pending_event_truth": {
                        "type": "encounter",
                        "attribute": "strength",
                        "monster_name": "Goblin Cacador",
                    },
                    "current_scene_state": {
                        "scene_key": "encounter_goblin",
                        "scene_type": "encounter",
                        "scene_phase": "combat",
                        "allowed_next_scenes": ["act_two_crossroads"],
                        "has_pending_event": True,
                        "has_recent_reward": False,
                    },
                },
            )

        snapshot = get_authority_snapshot(character)
        self.assertEqual(snapshot["current_target"], "Goblin Cacador")
        self.assertEqual(snapshot["interaction_mode"], "combat")
        self.assertEqual(snapshot["mode_transition_signal"], "active_threat")
        self.assertEqual(snapshot["allowed_action_kinds"], ["combat", "defend", "escape", "observe"])
        self.assertEqual(snapshot["pending_event_truth"]["attribute"], "strength")
        self.assertEqual(snapshot["current_scene_state"]["scene_phase"], "combat")
        self.assertTrue(snapshot["current_scene_state"]["has_pending_event"])

    def test_pending_roll_resolution_roundtrip_normalizes_set_values(self) -> None:
        character = SimpleNamespace(
            id=9,
            story_flags='{"chapter_started": true}',
            story_inventory="[]",
            pending_event=None,
        )

        with patch("narrative.state_store.session_scope", lambda: _fake_session_scope(character)):
            set_pending_roll_resolution(
                9,
                {
                    "event": {"type": "encounter", "monster_slug": "goblin-cacador"},
                    "roll_result": {
                        "roll": 16,
                        "monster": {
                            "name": "Goblin Cacador",
                            "favored_tactics": {"precision", "mystic"},
                        },
                    },
                },
            )

        stored_flags = json.loads(character.story_flags)
        stored_resolution = stored_flags["narrative_runtime"]["pending_roll_resolution"]
        self.assertIsInstance(stored_resolution["roll_result"]["monster"]["favored_tactics"], list)
        self.assertCountEqual(
            stored_resolution["roll_result"]["monster"]["favored_tactics"],
            ["precision", "mystic"],
        )

        restored_resolution = get_pending_roll_resolution(character)
        self.assertEqual(restored_resolution["roll_result"]["monster"]["name"], "Goblin Cacador")
        self.assertCountEqual(
            restored_resolution["roll_result"]["monster"]["favored_tactics"],
            ["precision", "mystic"],
        )


if __name__ == "__main__":
    unittest.main()
