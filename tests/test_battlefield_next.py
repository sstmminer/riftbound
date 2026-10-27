import random
import unittest

from riftbound.origins import OriginsRules


class NextBattlefieldTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(8))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)

    def unit(self, code="OGN-219", player=0, location=0):
        row = self.state["players"][player]
        card = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == code)
        row["main"].remove(card)
        unit = self.rules._new_unit(self.state, code, player, location, card=card, exhausted=False)
        self.state["fields"][location]["controller"] = player
        return unit

    def test_altar_to_unity_hold_creates_recruit(self):
        self.state["fields"][0]["code"] = "OGN-275"
        self.unit()
        before = len(self.rules._units(self.state, 0))
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(len(self.rules._units(self.state, 0)), before + 1)
        self.assertTrue(any(u["code"] == "OGN-273" for u in self.rules._units(self.state, 0)))

    def test_navori_fighting_pit_buffs_first_unbuffed_unit(self):
        self.state["fields"][0]["code"] = "OGN-283"
        unit = self.unit()
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(unit["buff"], 1)

    def test_void_gate_adds_bonus_spell_damage(self):
        self.state["fields"][0]["code"] = "OGN-296"
        unit = self.unit(location=0)
        self.rules._effect_spell(self.state, {"code": "OGN-009", "owner": 0,
                                              "targets": [unit["id"]], "card": "none"}, random.Random(3))
        self.assertEqual(unit["damage"], 4)


if __name__ == "__main__":
    unittest.main()
