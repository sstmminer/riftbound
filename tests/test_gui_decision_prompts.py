import unittest
from types import SimpleNamespace

from riftbound.gui import OriginsGUI
from riftbound.origins import OriginsRules


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


if __name__ == "__main__":
    unittest.main()
