import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class MysticRechoiceTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(612))
        self.state.update(phase="chain", actor=0, turn_player=0, turn=3, passes=0)
        self.state["players"][0]["energy"] = 10
        self.state["players"][0]["power"] = ["calm"] * 4

    def _counter_scenario(self, code):
        row = self.state["players"][0]
        counter = row["main"].pop()
        self.state["cards"][counter]["code"] = "OGN-080"
        row["hand"].append(counter)
        target = self.state["players"][1]["main"].pop()
        self.state["cards"][target]["code"] = code
        self.state["chain"] = [{"effect": "spell", "owner": 1, "card": target,
                                 "code": code, "targets": [], "destination": None,
                                 # Simulate a choice made before Mystic Reversal;
                                 # the new controller must not inherit it.
                                 "choice": "cards", "choice_done": True}]
        self.state["chain_return"] = "main"
        return counter

    def _put_counter_on_chain(self, counter):
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_counter" and counter in a.arguments)
        self.rules.apply(self.state, action, random.Random(612))
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_chain_target" and "chain:0" in a.arguments)
        self.rules.apply(self.state, choose, random.Random(612))
        for _ in range(2):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(612))

    def test_party_favors_reopens_choice_after_mystic_reversal(self):
        counter = self._counter_scenario("OGN-071")
        # Simulate stale metadata from the spell's pre-counter controller;
        # Mystic Reversal must clear it before opening the new choice window.
        self.state["chain"][0].update(choice="cards", choice_done=True)
        self._put_counter_on_chain(counter)
        decision = self.state["decision"]
        self.assertTrue(decision.get("counter_retarget_choice"))
        self.assertEqual(decision["player"], 1)
        self.assertNotIn("choice", decision["item"])
        self.assertNotIn("choice_done", decision["item"])
        self.assertEqual(set(decision["options"]), {"cards", "runes"})
        self.assertNotIn("choice", self.state["chain"][-1])
        self.assertNotIn("choice_done", self.state["chain"][-1])
        self.rules.apply(self.state, Action.make("choose_option", option="runes"),
                         random.Random(612))
        self.assertEqual(self.state["chain"][-1]["choice"], "runes")
        self.assertTrue(self.state["chain"][-1]["choice_done"])

    def test_whirlwind_reopens_choice_then_target_after_mystic_reversal(self):
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        counter = self._counter_scenario("OGN-187")
        self._put_counter_on_chain(counter)
        self.assertEqual(self.state["decision"]["player"], 1)
        self.assertEqual(set(self.state["decision"]["options"]), {"return", "skip"})
        self.rules.apply(self.state, Action.make("choose_option", option="return"),
                         random.Random(612))
        self.assertEqual(self.state["decision"]["player"], 1)
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(612))
        self.assertEqual(self.state["chain"][-1]["targets"], [target["id"]])
        self.assertTrue(self.state["chain"][-1]["choice_done"])


if __name__ == "__main__":
    unittest.main()
