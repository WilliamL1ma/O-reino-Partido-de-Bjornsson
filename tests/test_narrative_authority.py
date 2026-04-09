import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative.authority import build_narrative_authority, build_scene_fallback_actions, sanitize_suggested_actions
from narrative.turn_pipeline import finalize_master_output
from narrative.turn_service import build_default_suggested_actions, build_master_graph_state, invoke_and_finalize_master_graph


class NarrativeAuthorityTests(unittest.TestCase):
    def test_builds_post_combat_authority_from_recent_reward(self) -> None:
        authority = build_narrative_authority(
            scene_key="encounter_goblin",
            scene={"type": "encounter", "title": "Emboscada", "lead": "Um goblin cacador ocupa a passagem."},
            allowed_next_scenes=["act_two_crossroads"],
            recent_messages=[
                {"role": "gm", "content": "O goblin cai e a trilha volta a respirar."},
                {"role": "player", "content": "Eu revisto o corpo."},
            ],
            pending_event=None,
            context_hint={"kind": "post_encounter", "monster_name": "Goblin Cacador"},
            recent_reward={"monster_name": "Goblin Cacador", "loot_names": ["Arco de Curto Alcance"]},
            inventory=[{"name": "Flor de Prata"}],
        )

        self.assertEqual(authority["current_target"], "Goblin Cacador")
        self.assertEqual(authority["interaction_mode"], "post_combat")
        self.assertEqual(authority["interaction_type"], "post_combat")
        self.assertEqual(authority["recent_outcome"], "victory")
        self.assertEqual(authority["mode_transition_signal"], "post_combat_loot_window")
        self.assertEqual(authority["allowed_action_kinds"], ["loot", "observe", "investigate", "move", "recover"])
        self.assertTrue(authority["target_locked"])
        self.assertTrue(authority["post_combat_pending_loot"])
        self.assertEqual(authority["inventory_truth"], ["Flor de Prata"])
        self.assertEqual(authority["recent_reward_truth"]["loot_names"], ["Arco de Curto Alcance"])
        self.assertEqual(authority["current_scene_state"]["scene_phase"], "post_combat")

    def test_builds_roll_pending_authority_from_pending_event(self) -> None:
        authority = build_narrative_authority(
            scene_key="encounter_lupus",
            scene={"type": "encounter", "title": "Olhos na Mata", "lead": "O lupus circula sua posicao."},
            allowed_next_scenes=["freya_legacy"],
            recent_messages=[],
            pending_event={"type": "encounter", "monster_name": "Lupus da Floresta Profunda"},
            context_hint=None,
            recent_reward=None,
        )

        self.assertEqual(authority["current_target"], "Lupus da Floresta Profunda")
        self.assertEqual(authority["interaction_mode"], "roll_pending")
        self.assertEqual(authority["danger_level"], "high")
        self.assertEqual(authority["mode_transition_signal"], "pending_roll")

    def test_sanitize_suggested_actions_drops_combat_in_post_combat_state(self) -> None:
        authority = {
            "interaction_mode": "post_combat",
            "allowed_action_kinds": ["loot", "observe", "investigate", "move", "recover"],
            "current_target": "Goblin Cacador",
        }
        fallback_actions = build_scene_fallback_actions("encounter_goblin", authority, {"kind": "post_encounter"})

        actions = sanitize_suggested_actions(
            [
                "Atacar o goblin de novo para garantir a vitória",
                "Revistar o corpo do goblin com cuidado",
                "Observar os arredores antes de sair do local",
            ],
            authority,
            fallback_actions,
        )

        self.assertNotIn("Atacar o goblin de novo para garantir a vitória", actions)
        self.assertEqual(
            actions,
            [
                "Revistar o corpo do goblin com cuidado",
                "Observar os arredores antes de sair do local",
            ],
        )

    def test_finalize_master_output_uses_fallback_when_actions_are_all_invalid(self) -> None:
        authority = {
            "interaction_mode": "post_combat",
            "allowed_action_kinds": ["loot", "observe", "investigate", "move", "recover"],
            "current_target": "Goblin Cacador",
        }
        fallback_actions = build_scene_fallback_actions("encounter_goblin", authority, {"kind": "post_encounter"})

        payload = finalize_master_output(
            {
                "result_narration": "O goblin cai sem voltar a ameaçar você.",
                "result_event": None,
                "result_next_scene": None,
                "result_suggested_actions": [
                    "Atacar o goblin mais uma vez",
                    "Intimidar o goblin derrotado",
                ],
            },
            authority,
            fallback_actions,
        )

        self.assertEqual(payload["suggested_actions"], fallback_actions[:5])

    def test_sanitize_suggested_actions_rejects_target_swap_when_target_is_locked(self) -> None:
        authority = {
            "interaction_mode": "combat",
            "allowed_action_kinds": ["combat", "defend", "escape", "observe"],
            "current_target": "Goblin Cacador",
            "target_locked": True,
        }
        fallback_actions = build_scene_fallback_actions("encounter_goblin", authority)

        actions = sanitize_suggested_actions(
            [
                "Atacar a raposa antes que ela fuja",
                "Observar o goblin antes de investir de novo",
                "Buscar cobertura e medir o terreno",
            ],
            authority,
            fallback_actions,
        )

        self.assertEqual(
            actions,
            [
                "Observar o goblin antes de investir de novo",
                "Buscar cobertura e medir o terreno",
            ],
        )

    def test_build_default_suggested_actions_respects_post_combat_reward_state(self) -> None:
        actions = build_default_suggested_actions(
            scene_key="encounter_goblin",
            scene={"type": "encounter", "title": "Emboscada", "lead": "Um goblin cacador ocupa a passagem."},
            allowed_next_scenes=["act_two_crossroads"],
            context_hint={"kind": "post_encounter", "monster_name": "Goblin Cacador"},
            recent_reward={"monster_name": "Goblin Cacador", "loot_names": ["Arco de Curto Alcance"]},
        )

        self.assertEqual(actions[0], "Revistar com calma o corpo de Goblin Cacador")

    def test_build_narrative_authority_reuses_persisted_snapshot_when_scene_matches(self) -> None:
        authority = build_narrative_authority(
            scene_key="encounter_goblin",
            scene={"type": "encounter", "title": "Emboscada", "lead": "A trilha permanece tensa."},
            allowed_next_scenes=["act_two_crossroads"],
            recent_messages=[],
            pending_event=None,
            context_hint=None,
            recent_reward=None,
            persisted_authority={
                "scene_key": "encounter_goblin",
                "current_target": "Goblin Cacador",
                "interaction_mode": "combat",
                "target_locked": True,
            },
        )

        self.assertEqual(authority["current_target"], "Goblin Cacador")
        self.assertEqual(authority["interaction_mode"], "combat")

    def test_build_narrative_authority_prefers_same_scene_snapshot_over_conflicting_text_history(self) -> None:
        authority = build_narrative_authority(
            scene_key="encounter_goblin",
            scene={"type": "encounter", "title": "Emboscada", "lead": "A raposa cruza a trilha depois do confronto."},
            allowed_next_scenes=["act_two_crossroads"],
            recent_messages=[
                {"role": "gm", "content": "Uma raposa aparece entre as arvores."},
                {"role": "player", "content": "Eu observo a raposa e recuo."},
            ],
            pending_event=None,
            context_hint=None,
            recent_reward=None,
            persisted_authority={
                "scene_key": "encounter_goblin",
                "current_target": "Goblin Cacador",
                "interaction_mode": "combat",
                "target_locked": True,
                "mode_transition_signal": "active_threat",
                "allowed_action_kinds": ["combat", "defend", "escape", "observe"],
                "current_scene_state": {"scene_phase": "combat"},
            },
        )

        self.assertEqual(authority["current_target"], "Goblin Cacador")
        self.assertEqual(authority["target_source"], "authority_snapshot")
        self.assertEqual(authority["interaction_mode"], "combat")
        self.assertEqual(authority["mode_transition_signal"], "active_threat")
        self.assertEqual(authority["allowed_action_kinds"], ["combat", "defend", "escape", "observe"])

    def test_build_narrative_authority_uses_context_hint_as_post_combat_truth_without_text(self) -> None:
        authority = build_narrative_authority(
            scene_key="encounter_goblin",
            scene={"type": "encounter", "title": "Emboscada", "lead": "O silêncio volta para a trilha."},
            allowed_next_scenes=["act_two_crossroads"],
            recent_messages=[],
            pending_event=None,
            context_hint={"kind": "post_encounter", "monster_name": "Goblin Cacador"},
            recent_reward=None,
            persisted_authority={
                "scene_key": "encounter_goblin",
                "current_target": "Goblin Cacador",
                "interaction_mode": "post_combat",
                "recent_outcome": "victory",
            },
        )

        self.assertEqual(authority["interaction_mode"], "post_combat")
        self.assertEqual(authority["recent_outcome"], "victory")
        self.assertEqual(authority["mode_transition_signal"], "post_combat_resolution")
        self.assertTrue(authority["target_locked"])

    def test_build_master_graph_state_keeps_provider_config_out_of_payload(self) -> None:
        character = SimpleNamespace(
            id=7,
            name="Rowan",
            race_name="Humano",
            class_name="Wizard",
            personality="Calmo",
            objective="Sobreviver",
            fear="Perder o controle",
            strength=10,
            dexterity=12,
            constitution=11,
            intelligence=15,
            wisdom=13,
            charisma=9,
            perception=14,
            experience=20,
            gold=7,
            story_scene="encounter_goblin",
            story_act=1,
        )

        with (
            patch("narrative.turn_service.get_story_flags", return_value={"chapter_started": True}),
            patch("narrative.turn_service.get_story_inventory", return_value=[{"name": "Flor de Prata"}]),
            patch("narrative.turn_service.get_pending_event", return_value=None),
            patch("narrative.turn_service.get_context_hint", return_value=None),
            patch("narrative.turn_service.get_recent_reward", return_value=None),
            patch("narrative.turn_service.get_authority_snapshot", return_value={"scene_key": "encounter_goblin"}),
            patch("narrative.turn_service.build_lore_packet", return_value={"chapter": "I"}),
        ):
            payload = build_master_graph_state(
                character,
                {"title": "Emboscada", "lead": "Um goblin vigia a passagem.", "type": "encounter"},
                [SimpleNamespace(role="gm", content="O goblin rosna.")],
                "Resumo.",
                mode="turn",
                player_message="Eu observo.",
            )

        self.assertNotIn("api_key", payload)
        self.assertNotIn("model", payload)
        self.assertNotIn("timeout", payload)
        self.assertEqual(payload["authoritative_state"]["current_scene_state"]["scene_key"], "encounter_goblin")

    def test_invoke_and_finalize_master_graph_returns_clean_payload(self) -> None:
        graph_staté = {
            "authoritative_state": {
                "interaction_mode": "post_combat",
                "allowed_action_kinds": ["loot", "observe", "investigate", "move", "recover"],
                "current_target": "Goblin Cacador",
                "target_locked": True,
            },
            "fallback_actions": [
                "Revistar com calma o corpo de Goblin Cacador",
                "Observar os arredores antes de sair do local",
            ],
        }

        def _graph_runner(_state: dict) -> dict:
            return {
                "result_narration": "O goblin cai sem voltar a ameaçar você.",
                "result_event": None,
                "result_next_scene": None,
                "result_suggested_actions": [
                    "Atacar a raposa agora",
                    "Revistar com calma o corpo de Goblin Cacador",
                ],
            }

        result = invoke_and_finalize_master_graph(graph_state, _graph_runner)

        self.assertEqual(result.payload["narration"], "O goblin cai sem voltar a ameaçar você.")
        self.assertEqual(result.payload["suggested_actions"], ["Revistar com calma o corpo de Goblin Cacador"])


if __name__ == "__main__":
    unittest.main()
