import random
import unittest

from riftbound.origins import OriginsRules


class SpellBatch50Tests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(12))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["fury"] * 8

    def unit(self, code, player=0, location=0):
        return self.rules._new_unit(self.state, code, player, location,
                                    card=None, exhausted=False)

    def spell(self, code):
        return {"code": code, "owner": 0, "targets": [], "card": f"{code}:test"}

    def test_meditation_draws_two_when_exhausting_a_friendly_unit(self):
        target = self.unit("OGN-219", location="base:0")
        before = len(self.state["players"][0]["hand"])
        self.rules._effect_spell(self.state, {**self.spell("OGN-048"), "targets": [target["id"]]}, random.Random(1))
        self.assertTrue(target["exhausted"])
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 2)

    def test_unchecked_power_exhausts_friendly_and_damages_battlefield(self):
        friendly = self.unit("OGN-219", location="base:0")
        enemy = self.unit("OGN-210", player=1, location=0)
        self.rules._effect_spell(self.state, self.spell("OGN-123"), random.Random(1))
        self.assertTrue(friendly["exhausted"])
        self.assertEqual(enemy["damage"], 12)

    def test_catalyst_channels_two_exhausted_runes(self):
        before = len(self.state["players"][0]["rune_deck"])
        self.rules._effect_spell(self.state, self.spell("OGN-138"), random.Random(1))
        self.assertEqual(len(self.state["players"][0]["rune_deck"]), before - 2)
        self.assertTrue(all(r["exhausted"] for r in self.state["players"][0]["runes"][-2:]))

    def test_challenge_deals_each_unit_might_to_the_other(self):
        friendly = self.unit("OGN-219", location=0)
        enemy = self.unit("OGN-210", player=1, location=0)
        self.rules._effect_spell(self.state, {**self.spell("OGN-128"),
                                               "targets": [friendly["id"], enemy["id"]]}, random.Random(1))
        self.assertGreaterEqual(friendly["damage"], 1)
        self.assertGreaterEqual(enemy["damage"], 1)

    def test_wallop_readies_target(self):
        target = self.unit("OGN-219", location="base:0")
        target["exhausted"] = True
        self.rules._effect_spell(self.state, {**self.spell("OGN-146"),
                                               "targets": [target["id"]]}, random.Random(1))
        self.assertFalse(target["exhausted"])


if __name__ == "__main__":
    unittest.main()
