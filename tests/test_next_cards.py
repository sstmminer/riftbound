import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class NextCardBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(77))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["order"] * 8
        self.state["fields"][0]["controller"] = 0

    def give(self, code):
        row = self.state["players"][0]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_pakaa_hidden_and_bandle_tree_two_slots(self):
        first = self.give("OGN-135")
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "hide_card" and first in a.arguments]
        self.assertTrue(actions)
        self.rules.apply(self.state, actions[0], random.Random(1))
        second = self.give("OGN-135")
        self.state["fields"][0]["code"] = "OGN-278"
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "hide_card" and second in a.arguments]
        self.assertTrue(actions)

    def test_noxus_saboteur_blocks_opponent_hidden(self):
        saboteur = self.rules._new_unit(self.state, "OGN-018", 1, 0, exhausted=False)
        card = self.give("OGN-135")
        self.assertFalse(any(a.kind == "hide_card" and card in a.arguments
                             for a in self.rules.legal_actions(self.state)))
        self.state["units"].remove(saboteur)

    def test_swift_scout_returns_teemo(self):
        self.state["players"][0]["legend"] = "OGN-263"
        teemo_card = self.give("OGN-121")
        unit = self.rules._new_unit(self.state, "OGN-121", 0, 0, card=teemo_card, exhausted=False)
        self.state["players"][0]["hand"].remove(teemo_card)
        self.state["players"][0]["energy"] = 1
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "legend_teemo" and unit["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertNotIn(unit, self.state["units"])
        self.assertIn(teemo_card, self.state["players"][0]["hand"])

    def test_guillotine_marks_target_until_next_damage(self):
        card = self.give("OGN-254")
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and target["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(4):
            if self.state["phase"] not in {"chain", "showdown"}:
                break
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(target.get("kill_on_damage"), self.state["turn"])
        self.rules._deal_damage(self.state, target, 1)
        self.rules._cleanup(self.state, random.Random(1))
        self.assertNotIn(target, self.state["units"])

    def test_kinkou_monk_requires_explicit_up_to_two_targets(self):
        card = self.give("OGN-141")
        self.state["players"][0]["power"] = ["body"] * 8
        first = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments and '"location":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        self.assertTrue(any(a.kind == "choose_target" and first["id"] in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and first["id"] in a.arguments),
                         random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and second["id"] in a.arguments),
                         random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "confirm_targets"),
                         random.Random(1))
        self.assertEqual(self.state["chain"][-1]["targets"], [first["id"], second["id"]])


if __name__ == "__main__":
    unittest.main()
