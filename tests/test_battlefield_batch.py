import random
import unittest

from riftbound.origins import OriginsRules
from riftbound.engine import Action


class BattlefieldBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(19))
        self.state.update(phase="main", actor=0, turn_player=0, turn=3)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["fury", "order"] * 3

    def test_grove_of_the_god_willow_draws_when_holding(self):
        self.state["fields"][0]["code"] = "OGN-280"
        self.state["fields"][0]["controller"] = 0
        before = len(self.state["players"][0]["hand"])
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)

    def test_startipped_peak_channels_an_exhausted_rune_when_holding(self):
        self.state["fields"][0]["code"] = "OGN-288"
        self.state["fields"][0]["controller"] = 0
        row = self.state["players"][0]
        rune = row["rune_deck"].pop(0)
        row["rune_deck"] = [rune]
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(row["runes"][-1]["id"], rune["id"])
        self.assertTrue(row["runes"][-1]["exhausted"])

    def test_zaun_warrens_discards_then_draws_when_conquering(self):
        self.state["fields"][0]["code"] = "OGN-298"
        row = self.state["players"][0]
        before_hand = len(row["hand"])
        self.rules._score(self.state, 0, 0, "conquer", random.Random(3))
        self.assertEqual(len(row["hand"]), before_hand)
        self.assertEqual(len(row["trash"]), 1)

    def test_vilemaws_lair_blocks_return_to_base(self):
        self.state["fields"][0]["code"] = "OGN-295"
        unit = self.rules._new_unit(self.state, "OGN-001", 0, 0, card=None, exhausted=False)
        self.assertNotIn(unit["id"], self.rules._movable(self.state, "base:0"))

    def test_back_alley_bar_buffs_units_moving_from_field(self):
        self.state["fields"][0]["code"] = "OGN-277"
        unit = self.rules._new_unit(self.state, "OGN-001", 0, 0, card=None, exhausted=False)
        self.state["selection"] = {"destination": "base:0", "units": [unit["id"]]}
        self.state["phase"] = "move_select"
        self.rules.apply(self.state, Action.make("commit_move"), random.Random(3))
        self.assertEqual(unit["temporary"], 1)


if __name__ == "__main__":
    unittest.main()
