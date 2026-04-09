import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative.action_rolls import classify_player_action, normalize_pending_event


def _character() -> SimpleNamespace:
    return SimpleNamespace(
        class_name="fighter",
        strength=14,
        dexterity=13,
        constitution=12,
        intelligence=10,
        wisdom=11,
        charisma=9,
        perception=12,
    )


class ActionRollsTests(unittest.TestCase):
    def test_classify_player_action_recognizes_stealth_question(self) -> None:
        self.assertEqual(classify_player_action("Posso me esconder nas sombras e emboscar o goblin?"), "stealth")

    def test_classify_player_action_recognizes_new_combat_verbs(self) -> None:
        self.assertEqual(classify_player_action("Quero desarmar o goblin antes do proximo golpe."), "combat")

    def test_classify_player_action_recognizes_new_ritual_verbs(self) -> None:
        self.assertEqual(classify_player_action("Vou banir a corrupcao do altar agora."), "combat_magic")

    def test_normalize_pending_event_maps_tracking_to_survival(self) -> None:
        event = normalize_pending_event(
            _character(),
            "Quero rastrear as pegadas na lama antes de seguir.",
            {},
            None,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "skill_check")
        self.assertEqual(event["action_kind"], "survival")
        self.assertEqual(event["attribute"], "wisdom")
        self.assertEqual(event["label"], "SAB")

    def test_normalize_pending_event_maps_repair_to_craft(self) -> None:
        event = normalize_pending_event(
            _character(),
            "Vou reparar a barricada antes que ela ceda.",
            {},
            None,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["action_kind"], "craft")
        self.assertEqual(event["attribute"], "intelligence")
        self.assertEqual(event["label"], "INT")

    def test_normalize_pending_event_maps_stealth_verbs_to_dexterity(self) -> None:
        event = normalize_pending_event(
            _character(),
            "Vou despistar a patrulha e me ocultar entre as arvores.",
            {},
            None,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["action_kind"], "stealth")
        self.assertEqual(event["attribute"], "dexterity")
        self.assertEqual(event["label"], "DEX")


if __name__ == "__main__":
    unittest.main()
