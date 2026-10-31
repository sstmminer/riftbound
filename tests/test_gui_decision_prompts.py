import unittest
from types import SimpleNamespace

from riftbound.gui import OriginsGUI
from riftbound.origins import OriginsRules
from riftbound.engine import Action


class GuiDecisionPromptTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(__import__("random").Random(13))
        self.state.update(phase="decision", actor=0, turn_player=0, turn=2)
        self.gui = object.__new__(OriginsGUI)
        self.gui.rules = self.rules
        self.gui.env = SimpleNamespace(
            _state=self.state,
            observe=lambda _player: self.rules.observe(self.state, 0),
        )

    def test_prompt_names_source_and_ordered_targets(self):
        first = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        prompt = self.gui._decision_prompt({
            "kind": "target", "player": 0,
            "targets": [first["id"], second["id"]],
            "multi": True, "min": 2, "max": 2, "allow_repeat": True,
            "item": {"effect": "spell", "code": "OGN-029"},
        })
        self.assertIn("Falling Star", prompt)
        self.assertIn("按顺序", prompt)
        self.assertIn("2 个合法目标", prompt)

    def test_prompt_describes_chain_target_window(self):
        prompt = self.gui._decision_prompt({
            "kind": "chain_target", "player": 0,
            "targets": ["chain:0"],
            "item": {"effect": "spell", "code": "OGN-080"},
        })
        self.assertIn("Mystic Reversal", prompt)
        self.assertIn("结算链", prompt)

    def test_transition_log_includes_chain_stage_and_confirmed_target(self):
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        before = {
            "phase": "chain", "chain": [{"effect": "spell", "code": "OGN-029",
                                             "owner": 0, "targets": []}],
            "pending": [], "players": [], "units": [],
        }
        after = {
            "phase": "decision", "chain": [{"effect": "spell", "code": "OGN-029",
                                              "owner": 0, "targets": [target["id"]]}],
            "pending": [], "players": [], "units": [],
            "decision": {"kind": "target", "player": 0,
                          "targets": [target["id"]], "multi": False,
                          "item": {"effect": "spell", "code": "OGN-029"}},
        }
        logs = []
        self.gui.log_add = logs.append
        self.gui._log_transition(before, after)
        joined = "\n".join(logs)
        self.assertIn("结算链", joined)
        self.assertIn("Falling Star", joined)
        self.assertIn("Vanguard Sergeant", joined)
        self.assertIn("等待 P0", joined)

    def test_prompt_describes_divine_zone_requirements(self):
        prompt = self.gui._decision_prompt({
            "kind": "divine", "player": 0,
            "choices": {"units": ["p0:u1"], "gear": [], "runes": ["p0:r1", "p0:r2"], "hand": ["p0:c1"]},
            "selected": {"units": ["p0:u1"], "runes": [], "hand": []},
            "required": {"units": 1, "runes": 2, "hand": 1},
            "item": {"effect": "spell", "code": "OGN-244"},
        })
        self.assertIn("Divine Judgment", prompt)
        self.assertIn("单位 1/1", prompt)
        self.assertIn("符文 0/2", prompt)
        self.assertIn("点击卡牌切换高亮", prompt)

    def test_decision_selected_ids_include_divine_zone_choices(self):
        self.gui.selected_decision_targets = ["local-target"]
        self.state["decision"] = {
            "kind": "divine", "player": 0,
            "choices": {"units": [], "gear": [], "runes": [], "hand": []},
            "selected": {"units": ["p0:u1"], "runes": ["p0:r1"]},
            "required": {},
        }
        self.assertEqual(self.gui._decision_selected_ids(),
                         {"local-target", "p0:u1", "p0:r1"})

    def test_display_reveal_close_label_names_actual_closer(self):
        label = OriginsGUI._reveal_close_label({"owner": 0, "closer": 1})
        self.assertIn("P1", label)
        self.assertIn("展示方 P0 的对手", label)

    def test_decision_with_public_reveal_uses_decision_bar(self):
        """Nocturne's replacement choice must remain actionable over reveal."""
        gui = object.__new__(OriginsGUI)
        calls = []
        gui.actions = SimpleNamespace(winfo_children=lambda: [])
        gui.env = SimpleNamespace(
            done=False,
            current_player=0,
            legal_actions=lambda: (Action.make("choose_option", option="nocturne_skip"),),
            observe=lambda _player: {
                "reveal": {"kind": "display", "owner": 0, "closer": 1, "cards": []},
                "decision": {"kind": "choice", "player": 0, "options": ["nocturne_skip"]},
            },
        )
        gui._render_decision_bar = lambda decision, legal: calls.append("decision")
        gui._render_reveal_bar = lambda reveal, legal: calls.append("reveal")
        gui._opponent_job = None
        gui.render_actions()
        self.assertEqual(calls, ["decision"])

    def test_nocturne_replacement_prompt_and_labels_are_explicit(self):
        prompt = self.gui._decision_prompt({
            "kind": "choice", "player": 0,
            "item": {"effect": "dazzling_aurora", "owner": 0},
            "nocturne_reveal": {"card": "missing-card"},
        })
        self.assertIn("请选择放逐并继续", prompt)
        self.assertIn("Nocturne", prompt)

    def test_pair_target_selection_rejects_invalid_prefix(self):
        decision = {"target_pairs": [["friendly", "enemy-a"], ["friendly-2", "enemy-b"]]}
        self.assertTrue(self.gui._target_sequence_extendable(decision, ["friendly"]))
        self.assertTrue(self.gui._target_sequence_extendable(decision, ["friendly", "enemy-a"]))
        self.assertFalse(self.gui._target_sequence_extendable(decision, ["friendly", "enemy-b"]))

    def test_ordered_pair_target_selection_preserves_order(self):
        decision = {"target_pairs": [["source", "destination"]], "ordered_pairs": True}
        self.assertTrue(self.gui._target_sequence_extendable(decision, ["source"]))
        self.assertFalse(self.gui._target_sequence_extendable(decision, ["destination"]))


if __name__ == "__main__":
    unittest.main()
