import json
import random
import unittest

from riftbound.origins import OriginsRules


class HiddenTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(81))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["fields"][0]["controller"] = 0
        self.state["players"][0]["energy"] = 10
        self.state["players"][0]["power"] = ["fury", "calm", "mind", "body"] * 3
        self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)

    def card(self, code):
        row = self.state["players"][0]
        uid = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == "OGN-219")
        row["main"].remove(uid)
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_hide_is_private_to_owner_and_uses_facedown_zone(self):
        card = self.card("OGN-053")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.rules.validate(self.state)
        self.assertEqual(self.state["players"][0]["hidden"][0]["field"], 0)
        self.assertEqual(self.rules.observe(self.state, 0)["players"][0]["hidden"][0]["code"], "OGN-053")
        self.assertEqual(self.rules.observe(self.state, 1)["players"][0]["hidden"][0]["code"], "__back__")

    def test_hidden_stand_united_prompts_target_then_enters_chain(self):
        card = self.card("OGN-053")
        hide = next(a for a in self.rules.legal_actions(self.state) if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, hide, random.Random(3))
        self.state["turn"] = 3
        friendly = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_hidden_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.assertEqual(self.state["phase"], "decision")
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and friendly["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(3))
        self.assertEqual(self.state["phase"], "chain")


if __name__ == "__main__":
    unittest.main()
