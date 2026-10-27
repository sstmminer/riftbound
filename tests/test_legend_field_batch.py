import random
import unittest

from riftbound.origins import OriginsRules


class LegendFieldBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(11))
        self.state.update(phase="main", actor=0, turn_player=0, turn=3)
        for row in self.state["players"]:
            row["energy"], row["power"] = 20, ["fury"] * 4

    def unit(self, code="OGN-219", player=0, location=0):
        row = self.state["players"][player]
        card = row["hand"].pop() if row["hand"] else None
        if card is not None:
            self.state["cards"][card]["code"] = code
        unit = self.rules._new_unit(self.state, code, player, location, card=card, exhausted=False)
        self.state["fields"][location]["controller"] = player
        return unit

    def test_blind_monk_and_bounty_hunter_actions(self):
        target = self.unit()
        row = self.state["players"][0]
        row["legend"] = "OGN-257"
        buff = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "legend_buff" and target["id"] in a.arguments)
        self.rules.apply(self.state, buff, random.Random(1))
        self.assertEqual(target["buff"], 1)
        row["legend"] = "OGN-267"
        row["legend_exhausted"] = False
        action = next(a for a in self.rules.legal_actions(self.state) if a.kind == "legend_ganking")
        self.rules.apply(self.state, action, random.Random(1))
        self.assertTrue(self.rules._ganking(self.state, target))

    def test_unforgiven_moves_and_radiant_dawn_buffs_on_stun(self):
        target = self.unit()
        row = self.state["players"][0]
        row["legend"] = "OGN-259"
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "legend_move" and '"destination":1' in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(target["location"], 1)
        row["legend"] = "OGN-261"
        enemy = self.unit(player=1, location=0)
        self.rules._effect_stun_target(self.state, {"owner": 0, "target": enemy["id"]}, random.Random(1))
        self.assertEqual(target["buff"], 1)

    def test_hold_and_conquer_battlefield_effects(self):
        token_before = len(self.rules._units(self.state, 0))
        self.state["fields"][0]["code"] = "OGN-275"
        self.rules._score(self.state, 0, 0, "hold", random.Random(1))
        self.assertEqual(len(self.rules._units(self.state, 0)), token_before + 1)
        self.state["fields"][1]["code"] = "OGN-293"
        for _ in range(7):
            self.unit(location=1)
        self.rules._score(self.state, 0, 1, "hold", random.Random(1))
        self.assertEqual(self.state["winner"], 0)

    def test_the_boss_readies_on_conquer(self):
        self.state["players"][0]["legend"] = "OGN-269"
        self.state["players"][0]["legend_exhausted"] = True
        unit = self.unit(location=0)
        self.state["fields"][0]["controller"] = 1
        self.state["fields"][0]["code"] = "OGN-276"
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": False}
        self.rules._settle_battle(self.state, random.Random(1))
        self.assertFalse(self.state["players"][0]["legend_exhausted"])


if __name__ == "__main__":
    unittest.main()
