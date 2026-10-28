import random
import unittest

from riftbound.origins import OriginsRules


class SpellExpansionNewTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(123))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["chaos", "order"] * 4

    def spare(self, code):
        row = self.state["players"][0]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def drain(self):
        for _ in range(8):
            if self.state["phase"] not in {"chain", "showdown"}:
                return
            action = next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass")
            self.rules.apply(self.state, action, random.Random(9))
        self.fail("chain did not close")

    def test_stacked_deck_selects_one_of_top_three_and_recycles_rest(self):
        card = self.spare("OGN-183")
        row = self.state["players"][0]
        top = list(row["main"][:3])
        self.assertEqual(len(top), 3)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], top)
        chosen = top[1]
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and chosen in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertIn(chosen, row["hand"])
        self.assertTrue(all(uid in row["trash"] for uid in top if uid != chosen))

    def test_possession_takes_control_and_recalls_without_showdown(self):
        card = self.spare("OGN-203")
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and enemy["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(enemy["owner"], 0)
        self.assertEqual(enemy["location"], "base:0")
        self.assertTrue(enemy["exhausted"])
        self.assertEqual(self.state["phase"], "main")

    def test_imperial_decree_kills_unit_when_it_takes_damage(self):
        card = self.spare("OGN-221")
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertIn("imperial_decree", self.state)
        self.rules._deal_damage(self.state, target, 1)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertNotIn(target, self.state["units"])


if __name__ == "__main__":
    unittest.main()
