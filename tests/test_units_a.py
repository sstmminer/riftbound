import random
import unittest

from riftbound.origins import OriginsRules


class UnitBatchATests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(21))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        for row in self.state["players"]:
            row["energy"], row["power"] = 20, ["fury", "order", "mind", "body"]

    def unit(self, code, owner=0, location=0):
        unit = self.rules._new_unit(self.state, code, owner, location, card=None, exhausted=False)
        return unit

    def test_assault_two_and_taric_shield_aura(self):
        attacker = self.unit("OGN-037", location=0)
        defender = self.unit("OGN-219", owner=1, location=0)
        aura = self.unit("OGN-074", owner=1, location=0)
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.assertEqual(self.rules.might(self.state, attacker), 5)
        self.assertEqual(self.rules.might(self.state, defender), 5)
        self.assertEqual(self.rules.might(self.state, aura), 5)

    def test_lee_sin_can_exhaust_to_gain_a_buff(self):
        unit = self.unit("OGN-078", location="base:0")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "unit_buff" and unit["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(2))
        self.assertTrue(unit["exhausted"])
        self.assertEqual(unit["buff"], 1)

    def test_ravenbloom_student_gains_power_when_spell_is_played(self):
        student = self.unit("OGN-103", location="base:0")
        self.unit("OGN-219", owner=1, location=0)
        spell = next(uid for uid, card in self.state["cards"].items()
                      if card["code"] == "OGN-024")
        for zone in ("main", "hand", "trash"):
            if spell in self.state["players"][0][zone]:
                self.state["players"][0][zone].remove(spell)
                break
        self.state["players"][0]["hand"].append(spell)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and spell in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.assertEqual(student["temporary"], 0)
        self.assertEqual(self.state["chain"][-1]["effect"], "ravenbloom")
        while self.state["phase"] == "chain":
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(3))
        self.assertEqual(student["temporary"], 1)

    def test_dangerous_duo_legion_trigger_opens_target_choice(self):
        target = self.unit("OGN-219", location="base:0")
        card = next(uid for uid, row in self.state["cards"].items() if row["code"] == "OGN-219")
        for zone in ("main", "hand", "trash"):
            if card in self.state["players"][0][zone]:
                self.state["players"][0][zone].remove(card)
                break
        self.state["players"][0]["hand"].append(card)
        self.state["cards"][card]["code"] = "OGN-016"
        self.state["players"][0]["played"] = 1
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["kind"], "unit_target")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target"), random.Random(4))
        self.assertEqual(self.state["phase"], "chain")
        self.assertIsNone(self.state["decision"])
        while self.state["phase"] == "chain":
            self.rules.apply(self.state, self.rules.legal_actions(self.state)[0], random.Random(4))
        self.assertEqual(target["temporary"], 2)


if __name__ == "__main__":
    unittest.main()
