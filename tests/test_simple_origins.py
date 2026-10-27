import random
import unittest

from riftbound.origins import OriginsRules


class SimpleOriginsSpellTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(2))

    def test_sky_splitter_deals_five_to_field_unit(self):
        unit = self.rules._new_unit(self.state, "OGN-001", 0, 0, card=None, exhausted=False)
        self.rules._effect_spell(self.state, {"code": "OGN-014", "owner": 0,
                                              "targets": [unit["id"]], "card": "none"}, random.Random(1))
        self.assertEqual(unit["damage"], 5)

    def test_en_garde_buffs_only_target_and_extra_when_alone(self):
        unit = self.rules._new_unit(self.state, "OGN-001", 0, "base:0", card=None, exhausted=False)
        self.rules._effect_spell(self.state, {"code": "OGN-046", "owner": 0,
                                              "targets": [unit["id"]], "card": "none"}, random.Random(1))
        self.assertEqual(unit["temporary"], 2)

    def test_find_your_center_draws_and_channels(self):
        row = self.state["players"][0]
        row["runes"].append(row["rune_deck"].pop())
        before_hand = len(row["hand"])
        self.rules._effect_spell(self.state, {"code": "OGN-047", "owner": 0,
                                              "targets": [], "card": "none"}, random.Random(1))
        self.assertEqual(len(row["hand"]), before_hand + 1)
        self.assertTrue(any(r["exhausted"] for r in row["runes"]))

    def test_grand_strategem_buffs_all_friendly_units(self):
        first = self.rules._new_unit(self.state, "OGN-001", 0, "base:0", card=None, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-010", 0, 0, card=None, exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-001", 1, "base:1", card=None, exhausted=False)
        self.rules._effect_spell(self.state, {"code": "OGN-233", "owner": 0,
                                              "targets": [], "card": "none"}, random.Random(1))
        self.assertEqual((first["temporary"], second["temporary"], enemy["temporary"]), (5, 5, 0))


if __name__ == "__main__":
    unittest.main()
